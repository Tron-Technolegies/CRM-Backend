from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('AdminApp', '0067_alter_lead_company_name_alter_lead_phone_number_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='metapage',
            name='webhook_subscription_status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pending'),
                    ('subscribed', 'Subscribed'),
                    ('failed', 'Failed'),
                    ('no_token', 'No Token - Not Attempted'),
                ],
                default='pending',
                max_length=20,
            ),
        ),
    ]
