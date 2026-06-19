from django.db import models
from django.contrib.auth.models import User


class Staff(models.Model):
    ROLE_CHOICES = [
        ("admin", "Admin"),
        ("manager", "Manager"),
        ("sales agent", "Sales agent"),
        ("support agent", "Support agent"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="staff", null=True, blank=True,)

    full_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    # role = models.CharField(max_length=50, choices=ROLE_CHOICES)
    # department = models.CharField(max_length=100)

    role = models.CharField(max_length=50, choices=ROLE_CHOICES, blank=True, default="")
    department = models.CharField(max_length=100, blank=True, default="")

    is_invited = models.BooleanField(default=False)
    invited_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.full_name
    


class Lead(models.Model):

    SOURCE_CHOICES = [
        ("Website", "Website"),
        ("WhatsApp", "WhatsApp"),
        ("Facebook Ads", "Facebook Ads"),
        ("Google Ads", "Google Ads"),
        ("Referral", "Referral"),
    ]

    PRIORITY_CHOICES = [
        ("Low", "Low"),
        ("Medium", "Medium"),
        ("High", "High"),
    ]

    STATUS_CHOICES = [
        ("new", "New"),
        ("contacted", "Contacted"),
        ("converted", "Converted"),
        ("lost", "Lost"),
    ]

    full_name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True)
    company_name = models.CharField(max_length=255)
    lead_source = models.CharField( max_length=50, choices=SOURCE_CHOICES, default="Website")
    assigned_to = models.ForeignKey( Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name="leads")
    priority = models.CharField( max_length=20, choices=PRIORITY_CHOICES, default="Medium")
    expected_closing_date = models.DateField( blank=True, null=True)
    lead_description = models.TextField( blank=True, null=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="new")
    converted_at = models.DateTimeField(blank=True, null=True)

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
        ("Google Ads", "Google Ads"),
        ("Facebook Ads", "Facebook Ads"),
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
    assigned_to = models.ForeignKey( Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name="deals")
    expected_close_date = models.DateField( blank=True, null=True )
    deal_source = models.CharField( max_length=50, choices=SOURCE_CHOICES, default="Website" )
    priority = models.CharField( max_length=20, choices=PRIORITY_CHOICES, default="Medium" )
    deal_description = models.TextField( blank=True, null=True )

    lead = models.ForeignKey(Lead, on_delete=models.SET_NULL, null=True, blank=True, related_name="deals")
    customer = models.ForeignKey("Customer", on_delete=models.SET_NULL, null=True, blank=True, related_name="deals")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Auto-create or link Customer when Deal is marked Won
        if self.stage == "Won" and self.customer is None:
            customer, created = Customer.objects.get_or_create(
                company_name=self.company_name,
                defaults={
                    "contact_name": self.lead.full_name if self.lead else "",
                    "phone_number": self.lead.phone_number if self.lead else "",
                    "email": self.lead.email if self.lead else None,
                    "industry": "",
                    "status": "active",
                    "lifetime_value": self.deal_amount,
                },
            )
            if not created:
                # Add deal amount to existing customer's lifetime value
                customer.lifetime_value += self.deal_amount
                customer.save()
    
            self.customer = customer

            # Mark the originating lead as converted
            if self.lead and self.lead.status != "converted":
                from django.utils import timezone
                self.lead.status = "converted"
                self.lead.converted_at = timezone.now()
                self.lead.save()

        super().save(*args, **kwargs)

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
    assigned_to = models.ForeignKey( Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name="tasks")
    related_to = models.CharField( max_length=255, blank=True, null=True, help_text="e.g. Deal: Website Redesign")
    priority = models.CharField( max_length=10, choices=PRIORITY_CHOICES)
    status = models.CharField( max_length=20, choices=STATUS_CHOICES, default="pending")
    due_date = models.DateField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title
    


class PicklistOption(models.Model):
    FIELD_CHOICES = [
        ("lead_status", "Lead Status"),
        ("lead_source", "Lead Source"),
        ("lead_priority", "Lead Priority"),
        ("deal_stage", "Deal Stage"),
        ("deal_source", "Deal Source"),
        ("deal_priority", "Deal Priority"),
        ("customer_status", "Customer Status"),
        ("customer_industry", "Customer Industry"),
        ("task_status", "Task Status"),
        ("task_priority", "Task Priority"),
    ]

    field = models.CharField(max_length=50, choices=FIELD_CHOICES)
    value = models.CharField(max_length=50)   # internal value, e.g. "new"
    label = models.CharField(max_length=50)   # display label, e.g. "New"
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("field", "value")
        ordering = ["field", "order"]

    def __str__(self):
        return f"{self.field}: {self.label}"