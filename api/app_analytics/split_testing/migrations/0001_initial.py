# Generated by Django 3.2.23 on 2024-01-04 18:46

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('environments', '0033_add_environment_feature_state_version_logic'),
        ('features', '0062_alter_feature_segment_unique_together'),
        ('multivariate', '0007_alter_boolean_values'),
        ('identities', '0002_alter_identity_index_together'),
    ]

    operations = [
        migrations.CreateModel(
            name='SplitTest',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('evaluation_count', models.PositiveIntegerField()),
                ('conversion_count', models.PositiveIntegerField()),
                ('pvalue', models.FloatField()),
                ('created_at', models.DateTimeField(auto_now_add=True, null=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('environment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='split_tests', to='environments.environment')),
                ('feature', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='split_tests', to='features.feature')),
                ('multivariate_feature_option', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='multivariate.multivariatefeatureoption')),
            ],
        ),
        migrations.CreateModel(
            name='ConversionEvent',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, null=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('environment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='conversion_events', to='environments.environment')),
                ('identity', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='conversion_events', to='identities.identity')),
            ],
        ),
        migrations.AddConstraint(
            model_name='splittest',
            constraint=models.UniqueConstraint(fields=('environment', 'feature', 'multivariate_feature_option'), name='unique_environment_feature_mvfo'),
        ),
    ]
