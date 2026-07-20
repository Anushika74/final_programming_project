"""Notification adapters: email (SMTP) and desktop (notify-send).

Both are best-effort and fail safe: if a channel is not configured or fails, a
warning is logged and execution continues. No exceptions propagate to the alert
engine.
"""
from __future__ import annotations

import logging
import shutil
import smtplib
import subprocess
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger(__name__)


def send_email(subject: str, body: str) -> bool:
    """Send an email alert via SMTP. Returns True on success."""
    if not settings.SMTP_HOST or not settings.ALERT_EMAIL_TO:
        logger.debug("Email notifications disabled (SMTP not configured).")
        return False
    try:
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = settings.SMTP_FROM
        message["To"] = settings.ALERT_EMAIL_TO
        message.set_content(body)

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            server.starttls()
            if settings.SMTP_USER:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(message)
        logger.info("Sent alert email to %s", settings.ALERT_EMAIL_TO)
        return True
    except Exception as exc:  # noqa: BLE001 - notifications must never crash the app
        logger.warning("Failed to send alert email: %s", exc)
        return False


def send_desktop(title: str, body: str) -> bool:
    """Send a desktop notification using `notify-send` (Linux). Best-effort."""
    notify_bin = shutil.which("notify-send")
    if notify_bin is None:
        logger.debug("Desktop notifications unavailable (notify-send not found).")
        return False
    try:
        subprocess.run(
            [notify_bin, "-a", settings.APP_NAME, title, body],
            check=False,
            timeout=5,
        )
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to send desktop notification: %s", exc)
        return False


def dispatch(title: str, body: str) -> dict[str, bool]:
    """Send through all available channels, returning per-channel success."""
    return {
        "email": send_email(title, body),
        "desktop": send_desktop(title, body),
    }
