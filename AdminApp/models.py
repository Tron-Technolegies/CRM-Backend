from django.db import models
from django.contrib.auth.models import User


class Company(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True)
    website = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Staff(models.Model):
    ROLE_CHOICES = [
        ("admin", "Admin"),
        ("manager", "Manager"),
        ("sales agent", "Sales agent"),
        ("support agent", "Support agent"),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True, related_name="staff")

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="staff", null=True, blank=True,)

    full_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=50, choices=ROLE_CHOICES, blank=True, default="")
    department = models.CharField(max_length=100, blank=True, default="")

    is_invited = models.BooleanField(default=False)
    invited_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.full_name



class Customer(models.Model):
    STATUS_CHOICES = [
        ("active", "Active"),
        ("inactive", "Inactive"),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True, related_name="customers")

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

    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True, related_name="leads")

    full_name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True)
    company_name = models.CharField(max_length=255)
    lead_source = models.CharField(max_length=50, choices=SOURCE_CHOICES, default="Website")
    assigned_to = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name="leads")
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default="Medium")
    lead_description = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="new")
    
    converted_customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name="originating_leads")
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

    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True, related_name="deals")

    deal_name = models.CharField(max_length=255)
    company_name = models.CharField(max_length=255)
    deal_amount = models.DecimalField( max_digits=12, decimal_places=2, default=0 )
    stage = models.CharField( max_length=50, choices=STAGE_CHOICES, default="Discussion" )
    assigned_to = models.ForeignKey( Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name="deals")
    expected_close_date = models.DateField( blank=True, null=True )
    deal_source = models.CharField( max_length=50, choices=SOURCE_CHOICES, default="Website" )
    priority = models.CharField( max_length=20, choices=PRIORITY_CHOICES, default="Medium" )
    deal_description = models.TextField( blank=True, null=True )

    customer = models.ForeignKey("Customer", on_delete=models.SET_NULL, null=True, blank=True, related_name="deals")
    account = models.ForeignKey("Accounts", on_delete=models.SET_NULL, null=True, blank=True, related_name="deals")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    def __str__(self):
        return self.deal_name
    



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

    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True, related_name="tasks")

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

    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True, related_name="picklist_options")

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
    


class Address(models.Model):
    country = models.CharField(max_length=255, blank=True)
    address = models.CharField(max_length=255, blank=True)
    street_address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=255, blank=True)
    state = models.CharField(max_length=255, blank=True)
    zip_code = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return f"{self.city}, {self.state}, {self.country}"



class Accounts(models.Model):

    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True, related_name="accounts")

    account_name = models.CharField(max_length=255)
    assigned_to = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name="accounts")
    phone_number = models.CharField(max_length=20, blank=True)
    account_site = models.CharField(max_length=255, blank=True)
    parent_account = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name="sub_accounts")
    website = models.CharField(max_length=255, blank=True)
    account_type = models.CharField(max_length=255, blank=True)
    industry = models.CharField(max_length=255, blank=True)
    ownership = models.CharField(max_length=255, blank=True)
    employees = models.CharField(max_length=20, blank=True)

    billing_address = models.ForeignKey(Address, on_delete=models.SET_NULL, null=True, blank=True, related_name="billing_accounts")
    shipping_address = models.ForeignKey(Address, on_delete=models.SET_NULL, null=True, blank=True, related_name="shipping_accounts")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def delete(self, *args, **kwargs):
        
        if self.billing_address:
            self.billing_address.delete()
        if self.shipping_address:
            self.shipping_address.delete()
        super().delete(*args, **kwargs)



class Product(models.Model):
    PRODUCT_TYPE = [
        ("goods", "Goods"),
        ("service", "Service"),
    ]

    STATUS = [
        ("active", "Active"),
        ("inactive", "Inactive"),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True, related_name="products")

    name = models.CharField(max_length=255)
    product_code = models.CharField(max_length=50, unique=True)
    sku = models.CharField(max_length=100, unique=True)
    product_type = models.CharField( max_length=20, choices=PRODUCT_TYPE, default="goods")
    category = models.CharField(max_length=100, blank=True, null=True)
    manufacturer = models.CharField(max_length=255, blank=True, null=True)

    vendor = models.ForeignKey( "Vendor", on_delete=models.SET_NULL, null=True, blank=True, related_name="products")

    unit_price = models.DecimalField( max_digits=12, decimal_places=2)
    cost_price = models.DecimalField( max_digits=12, decimal_places=2, default=0)
    tax_percentage = models.DecimalField( max_digits=5, decimal_places=2, default=0)
    quantity_in_stock = models.PositiveIntegerField(default=0)
    reorder_level = models.PositiveIntegerField(default=0)
    unit = models.CharField( max_length=50, default="Nos")
    description = models.TextField(blank=True, null=True)
    status = models.CharField( max_length=20, choices=STATUS, default="active")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name



