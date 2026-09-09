"""
AdminApp/email_service.py

Reusable Gmail API email service for company-specific OAuth 2.0 integrations.
Each company can connect its own Gmail account through Google OAuth.
Emails are sent via the Gmail API on behalf of the company connected account.

SECURITY:
- Access/refresh tokens are never logged or returned to clients.
- Token decryption happens only here, server-side.
- Each company can only access its own EmailIntegration.
"""

import base64
import logging
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from django.conf import settings

logger = logging.getLogger(__name__)


def _get_credentials(integration):
    """
    Build a google.oauth2.credentials.Credentials object from the stored
    EmailIntegration record. Refreshes the access token if it is expired
    or within 5 minutes of expiry, and persists the new tokens to the DB.

    Returns the Credentials object, or raises an exception if refresh fails.
    """
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request as GoogleRequest
    from google.auth.exceptions import RefreshError

    raw_access = integration.access_token     # decrypted via property
    raw_refresh = integration.refresh_token   # decrypted via property

    expiry = integration.token_expiry  # aware datetime or None

    creds = Credentials(
        token=raw_access,
        refresh_token=raw_refresh,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        scopes=["https://www.googleapis.com/auth/gmail.send"],
    )

    # Attach the expiry so google-auth knows whether to refresh
    if expiry:
        creds.expiry = expiry

    # Refresh if expired or within 5-minute window
    now = datetime.now(tz=timezone.utc)
    needs_refresh = (
        not raw_access
        or not expiry
        or expiry <= now + timedelta(minutes=5)
    )

    if needs_refresh:
        if not raw_refresh:
            raise ValueError(
                "Gmail access token is expired and no refresh token is available. "
                "The company must reconnect their Gmail account."
            )
        try:
            creds.refresh(GoogleRequest())
        except RefreshError as exc:
            logger.warning(
                "Gmail token refresh failed for company_id=%s: %s",
                integration.company_id,
                exc,
            )
            # Mark as disconnected so the UI can prompt reconnection
            integration.is_connected = False
            integration.save(update_fields=["is_connected", "updated_at"])
            raise ValueError(
                "Gmail credentials have been revoked or expired. "
                "Please reconnect the Gmail account in Settings."
            ) from exc

        # Persist updated tokens (encrypted via property setters)
        integration.access_token = creds.token
        if creds.refresh_token:
            integration.refresh_token = creds.refresh_token
        integration.token_expiry = creds.expiry
        integration.save(update_fields=[
            "access_token_encrypted",
            "refresh_token_encrypted",
            "token_expiry",
            "updated_at",
        ])
        logger.info("Gmail token refreshed for company_id=%s", integration.company_id)

    return creds


def get_company_email_integration(company):
    """
    Return the active EmailIntegration for `company`, or None if not connected.
    Company isolation enforced: only the matching company record is returned.
    """
    from AdminApp.models import EmailIntegration
    try:
        integration = EmailIntegration.objects.select_related("company").get(
            company=company,
            is_connected=True,
        )
        return integration
    except EmailIntegration.DoesNotExist:
        return None


def send_company_email(
    company,
    to,
    subject,
    body="",
    html_body=None,
    cc=None,
    bcc=None,
):
    """
    Send an email on behalf of `company` using its connected Gmail account.

    Args:
        company:   Company model instance (must have an active EmailIntegration).
        to:        str or list[str] - recipient email address(es).
        subject:   str - email subject line.
        body:      str - plain-text body (optional if html_body provided).
        html_body: str - HTML body (optional).
        cc:        str or list[str] - CC recipients (optional).
        bcc:       str or list[str] - BCC recipients (optional).

    Returns:
        dict: {"success": True,  "message_id": "<gmail message id>"}
           or {"success": False, "error": "<reason>"}

    SECURITY: tokens are never logged or included in the returned dict.
    """
    from googleapiclient.discovery import build as google_build
    from googleapiclient.errors import HttpError

    # 1. Retrieve the integration (company-isolated)
    integration = get_company_email_integration(company)
    if not integration:
        return {
            "success": False,
            "error": (
                "No email account is connected for this company. "
                "Please connect a Gmail account in Settings > Email Integration."
            ),
        }

    # 2. Obtain (and if needed refresh) credentials
    try:
        creds = _get_credentials(integration)
    except ValueError as exc:
        return {"success": False, "error": str(exc)}

    # 3. Build MIME message
    msg = EmailMessage()
    msg["From"] = integration.email
    msg["To"] = ", ".join(to) if isinstance(to, list) else to
    msg["Subject"] = subject
    if cc:
        msg["Cc"] = ", ".join(cc) if isinstance(cc, list) else cc
    if bcc:
        msg["Bcc"] = ", ".join(bcc) if isinstance(bcc, list) else bcc

    if html_body:
        msg.set_content(body or "")
        msg.add_alternative(html_body, subtype="html")
    else:
        msg.set_content(body)

    # 4. Encode and send via Gmail API
    raw_bytes = base64.urlsafe_b64encode(msg.as_bytes()).decode()

    try:
        service = google_build("gmail", "v1", credentials=creds, cache_discovery=False)
        result = service.users().messages().send(
            userId="me",
            body={"raw": raw_bytes},
        ).execute()
    except HttpError as exc:
        status_code = exc.resp.status
        logger.error(
            "Gmail API HttpError for company_id=%s: status=%s",
            company.id,
            status_code,
        )
        if status_code == 401:
            integration.is_connected = False
            integration.save(update_fields=["is_connected", "updated_at"])
            return {
                "success": False,
                "error": "Gmail credentials are no longer valid. Please reconnect your Gmail account.",
            }
        if status_code == 403:
            return {
                "success": False,
                "error": "Gmail API access denied. Ensure the Gmail API is enabled in Google Cloud Console.",
            }
        return {"success": False, "error": f"Gmail API error (HTTP {status_code})."}
    except Exception:
        logger.exception("Unexpected error sending Gmail for company_id=%s", company.id)
        return {"success": False, "error": "An unexpected error occurred while sending the email."}

    message_id = result.get("id", "")
    logger.info(
        "Email sent via Gmail API. company_id=%s from=%s to=%s message_id=%s",
        company.id,
        integration.email,
        to,
        message_id,
    )
    return {"success": True, "message_id": message_id}
