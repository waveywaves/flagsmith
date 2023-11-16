from __future__ import annotations

import re
import typing

from core.models import (
    SoftDeleteExportableModel,
    abstract_base_auditable_model_factory,
)
from django.conf import settings
from django.core.cache import caches
from django.db import models
from django.utils import timezone
from django_lifecycle import (
    AFTER_SAVE,
    AFTER_UPDATE,
    BEFORE_CREATE,
    LifecycleModelMixin,
    hook,
)

from audit.related_object_type import RelatedObjectType
from organisations.models import Organisation
from permissions.models import (
    PROJECT_PERMISSION_TYPE,
    AbstractBasePermissionModel,
    PermissionModel,
)
from projects.managers import ProjectManager
from projects.tasks import write_environments_to_dynamodb

if typing.TYPE_CHECKING:
    from environments.models import Environment
    from features.models import Feature
    from segments.models import Segment

# TODO #2797 add audit log tests for permission changes

project_segments_cache = caches[settings.PROJECT_SEGMENTS_CACHE_LOCATION]
environment_cache = caches[settings.ENVIRONMENT_CACHE_NAME]


UNAUDITED_PROJECT_FIELDS = (
    "hide_disabled_flags",
    "enable_dynamo_db",
    "prevent_flag_defaults",
    "enable_realtime_updates",
    "only_allow_lower_case_feature_names",
    "feature_name_regex",
    "max_segments_allowed",
    "max_features_allowed",
    "max_segment_overrides_allowed",
)


class Project(
    LifecycleModelMixin,
    SoftDeleteExportableModel,
    abstract_base_auditable_model_factory(
        RelatedObjectType.PROJECT,
        UNAUDITED_PROJECT_FIELDS,
        audit_create=True,
        audit_delete=True,
    ),
):
    name = models.CharField(max_length=2000)
    created_date = models.DateTimeField("DateCreated", auto_now_add=True)
    organisation = models.ForeignKey(
        Organisation, related_name="projects", on_delete=models.CASCADE
    )
    organisation_id: int
    hide_disabled_flags = models.BooleanField(
        default=False,
        help_text="If true will exclude flags from SDK which are " "disabled",
    )
    enable_dynamo_db = models.BooleanField(
        default=False,
        help_text="If true will sync environment data with dynamodb and allow access to dynamodb identities",
    )
    prevent_flag_defaults = models.BooleanField(
        default=False,
        help_text="Prevent defaults from being set in all environments when creating a feature.",
    )
    enable_realtime_updates = models.BooleanField(
        default=False,
        help_text="Enable this to trigger a realtime(sse) event whenever the value of a flag changes",
    )
    only_allow_lower_case_feature_names = models.BooleanField(
        default=True, help_text="Used by UI to validate feature names"
    )
    feature_name_regex = models.CharField(
        null=True,
        blank=True,
        max_length=255,
        help_text="Used for validating feature names",
    )
    max_segments_allowed = models.IntegerField(
        default=100, help_text="Max segments allowed for this project"
    )
    max_features_allowed = models.IntegerField(
        default=400, help_text="Max features allowed for this project"
    )
    max_segment_overrides_allowed = models.IntegerField(
        default=100,
        help_text="Max segments overrides allowed for any (one) environment within this project",
    )

    objects = ProjectManager()

    environments: models.QuerySet[Environment]
    features: models.QuerySet[Feature]
    segments: models.QuerySet[Segment]

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return "Project %s" % self.name

    @property
    def is_too_large(self) -> bool:
        return (
            self.features.count() > self.max_features_allowed
            or self.segments.count() > self.max_segments_allowed
            or self.environments.annotate(
                segment_override_count=models.Count("feature_segments")
            )
            .filter(segment_override_count__gt=self.max_segment_overrides_allowed)
            .exists()
        )

    def get_segments_from_cache(self):
        segments = project_segments_cache.get(self.id)

        if not segments:
            # This is optimised to account for rules nested one levels deep (since we
            # don't support anything above that from the UI at the moment). Anything
            # past that will require additional queries / thought on how to optimise.
            segments = self.segments.all().prefetch_related(
                "rules",
                "rules__conditions",
                "rules__rules",
                "rules__rules__conditions",
                "rules__rules__rules",
            )
            project_segments_cache.set(
                self.id, segments, timeout=settings.CACHE_PROJECT_SEGMENTS_SECONDS
            )

        return segments

    @hook(BEFORE_CREATE)
    def set_enable_dynamo_db(self):
        self.enable_dynamo_db = self.enable_dynamo_db or (
            settings.EDGE_RELEASE_DATETIME is not None
            and settings.EDGE_RELEASE_DATETIME < timezone.now()
        )

    @hook(AFTER_SAVE)
    def clear_environments_cache(self):
        environment_cache.delete_many(
            list(self.environments.values_list("api_key", flat=True))
        )

    @hook(AFTER_UPDATE)
    def write_to_dynamo(self):
        write_environments_to_dynamodb.delay(kwargs={"project_id": self.id})

    @property
    def is_edge_project_by_default(self) -> bool:
        return bool(
            settings.EDGE_RELEASE_DATETIME
            and self.created_date >= settings.EDGE_RELEASE_DATETIME
        )

    def is_feature_name_valid(self, feature_name: str) -> bool:
        """
        Validate the feature name based on the feature_name_regex attribute.

        Since we always want to evaluate the regex against the whole string, we're wrapping the
        attribute value in ^(...)$. Note that ^(...)$ and ^^(...)$$ are equivalent (in case the
        attribute already has the boundaries defined)
        """
        return (
            not self.feature_name_regex
            or re.match(f"^{self.feature_name_regex}$", feature_name) is not None
        )

    def get_audit_log_identity(self) -> str:
        return self.name

    def get_project(self, delta=None) -> Project | None:
        return self


class ProjectPermissionManager(models.Manager):
    def get_queryset(self):
        return (
            super(ProjectPermissionManager, self)
            .get_queryset()
            .filter(type=PROJECT_PERMISSION_TYPE)
        )


class ProjectPermissionModel(PermissionModel):
    class Meta:
        proxy = True

    objects = ProjectPermissionManager()


class UserPermissionGroupProjectPermission(AbstractBasePermissionModel):
    group = models.ForeignKey("users.UserPermissionGroup", on_delete=models.CASCADE)
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_query_name="grouppermission"
    )
    admin = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["group", "project"], name="unique_group_project_permission"
            )
        ]

    def get_audit_log_identity(self) -> str:
        return f"{self.group.name} / {self.project.name}"

    def get_project(self, delta=None) -> Project | None:
        return self.project


class UserProjectPermission(AbstractBasePermissionModel):
    user = models.ForeignKey("users.FFAdminUser", on_delete=models.CASCADE)
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_query_name="userpermission"
    )
    admin = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "project"], name="unique_user_project_permission"
            )
        ]

    def get_audit_log_identity(self) -> str:
        return f"{self.user.email} / {self.project.name}"

    def get_project(self, delta=None) -> Project | None:
        return self.project