class Quotes(models.Model):
    QUOTE_STAGE_CHOICES = [
        ('draft', 'Draft'),
        ('negotiation', 'Negotiation'),
        ('delivered', 'Delivered'),
        ('on_hold', 'On Hold'),
        ('confirmed', 'Confirmed'),
        ('closed_won', 'Closed Won'),
        ('closed_lost', 'Closed Lost'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True, related_name="quotes")
    
    subject = models.CharField(max_length=255)
    quote_stage = models.CharField(max_length=50, choices=QUOTE_STAGE_CHOICES, default='draft')
    valid_until = models.DateField(null=True, blank=True)

    assigned_to = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name="quotes")
    deal = models.ForeignKey('Deal', on_delete=models.SET_NULL, null=True, blank=True, related_name="quotes")
    contact_name = models.CharField(max_length=255)
    account = models.ForeignKey(Accounts, on_delete=models.SET_NULL, null=True, blank=True, related_name="quotes")

    billing_address = models.ForeignKey(Address, on_delete=models.SET_NULL, null=True, blank=True, related_name="quote_billing")
    shipping_address = models.ForeignKey(Address, on_delete=models.SET_NULL, null=True, blank=True, related_name="quote_shipping")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.subject

    def delete(self, *args, **kwargs):
        if self.billing_address:
            self.billing_address.delete()
        if self.shipping_address:
            self.shipping_address.delete()
        super().delete(*args, **kwargs)

class QuoteProduct(models.Model):  

    quote = models.ForeignKey(Quotes, on_delete=models.CASCADE, related_name="items")
    
    product = models.ForeignKey( Product, on_delete=models.CASCADE)
    description = models.TextField(blank=True, null=True)
    
    quantity = models.PositiveIntegerField(default=1)
    list_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    discount = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, help_text="Percentage or Fixed amount")
    tax = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, help_text="Tax percentage")
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.product} (Quote: {self.quote.subject})"
    


class Meeting(models.Model):
    VENUE_CHOICES = [
        ("online", "Online"),
        ("client_location", "Client Location"),
        ("in_office", "In-Office"),
    ]

    PROVIDER_CHOICES = [
        ("zoom", "Zoom"),
        ("google_meet", "Google Meet"),
        ("microsoft_teams", "Microsoft Teams"),
        ("other", "Other"),
    ]

    RELATED_TYPE_CHOICES = [
        ("none", "None"),
        ("lead", "Lead"),
        ("customer", "Customer"),
    ]

    REPEAT_CHOICES = [
        ("none", "None"),
        ("daily", "Daily"),
        ("weekly", "Weekly"),
        ("monthly", "Monthly"),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True, related_name="meetings")

    title = models.CharField(max_length=255)
    meeting_venue = models.CharField(max_length=50, choices=VENUE_CHOICES, default="online")

    provider = models.CharField(max_length=50, choices=PROVIDER_CHOICES, blank=True, default="")

    location = models.CharField(max_length=255, blank=True, default="")
    all_day = models.BooleanField(default=False)

    from_datetime = models.DateTimeField()
    to_datetime = models.DateTimeField()

    host = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name="hosted_meetings")
    participants = models.ManyToManyField(Staff, blank=True, related_name="meetings")

    related_type = models.CharField(max_length=20, choices=RELATED_TYPE_CHOICES, default="none")
    related_lead = models.ForeignKey(Lead, on_delete=models.SET_NULL, null=True, blank=True, related_name="meetings")
    related_customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name="meetings")

    repeat = models.CharField(max_length=20, choices=REPEAT_CHOICES, default="none")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title



