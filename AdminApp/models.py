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

    phone_number = models.CharField(max_length=20)

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
    


class Deal(models.Model):

    STAGE_CHOICES = [
        ("Discussion", "Discussion"),
        ("Demo", "Demo"),
        ("Proposal", "Proposal"),
        ("Negotiation", "Negotiation"),
        ("Won", "Won"),
        ("Lost", "Lost"),
    ]

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

    deal_name = models.CharField(max_length=255)

    company_name = models.CharField(max_length=255)

    deal_amount = models.DecimalField( max_digits=12, decimal_places=2, default=0 )

    stage = models.CharField( max_length=50, choices=STAGE_CHOICES, default="Discussion" )

    assigned_to = models.CharField(max_length=255)

    expected_close_date = models.DateField( blank=True, null=True )

    deal_source = models.CharField( max_length=50, choices=SOURCE_CHOICES, default="Website" )

    priority = models.CharField( max_length=20, choices=PRIORITY_CHOICES, default="Medium" )
    
    deal_description = models.TextField( blank=True, null=True )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.deal_name