import asyncio
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.domain.notification import VisitNotification


class SMTPSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: SecretStr | None = None
    smtp_use_tls: bool = True
    emails_from_email: str | None = None


class SMTPEmailSender:
    def __init__(self, settings: SMTPSettings) -> None:
        self._settings = settings

    async def send_visit_created(self, notification: VisitNotification) -> None:
        settings = self._settings
        if not settings.smtp_host or not settings.emails_from_email:
            raise RuntimeError("SMTP no está configurado")
        await asyncio.to_thread(self._send, notification)

    def _send(self, notification: VisitNotification) -> None:
        settings = self._settings
        message = EmailMessage()
        message["From"] = settings.emails_from_email
        message["To"] = notification.recipient_email
        message["Subject"] = "Nueva visita pastoral programada"
        scheduled_at = notification.scheduled_at
        if scheduled_at.tzinfo is not None:
            scheduled_at = scheduled_at.astimezone(ZoneInfo("America/Bogota"))
        message.set_content(
            "Se programó una visita pastoral.\n\n"
            f"Hermano: {notification.brother_name}\n"
            f"Tipo: {notification.visit_type.value}\n"
            f"Fecha: {scheduled_at.isoformat()}\n"
            f"Duración: {notification.duration_minutes} minutos\n"
            f"Ubicación: {notification.location}\n"
        )

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as client:
            client.ehlo()
            if settings.smtp_use_tls:
                client.starttls(context=ssl.create_default_context())
                client.ehlo()
            if settings.smtp_user and settings.smtp_password:
                client.login(settings.smtp_user, settings.smtp_password.get_secret_value())
            client.send_message(message)