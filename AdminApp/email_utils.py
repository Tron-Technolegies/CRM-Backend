import os
import resend

resend.api_key = os.getenv("RESEND_API_KEY")


def send_invite_email(to_email, subject, html_content, from_email=None):
    """
    Sends an email via Resend's HTTP API instead of SMTP.
    Works on Render because it uses HTTPS (443), not SMTP ports
    (587/465/25) that Render blocks outbound.
    """
    params = {
        "from": from_email or "onboarding@resend.dev",  # swap once you verify your own domain in Resend
        "to": [to_email],
        "subject": subject,
        "html": html_content,
    }
    return resend.Emails.send(params)