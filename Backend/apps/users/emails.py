from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode


def send_password_reset_email(user):
    """Email a one-use link to choose a new password, valid for PASSWORD_RESET_TIMEOUT seconds."""
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    reset_url = f"{settings.APP_URL}/reset-password?uid={uid}&token={token}"
    text = (
        f"Reset your password\n\n"
        f"Someone asked to reset the password for the Unfurl account {user.email}.\n\n"
        f"Choose a new password: {reset_url}\n\n"
        f"Expires in 15 minutes. If this wasn't you, you can ignore this email and your password won't change.\n"
    )
    html = render_to_string("users/emails/password_reset.html", {"email": user.email, "reset_url": reset_url})
    message = EmailMultiAlternatives("Reset your Unfurl password", text, to=[user.email])
    message.attach_alternative(html, "text/html")
    message.send()
