# Generated migration for MetaDeletionRequest model.
import uuid

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('AdminApp', '0070_metapage_webhook_subscription_error'),
    ]

    operations = [
        migrations.CreateModel(
            name='MetaDeletionRequest',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                (
                    'confirmation_code',
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        unique=True,
                        db_index=True,
                    ),
                ),
                (
                    'facebook_user_id',
                    models.CharField(db_index=True, max_length=255),
                ),
                (
                    'company',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='meta_deletion_requests',
                        to='AdminApp.company',
                    ),
                ),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('pending', 'Pending'),
                            ('completed', 'Completed'),
                            ('not_found', 'Not Found \u2014 no matching integration'),
                            ('error', 'Error \u2014 processing failed'),
                        ],
                        default='pending',
                        max_length=20,
                    ),
                ),
                ('notes', models.TextField(blank=True, default='')),
                (
                    'requested_at',
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    'completed_at',
                    models.DateTimeField(blank=True, null=True),
                ),
            ],
            options={
                'ordering': ['-requested_at'],
            },
        ),
        migrations.AddIndex(
            model_name='metadeletionrequest',
            index=models.Index(
                fields=['facebook_user_id', 'status'],
                name='metadel_uid_status_idx',
            ),
        ),
    ]
