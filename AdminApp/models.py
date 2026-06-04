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
    


class Customer(models.Model):
    STATUS_CHOICES = [
        ("active", "Active"),
        ("inactive", "Inactive"),
    ]

    company_name = models.CharField(max_length=255)
    contact_name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True)
    industry = models.CharField(max_length=50)
    status = models.CharField( max_length=20, choices=STATUS_CHOICES, default="active")
    lifetime_value = models.DecimalField( max_digits=12, decimal_places=2, default=0 )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.company_name
    


class Task(models.Model):
    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
    ]

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    assigned_to = models.CharField(max_length=255)
    related_to = models.CharField( max_length=255, blank=True, null=True, help_text="e.g. Deal: Website Redesign")
    priority = models.CharField( max_length=10, choices=PRIORITY_CHOICES)
    status = models.CharField( max_length=20, choices=STATUS_CHOICES, default="pending")
    due_date = models.DateField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title
    


class Staff(models.Model):
    ROLE_CHOICES = [
        ("admin", "Admin"),
        ("manager", "Manager"),
        ("sales agent", "Sales agent"),
        ("support agent", "Support agent"),
    ]

    full_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=50, choices=ROLE_CHOICES)
    department = models.CharField(max_length=100)

    is_invited = models.BooleanField(default=True)
    invited_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.full_name