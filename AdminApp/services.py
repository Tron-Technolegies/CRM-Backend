from django.conf import settings
from django.core.mail import send_mail
import logging

from AdminApp.models import Lead, Notification, NotificationPreference, Staff


logger = logging.getLogger(__name__)


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


import threading

def _send_email_async(subject, message, from_email, recipient_list):
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=recipient_list,
            fail_silently=True,
        )
    except Exception as e:
        logger.warning(f"Async email sending failed: {e}")

def notify_user(
    *,
    company,
    user,
    notification_type,
    title,
    message,
):
    from django.contrib.auth.models import User as AuthUser
    from AdminApp.models import Staff as StaffModel

    target_user = None
    target_email = None

    if isinstance(user, AuthUser):
        target_user = user
        target_email = user.email
    elif isinstance(user, StaffModel):
        target_user = user.user or AuthUser.objects.filter(email__iexact=user.email).first()
        target_email = user.email or (target_user.email if target_user else None)
    elif user is not None:
        target_user = getattr(user, "user", None) or user
        target_email = getattr(user, "email", None)

    if not target_user:
        logger.warning(f"Could not find User for notification: {user}")
        return None

    notification = Notification.objects.create(
        company=company,
        user=target_user,
        notification_type=notification_type,
        title=title,
        message=message,
    )

    preference, _ = NotificationPreference.objects.get_or_create(
        company=company,
        user=target_user,
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

    if send_email and target_email:
        thread = threading.Thread(
            target=_send_email_async,
            args=(title, message, settings.DEFAULT_FROM_EMAIL, [target_email]),
            daemon=True,
        )
        thread.start()

    return notification



def get_meta_lead_staff(company):
    return Staff.objects.filter(
        company=company,
        is_accepted=True,
        user__is_active=True,
    ).first()

def create_lead_for_company(
    company,
    full_name,
    phone_number,
    email=None,
    company_name="",
    lead_source="Website",
    assigned_to=None,
    priority="Medium",
    lead_description=None,
):
    lead = Lead.objects.create(
        company=company,
        full_name=full_name,
        phone_number=phone_number,
        email=email,
        company_name=company_name,
        lead_source=lead_source,
        assigned_to=assigned_to,
        priority=priority,
        lead_description=lead_description,
    )

    if lead.assigned_to and lead.assigned_to.user:
        try:
            notify_user(
                company=company,
                user=lead.assigned_to.user,
                notification_type="lead_assigned",
                title="New Lead Assigned",
                message=(
                    f"A new lead has been assigned to you.\n\n"
                    f"Lead: {lead.full_name}\n"
                    f"Phone: {lead.phone_number}\n"
                    f"Email: {lead.email or 'N/A'}\n"
                    f"Source: {lead.lead_source}\n"
                ),
            )
        except Exception:
            logger.exception(
                "Failed to notify staff for lead %s",
                lead.id
            )

    return lead