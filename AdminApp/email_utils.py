from django.core.mail import send_mail


def send_invite_email(to_email, subject, html_content, from_email=None):
    """
    Sends an email via SMTP, through the IPv4-forcing custom backend
    configured in settings.EMAIL_BACKEND.
    """
    send_mail(
        subject=subject,
        message="",              # plain-text fallback (optional)
        from_email=from_email,   # None falls back to settings.DEFAULT_FROM_EMAIL
        recipient_list=[to_email],
        html_message=html_content,
        fail_silently=False,
    )