from django.db import models


class Lead(models.Model):

    SOURCE_CHOICES = [
        ("Website", "Website"),
        ("Ads", "Ads"),
        ("Referral", "Referral"),
        ("WhatsApp", "WhatsApp"),
    ]

    PRIORITY_CHOICES = [
        ("Low", "Low"),
        ("Medium", "Medium"),
        ("High", "High"),
    ]

    full_name = models.CharField(max_length=255)
    phone_number = models.IntegerField(max_length=20)
    email = models.EmailField(blank=True, null=True)

    company_name = models.CharField(max_length=255)

    lead_source = models.CharField( max_length=50, choices=SOURCE_CHOICES, default="Website")

    assigned_to = models.CharField(max_length=255)

    priority = models.CharField( max_length=20, choices=PRIORITY_CHOICES, default="Medium")

    expected_closing_date = models.DateField( blank=True, null=True)

    lead_description = models.TextField( blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.full_name