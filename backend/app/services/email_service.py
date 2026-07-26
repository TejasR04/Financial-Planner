"""Small SMTP adapter for account emails.

Local development intentionally logs reset links when SMTP is not configured,
so the password-reset flow remains testable without putting credentials in the
repository. Production deployments should configure SMTP_* variables.
"""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from urllib.parse import quote

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def send_password_reset_email(recipient: str, token: str) -> None:
    settings = get_settings()
    reset_url = f"{settings.frontend_url.rstrip('/')}/reset-password?token={quote(token)}"

    if not settings.smtp_host:
        if settings.environment == "development":
            logger.warning("Password reset link for %s: %s", recipient, reset_url)
        else:
            logger.error("SMTP is not configured; password reset email was not sent")
        return

    message = EmailMessage()
    message["Subject"] = "Reset your Meridian password"
    message["From"] = settings.smtp_from_email or settings.smtp_username or "no-reply@meridian.local"
    message["To"] = recipient
    message.set_content(
        "We received a request to reset your Meridian password. "
        f"Use this link within {settings.password_reset_token_expire_minutes} minutes:\n\n"
        f"{reset_url}\n\n"
        "If you did not request this, you can safely ignore this email."
    )

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as client:
        if settings.smtp_use_tls:
            client.starttls()
        if settings.smtp_username and settings.smtp_password:
            client.login(settings.smtp_username, settings.smtp_password)
        client.send_message(message)
