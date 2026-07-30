"""
Buyer blast — email deal alert + Stripe lock link to cash buyers.
"""

from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage


def _buyer_list() -> list[str]:
    raw = (os.getenv("BUYER_EMAILS") or "").strip()
    if not raw:
        return []
    return [e.strip() for e in raw.replace(";", ",").split(",") if e.strip()]


def email_configured() -> bool:
    user = (os.getenv("EMAIL_USER") or "").strip()
    password = (os.getenv("EMAIL_PASS") or "").strip()
    placeholders = {
        "",
        "your_gmail_app_password",
        "xxxx_gmail_app_password_xxxx",
        "you@gmail.com",
    }
    if user in placeholders or password in placeholders:
        return False
    return bool(user and password and _buyer_list())


def alert_buyers(
    address: str,
    arv: float,
    mao: float,
    fee: float,
    payment_link: str,
    flood_risk: bool = False,
) -> tuple[bool, str]:
    """
    Email Deal Alert to BUYER_EMAILS list.
    Uses Gmail SMTP + App Password (EMAIL_USER / EMAIL_PASS).
    """
    buyers = _buyer_list()
    user = (os.getenv("EMAIL_USER") or "").strip()
    password = (os.getenv("EMAIL_PASS") or "").strip()
    from_addr = (os.getenv("EMAIL_FROM") or user).strip()

    if not buyers:
        return False, "No BUYER_EMAILS in secrets/.env"
    if not user or not password:
        return False, "Missing EMAIL_USER / EMAIL_PASS"

    flood_line = ""
    if flood_risk:
        flood_line = (
            "\n*** FLOOD INSURANCE REQUIRED ***\n"
            "High Risk Flood Zone (AE). MAO already shaved $15,000 for flood risk. "
            "Verify NFIP/private premiums before locking.\n"
        )

    body = (
        f"NEW 33615 / TAMPA DEAL INBOUND\n\n"
        f"Address: {address}\n"
        f"ARV: ${arv:,.2f}\n"
        f"Price (MAO): ${mao:,.2f}\n"
        f"Assignment Fee: ${fee:,.2f}\n"
        f"{flood_line}\n"
        f"First-come, first-served.\n"
        f"Lock it with non-refundable EMD:\n{payment_link}\n"
    )

    msg = EmailMessage()
    msg.set_content(body)
    msg["Subject"] = f"HOT DEAL: {address}"
    msg["From"] = from_addr
    msg["To"] = ", ".join(buyers)

    host = (os.getenv("SMTP_HOST") or "smtp.gmail.com").strip()
    port = int(os.getenv("SMTP_PORT") or "465")

    try:
        with smtplib.SMTP_SSL(host, port) as smtp:
            smtp.login(user, password)
            smtp.send_message(msg)
        return True, f"Blasted to {len(buyers)} buyer(s)."
    except Exception as exc:
        return False, f"Email failed: {exc}"
