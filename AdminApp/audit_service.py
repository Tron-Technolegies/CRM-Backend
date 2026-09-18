from datetime import date, datetime
from decimal import Decimal
import logging
import uuid
from django.contrib.contenttypes.models import ContentType
from django.db import models

from AdminApp.models import (
    Accounts,
    AuditLog,
    Call,
    Customer,
    Deal,
    Invoice,
    Lead,
    Meeting,
    Product,
    PurchaseOrder,
    Quotes,
    SalesOrder,
    Service,
    Staff,
    Task,
    Vendor,
)

logger = logging.getLogger(__name__)

SENSITIVE_FIELDS = {
    "password",
    "access_token",
    "refresh_token",
    "access_token_encrypted",
    "refresh_token_encrypted",
    "invitation_token",
    "secret",
    "api_key",
    "auth_token",
}

IGNORED_FIELDS = {
    "created_at",
    "updated_at",
    "id",
    "pk",
}

MODEL_MAP = {
    "lead": Lead,
    "leads": Lead,
    "customer": Customer,
    "customers": Customer,
    "deal": Deal,
    "deals": Deal,
    "account": Accounts,
    "accounts": Accounts,
    "quote": Quotes,
    "quotes": Quotes,
    "salesorder": SalesOrder,
    "sales_order": SalesOrder,
    "salesorders": SalesOrder,
    "invoice": Invoice,
    "invoices": Invoice,
    "task": Task,
    "tasks": Task,
    "meeting": Meeting,
    "meetings": Meeting,
    "call": Call,
    "calls": Call,
    "product": Product,
    "products": Product,
    "service": Service,
    "services": Service,
    "vendor": Vendor,
    "vendors": Vendor,
    "purchaseorder": PurchaseOrder,
    "purchase_order": PurchaseOrder,
    "purchaseorders": PurchaseOrder,
    "staff": Staff,
}


def _serialize_val(val):
    """Safely serialize model field values into JSON-compatible primitives."""
    if val is None:
        return None
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, uuid.UUID):
        return str(val)
    if isinstance(val, models.Model):
        return getattr(val, "full_name", None) or getattr(val, "name", None) or str(val)
    return val


def get_authenticated_staff(request):
    """
    Extract the authenticated Staff instance from the request context.
    Never accepts or trusts staff_id / user_id from frontend input.
    """
    if not request:
        return None

    staff = getattr(request, "staff", None)
    if staff:
        return staff

    user = getattr(request, "user", None)
    if user and hasattr(user, "staff") and user.staff:
        return user.staff

    if user and getattr(user, "email", None):
        return Staff.objects.filter(email__iexact=user.email).first()

    return None


def snapshot_instance(instance):
    """
    Capture a dictionary snapshot of field values of an instance before updating.
    Excludes sensitive and system timestamp fields.
    """
    if not instance:
        return {}

    snapshot = {}
    for field in instance._meta.fields:
        field_name = field.name
        if field_name in SENSITIVE_FIELDS or field_name in IGNORED_FIELDS:
            continue

        if field.is_relation and field.many_to_one:
            fk_id = getattr(instance, field.attname, None)
            snapshot[field_name] = fk_id
        else:
            val = getattr(instance, field_name, None)
            snapshot[field_name] = _serialize_val(val)

    return snapshot


def calculate_field_changes(old_snapshot, new_instance):
    """
    Compare previous snapshot dict against current field values of updated instance.
    Returns a dict of changed fields: {"field_name": {"old": ..., "new": ...}}
    """
    if not old_snapshot or not new_instance:
        return {}

    changes = {}
    for field in new_instance._meta.fields:
        field_name = field.name
        if field_name in SENSITIVE_FIELDS or field_name in IGNORED_FIELDS:
            continue

        if field.is_relation and field.many_to_one:
            new_fk_id = getattr(new_instance, field.attname, None)
            old_fk_id = old_snapshot.get(field_name)
            if old_fk_id != new_fk_id:
                changes[field_name] = {
                    "old": old_fk_id,
                    "new": new_fk_id,
                }
        else:
            new_val = _serialize_val(getattr(new_instance, field_name, None))
            old_val = old_snapshot.get(field_name)
            if old_val != new_val:
                changes[field_name] = {
                    "old": old_val,
                    "new": new_val,
                }

    return changes


