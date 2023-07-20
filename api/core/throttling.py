from rest_framework.throttling import UserRateThrottle


class BurstRateThrottle(UserRateThrottle):
    scope = "burst"
    rate = "20/minute"


class SustainedRateThrottle(UserRateThrottle):
    scope = "sustained"
    rate = "1000/day"


class MutationRequestThrottleViewMixin:
    """
    Used for throttling endpoints that generates audit logs
    """

    mutation_methods = ["POST", "PUT", "PATCH", "DELETE"]

    def get_throttles(self):
        throttles = []
        if self.request.method in self.mutation_methods:
            throttles = [BurstRateThrottle(), SustainedRateThrottle()]
        return throttles
