"""SMTP email delivery for transactional user emails."""

import asyncio
import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr
from typing import Any, Optional
from urllib.parse import quote

from app.core.config import settings


logger = logging.getLogger(__name__)


class EmailService:
    """Simple SMTP-backed email sender."""

    def __init__(self, config: Optional[dict[str, Any]] = None):
        source = config or {}
        use_ssl = bool(source.get("use_ssl", settings.SMTP_USE_SSL))
        self.config = {
            "host": str(source.get("host") or settings.SMTP_HOST or "").strip(),
            "port": int(source.get("port") or settings.SMTP_PORT or 587),
            "username": str(source.get("username") or settings.SMTP_USERNAME or "").strip(),
            "password": str(source.get("password") or settings.SMTP_PASSWORD or ""),
            "from_email": str(source.get("from_email") or settings.SMTP_FROM_EMAIL or "").strip(),
            "from_name": str(source.get("from_name") or settings.SMTP_FROM_NAME or "VQuest").strip() or "VQuest",
            "use_tls": bool(source.get("use_tls", settings.SMTP_USE_TLS)) and not use_ssl,
            "use_ssl": use_ssl,
            "timeout_seconds": int(source.get("timeout_seconds") or settings.SMTP_TIMEOUT_SECONDS or 20),
            "password_reset_url_template": str(
                source.get("password_reset_url_template") or settings.PASSWORD_RESET_URL_TEMPLATE or ""
            ).strip(),
        }

    @property
    def is_configured(self) -> bool:
        return bool(
            self.config["host"]
            and self.config["from_email"]
            and self.config["password_reset_url_template"]
        )

    def build_password_reset_url(self, token: str) -> str:
        """Build the reset URL used in password reset emails."""
        template = self.config["password_reset_url_template"]
        if not template:
            raise ValueError("PASSWORD_RESET_URL_TEMPLATE is not configured")

        encoded_token = quote(token, safe="")
        if "{token}" in template:
            return template.format(token=encoded_token)

        separator = "&" if "?" in template else "?"
        return f"{template}{separator}token={encoded_token}"

    async def send_password_reset_email(
        self,
        *,
        to_email: str,
        token: str,
        recipient_name: Optional[str] = None,
    ) -> None:
        """Send a password reset email with a signed reset link."""
        if not self.is_configured:
            raise ValueError("SMTP password reset email is not configured")

        app_name = self.config["from_name"] or "VQuest"
        reset_url = self.build_password_reset_url(token)
        recipient_label = recipient_name.strip() if recipient_name else "there"
        expires_in = settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES
        subject = f"Reset your {app_name} password"
        text_body = (
            f"Hi {recipient_label},\n\n"
            f"We received a request to reset your {app_name} password.\n"
            f"Use the link below to choose a new password:\n\n"
            f"{reset_url}\n\n"
            f"This link expires in {expires_in} minutes. If you did not request this change, you can ignore this email.\n"
        )
        html_body = f"""
        <html>
          <body style=\"font-family: Arial, sans-serif; color: #111827; line-height: 1.6;\">
            <p>Hi {recipient_label},</p>
            <p>We received a request to reset your {app_name} password.</p>
            <p>
              <a href=\"{reset_url}\" style=\"display: inline-block; padding: 12px 18px; background: #0f766e; color: #ffffff; text-decoration: none; border-radius: 8px;\">
                Reset Password
              </a>
            </p>
            <p>If the button does not work, paste this link into your browser:</p>
            <p><a href=\"{reset_url}\">{reset_url}</a></p>
            <p>This link expires in {expires_in} minutes. If you did not request this change, you can ignore this email.</p>
          </body>
        </html>
        """.strip()

        await asyncio.to_thread(
            self._send_message,
            to_email,
            subject,
            text_body,
            html_body,
        )

    async def send_test_email(self, *, to_email: str) -> None:
        """Send a simple SMTP test email using the configured transport."""
        if not self.config["host"] or not self.config["from_email"]:
            raise ValueError("SMTP host and from email are required")

        app_name = self.config["from_name"] or "VQuest"
        subject = f"{app_name} SMTP Test"
        text_body = (
            f"This is a test email from {app_name}.\n\n"
            f"Your SMTP configuration is working correctly."
        )
        html_body = f"""
        <html>
          <body style=\"font-family: Arial, sans-serif; color: #111827; line-height: 1.6;\">
            <p>This is a test email from <strong>{app_name}</strong>.</p>
            <p>Your SMTP configuration is working correctly.</p>
          </body>
        </html>
        """.strip()

        await asyncio.to_thread(self._send_message, to_email, subject, text_body, html_body)

    def _send_message(
        self,
        to_email: str,
        subject: str,
        text_body: str,
        html_body: str,
    ) -> None:
        """Send an email through the configured SMTP server."""
        message = EmailMessage()
        from_name = self.config["from_name"] or self.config["from_email"]
        message["From"] = formataddr((from_name, self.config["from_email"]))
        message["To"] = to_email
        message["Subject"] = subject
        message.set_content(text_body)
        message.add_alternative(html_body, subtype="html")

        context = ssl.create_default_context()
        username = self.config["username"]
        password = self.config["password"]

        if self.config["use_ssl"]:
            with smtplib.SMTP_SSL(
                self.config["host"],
                self.config["port"],
                timeout=self.config["timeout_seconds"],
                context=context,
            ) as smtp:
                if username and password:
                    smtp.login(username, password)
                smtp.send_message(message)
            logger.info("Sent transactional email to %s", to_email)
            return

        with smtplib.SMTP(
            self.config["host"],
            self.config["port"],
            timeout=self.config["timeout_seconds"],
        ) as smtp:
            smtp.ehlo()
            if self.config["use_tls"]:
                smtp.starttls(context=context)
                smtp.ehlo()
            if username and password:
                smtp.login(username, password)
            smtp.send_message(message)
        logger.info("Sent transactional email to %s", to_email)