def log_audit(request, instance, action, changes=None, object_repr=None, staff=None, company=None):
    """
    Create a generic AuditLog record associated with company and authenticated staff.
    """
    try:
        # Resolve company
        company_obj = (
            company
            or getattr(request, "company", None)
            or getattr(instance, "company", None)
        )

        if not company_obj and hasattr(instance, "staff") and getattr(instance, "staff"):
            company_obj = instance.staff.company

        if not company_obj:
            logger.warning(f"Audit log skipped for {instance}: company could not be resolved.")
            return None

        # Resolve authenticated staff actor
        staff_obj = staff or get_authenticated_staff(request)

        # Content type & object ID
        content_type = ContentType.objects.get_for_model(instance.__class__)
        object_id = instance.pk

        # Object representation
        repr_str = object_repr or str(instance)
        if len(repr_str) > 255:
            repr_str = repr_str[:252] + "..."

        audit_entry = AuditLog.objects.create(
            company=company_obj,
            staff=staff_obj,
            action=action,
            content_type=content_type,
            object_id=object_id,
            object_repr=repr_str,
            changes=changes or {},
        )
        return audit_entry

    except Exception as e:
        logger.exception("Failed to create AuditLog entry for %s: %s", instance, e)
        return None


def get_audit_summary_for_object(company, model_or_instance, object_id=None):
    """
    Retrieve audit history for a specific record in a company.
    Returns:
    {
        "lastEditedBy": { "id": int, "name": str } | None,
        "lastEditedAt": ISO string | None,
        "editHistory": [
            {
                "id": int,
                "action": str,
                "editedBy": { "id": int, "name": str } | None,
                "editedAt": ISO string,
                "changes": dict,
                "objectRepr": str
            }, ...
        ]
    }
    """
    if object_id is None:
        model_class = model_or_instance.__class__
        obj_id = model_or_instance.pk
    elif isinstance(model_or_instance, type) and issubclass(model_or_instance, models.Model):
        model_class = model_or_instance
        obj_id = object_id
    elif isinstance(model_or_instance, str):
        model_class = MODEL_MAP.get(model_or_instance.lower())
        if not model_class:
            return {"lastEditedBy": None, "lastEditedAt": None, "editHistory": []}
        obj_id = object_id
    else:
        model_class = model_or_instance.__class__
        obj_id = object_id

    content_type = ContentType.objects.get_for_model(model_class)

    logs = AuditLog.objects.filter(
        company=company,
        content_type=content_type,
        object_id=obj_id,
    ).select_related("staff").order_by("-created_at")

    history = []
    for log in logs:
        staff_data = None
        if log.staff:
            staff_data = {
                "id": log.staff.id,
                "name": log.staff.full_name,
            }

        history.append({
            "id": log.id,
            "action": log.action,
            "editedBy": staff_data,
            "editedAt": log.created_at.isoformat(),
            "changes": log.changes,
            "objectRepr": log.object_repr,
        })

    # Find the latest update event for lastEditedBy / lastEditedAt;
    # if never updated, fall back to the first log event (e.g. created/converted).
    last_edit = logs.filter(action__in=["updated", "converted"]).first() or logs.first()

    last_edited_by = None
    last_edited_at = None

    if last_edit:
        if last_edit.staff:
            last_edited_by = {
                "id": last_edit.staff.id,
                "name": last_edit.staff.full_name,
            }
        last_edited_at = last_edit.created_at.isoformat()

    return {
        "lastEditedBy": last_edited_by,
        "lastEditedAt": last_edited_at,
        "editHistory": history,
    }
