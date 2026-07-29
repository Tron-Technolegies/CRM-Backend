from django.core.management.base import BaseCommand

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


class Command(BaseCommand):
    help = "Seed global default picklist options (company=None)"

    def handle(self, *args, **options):
        created_count = 0
        for field, options_list in seed_data.items():
            for i, (value, label) in enumerate(options_list):
                obj, created = PicklistOption.objects.get_or_create(
                    company=None,
                    field=field,
                    value=value,
                    defaults={"label": label, "order": i},
                )
                if created:
                    created_count += 1

        self.stdout.write(self.style.SUCCESS(f"Seeded {created_count} new picklist options"))