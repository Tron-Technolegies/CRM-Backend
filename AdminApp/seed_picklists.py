from AdminApp.models import PicklistOption

seed_data = {
    "lead_status": [("new", "New"), ("contacted", "Contacted"), ("converted", "Converted"), ("lost", "Lost")],
    "lead_source": [("Website", "Website"), ("WhatsApp", "WhatsApp"), ("Facebook Ads", "Facebook Ads"), ("Google Ads", "Google Ads"), ("Referral", "Referral")],
    "lead_priority": [("Low", "Low"), ("Medium", "Medium"), ("High", "High")],
    "deal_stage": [("Discussion", "Discussion"), ("Demo", "Demo"), ("Proposal", "Proposal"), ("Negotiation", "Negotiation"), ("Won", "Won"), ("Lost", "Lost")],
    "deal_source": [("Website", "Website"), ("Ads", "Ads"), ("Referral", "Referral"), ("WhatsApp", "WhatsApp")],
    "deal_priority": [("Low", "Low"), ("Medium", "Medium"), ("High", "High")],
    "customer_status": [("active", "Active"), ("inactive", "Inactive")],
    "customer_industry": [("Technology", "Technology"), ("Finance", "Finance"), ("Software", "Software"), ("Design", "Design"), ("Marketing", "Marketing"), ("Nonprofit", "Nonprofit")],
    "task_status": [("pending", "Pending"), ("in_progress", "In Progress"), ("completed", "Completed")],
    "task_priority": [("low", "Low"), ("medium", "Medium"), ("high", "High")],
}

for field, options in seed_data.items():
    for i, (value, label) in enumerate(options):
        PicklistOption.objects.get_or_create(field=field, value=value, defaults={"label": label, "order": i})

print("Seeded successfully")