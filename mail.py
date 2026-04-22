"""Send portfolio contact notifications via Gmail SMTP (STARTTLS, port 587)."""

from email.message import EmailMessage

import aiosmtplib

from db import get_settings


async def send_contact_email(*, sender_name: str, sender_email: str, body_text: str) -> None:
    settings = get_settings()
    msg = EmailMessage()
    msg["Subject"] = f"Portfolio Contact: {sender_name}"
    msg["From"] = settings.GMAIL_USER
    msg["To"] = settings.ADMIN_EMAIL
    msg["Reply-To"] = sender_email
    msg.set_content(
        f"From: {sender_name} <{sender_email}>\n\n{body_text}",
        charset="utf-8",
    )
    await aiosmtplib.send(
        msg,
        hostname="smtp.gmail.com",
        port=587,
        start_tls=True,
        username=settings.GMAIL_USER,
        password=settings.GMAIL_APP_PASSWORD,
    )


async def send_reply_email(
    *,
    to_email: str,
    subject: str,
    body: str,
    visitor_name: str,
    original_message: str,
) -> None:
    """Send admin reply to a contact-form visitor (visitor's address in To)."""
    settings = get_settings()
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.GMAIL_USER
    msg["To"] = to_email
    msg["Reply-To"] = str(settings.ADMIN_EMAIL)
    text = (
        f"Hi {visitor_name},\n\n{body.strip()}\n\n"
        f"---\nYour original message:\n{original_message.strip()}\n"
    )
    msg.set_content(text, charset="utf-8")
    await aiosmtplib.send(
        msg,
        hostname="smtp.gmail.com",
        port=587,
        start_tls=True,
        username=settings.GMAIL_USER,
        password=settings.GMAIL_APP_PASSWORD,
    )
