from django.conf import settings
from django.core.mail import send_mail

from AdminApp.models import Notification, NotificationPreference


def get_related_label(related_type, lead=None, contact=None, deal=None, account=None):
    """
    Build a human-readable 'Related To' label for notification emails.
    Expects the actual model instances (already fetched), not IDs.
    """
    if related_type == "lead" and lead:
        return f"Lead - {lead.full_name}"
    elif related_type == "contact" and contact:
        return f"Contact - {contact.contact_name}"
    elif related_type == "deal" and deal:
        return f"Deal - {deal.deal_name}"
    elif related_type == "account" and account:
        return f"Account - {account.account_name}"
    return None


def notify_user(
    *,
    company,
    user,
    notification_type,
    title,
    message,
):

    notification = Notification.objects.create(
        company=company,
        user=user,
        notification_type=notification_type,
        title=title,
        message=message,
    )

    preference, _ = NotificationPreference.objects.get_or_create(
        company=company,
        user=user,
    )

    send_email = False

    if notification_type == "new_lead":
        send_email = preference.email_new_lead_alerts

    elif notification_type == "lead_assigned":
        send_email = preference.email_new_lead_alerts

    elif notification_type == "deal_assigned":
        send_email = preference.email_deal_assignments

    elif notification_type == "task_assigned":
        send_email = preference.email_task_assignments

    elif notification_type == "meeting_reminder":
        send_email = preference.email_meeting_reminders

    elif notification_type == "call_assigned":
        send_email = preference.email_call_assignments

    elif notification_type == "case_assigned":
        send_email = preference.email_case_assignments

    elif notification_type == "sales_order":
        send_email = preference.email_sales_order_updates

    elif notification_type == "purchase_order":
        send_email = preference.email_purchase_order_updates

    elif notification_type == "invoice_created":
        send_email = preference.email_invoice_updates

    elif notification_type == "system_update":
        send_email = preference.email_system_updates

    else:
        send_email = True

    if send_email:
        send_mail(
            subject=title,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )

    return notification