class Call(models.Model):
    CALL_TYPE = [
        ("inbound", "Inbound"),
        ("outbound", "Outbound"),
    ]

    STATUS = [
        ("scheduled", "Scheduled"),
        ("completed", "Completed"),
        ("missed", "Missed"),
        ("cancelled", "Cancelled"),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True, related_name="calls")

    subject = models.CharField(max_length=200)
    call_type = models.CharField(max_length=20, choices=CALL_TYPE)
    status = models.CharField(max_length=20, choices=STATUS, default="scheduled")
    start_time = models.DateTimeField()
    duration = models.PositiveIntegerField(help_text="Duration in minutes")
    notes = models.TextField(blank=True)

    assigned_to = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name="calls")

    lead = models.ForeignKey(Lead, null=True, blank=True, on_delete=models.SET_NULL, related_name="calls")
    contact = models.ForeignKey(Customer, null=True, blank=True, on_delete=models.SET_NULL, related_name="calls")
    deal = models.ForeignKey(Deal, null=True, blank=True, on_delete=models.SET_NULL, related_name="calls")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.subject
    


class Vendor(models.Model):
    STATUS_CHOICES = [
        ("active", "Active"),
        ("inactive", "Inactive"),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True, related_name="vendors")

    vendor_name = models.CharField(max_length=255)
    vendor_code = models.CharField(max_length=50, unique=True)
    contact_person = models.CharField(max_length=255, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    mobile = models.CharField(max_length=20, blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    gst_number = models.CharField(max_length=30, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    notes = models.TextField(blank=True, null=True)

    # Replace flat address fields with structured Address FK
    address = models.OneToOneField(
        Address, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="vendor"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.vendor_name

    def delete(self, *args, **kwargs):
        if self.address:
            self.address.delete()
        super().delete(*args, **kwargs)
    


class PriceBook(models.Model):
    STATUS_CHOICES = [
        ("active", "Active"),
        ("inactive", "Inactive"),
    ]

    company = models.ForeignKey( Company, on_delete=models.CASCADE, null=True, blank=True,)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    status = models.CharField( max_length=20, choices=STATUS_CHOICES, default="active")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
    
class PriceBookItem(models.Model):
    
    price_book = models.ForeignKey( PriceBook, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey( Product, on_delete=models.CASCADE, related_name="price_book_items")
    price = models.DecimalField( max_digits=10, decimal_places=2)

    class Meta:
        unique_together = ("price_book", "product")

    def __str__(self):
        return f"{self.price_book.name} - {self.product.name}"
    


class SalesOrder(models.Model):
    STATUS_CHOICES = [
        ("created", "Created"),
        ("approved", "Approved"),
        ("delivered", "Delivered"),
        ("cancelled", "Cancelled"),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True, related_name="sales_orders")

    owner = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name="sales_orders")
    subject = models.CharField(max_length=255)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="sales_orders")
    quote = models.ForeignKey(Quotes, on_delete=models.SET_NULL, null=True, blank=True, related_name="sales_orders")
    deal = models.ForeignKey(Deal, on_delete=models.SET_NULL, null=True, blank=True, related_name="sales_orders")  # add this
    purchase_order_number = models.CharField(max_length=100, blank=True)
    carrier = models.CharField(max_length=100, blank=True)
    sales_commission = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="created")
    excise_duty = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    billing_address = models.OneToOneField(Address, on_delete=models.SET_NULL, null=True, blank=True, related_name="sales_order_billing")
    shipping_address = models.OneToOneField(Address, on_delete=models.SET_NULL, null=True, blank=True, related_name="sales_order_shipping")
    terms_and_conditions = models.TextField(blank=True)
    description = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.subject

    def delete(self, *args, **kwargs):
        if self.billing_address:
            self.billing_address.delete()
        if self.shipping_address:
            self.shipping_address.delete()
        super().delete(*args, **kwargs)
    
class SalesOrderItem(models.Model):
    sales_order = models.ForeignKey(SalesOrder, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    list_price = models.DecimalField(max_digits=12, decimal_places=2)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    description = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        self.line_total = (self.list_price * self.quantity) - self.discount + self.tax
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.name}"
    


class Invoice(models.Model):

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("sent", "Sent"),
        ("paid", "Paid"),
        ("overdue", "Overdue"),
        ("cancelled", "Cancelled"),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True, related_name="invoices")

    owner = models.ForeignKey( Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name="invoices")
    subject = models.CharField(max_length=255)
    invoice_number = models.CharField( max_length=50, unique=True)
    customer = models.ForeignKey( Customer, on_delete=models.PROTECT, related_name="invoices")
    sales_order = models.ForeignKey( SalesOrder, on_delete=models.SET_NULL, null=True, blank=True, related_name="invoices")
    billing_address = models.OneToOneField( Address, on_delete=models.CASCADE, null=True, blank=True, related_name="invoice_billing")
    shipping_address = models.OneToOneField( Address, on_delete=models.CASCADE, null=True, blank=True, related_name="invoice_shipping")
    invoice_date = models.DateField()
    due_date = models.DateField( null=True, blank=True)
    purchase_order_number = models.CharField( max_length=100, blank=True)
    status = models.CharField( max_length=20, choices=STATUS_CHOICES, default="draft")
    terms_and_conditions = models.TextField(blank=True)
    description = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            last_invoice = Invoice.objects.order_by("-id").first()

            if last_invoice:
                last_number = int(last_invoice.invoice_number.split("-")[-1])
                next_number = last_number + 1
            else:
                next_number = 1

            self.invoice_number = f"INV-{next_number:05d}"

        super().save(*args, **kwargs)
    def delete(self, *args, **kwargs):
        if self.billing_address:
            self.billing_address.delete()
        if self.shipping_address:
            self.shipping_address.delete()
        super().delete(*args, **kwargs)
    
class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="invoice_items")
    quantity = models.PositiveIntegerField()
    list_price = models.DecimalField(max_digits=12, decimal_places=2)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def save(self, *args, **kwargs):
        self.line_total = (self.list_price * self.quantity) - self.discount + self.tax
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.name}"
    


class PurchaseOrder(models.Model):

    STATUS_CHOICES = [
        ("created", "Created"),
        ("sent", "Sent"),
        ("confirmed", "Confirmed"),
        ("partially_received", "Partially Received"),
        ("received", "Received"),
        ("cancelled", "Cancelled"),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True, related_name="purchase_orders")

    owner = models.ForeignKey( Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name="purchase_orders")
    subject = models.CharField(max_length=255)
    purchase_order_number = models.CharField( max_length=50, unique=True, editable=False)
    vendor = models.ForeignKey( Vendor, on_delete=models.PROTECT, related_name="purchase_orders")
    billing_address = models.OneToOneField( Address, on_delete=models.CASCADE, null=True, blank=True, related_name="purchase_order_billing")
    shipping_address = models.OneToOneField( Address, on_delete=models.CASCADE, null=True, blank=True, related_name="purchase_order_shipping")
    purchase_date = models.DateField()
    expected_delivery_date = models.DateField( null=True, blank=True)
    status = models.CharField( max_length=30, choices=STATUS_CHOICES, default="created")
    terms_and_conditions = models.TextField( blank=True)
    description = models.TextField( blank=True)
    created_at = models.DateTimeField( auto_now_add=True)
    updated_at = models.DateTimeField( auto_now=True)

    def save(self, *args, **kwargs):
        if not self.purchase_order_number:
            last_po = PurchaseOrder.objects.order_by("-id").first()

            if last_po:
                last_number = int(last_po.purchase_order_number.split("-")[1])
                next_number = last_number + 1
            else:
                next_number = 1

            self.purchase_order_number = f"PO-{next_number:05d}"

        super().save(*args, **kwargs)

    def __str__(self):
        return self.purchase_order_number

    def delete(self, *args, **kwargs):
        if self.billing_address:
            self.billing_address.delete()

        if self.shipping_address:
            self.shipping_address.delete()

        super().delete(*args, **kwargs)

class PurchaseOrderItem(models.Model):

    purchase_order = models.ForeignKey( PurchaseOrder, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey( Product, on_delete=models.PROTECT, related_name="purchase_order_items")
    quantity = models.PositiveIntegerField()
    list_price = models.DecimalField( max_digits=12, decimal_places=2)
    discount = models.DecimalField( max_digits=12, decimal_places=2, default=0)
    tax = models.DecimalField( max_digits=12, decimal_places=2, default=0)
    line_total = models.DecimalField( max_digits=12, decimal_places=2, default=0)
    description = models.TextField( blank=True)

    def save(self, *args, **kwargs):
        self.line_total = (
            (self.list_price * self.quantity)
            - self.discount
            + self.tax
        )

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.purchase_order.purchase_order_number} - {self.product.name}"