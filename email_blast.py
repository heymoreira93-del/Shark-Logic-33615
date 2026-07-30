"""
Buyer blast — email deal alert + Stripe lock link to cash buyers.
"""

from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage

# Canonical env names + Cloud-secret aliases (must match systems_check / bootstrap)
_EMAIL_ALIASES: dict[str, tuple[str, ...]] = {
    "EMAIL_USER": ("EMAIL_USER", "GMAIL_USER", "SMTP_USER"),
    "EMAIL_PASS": ("EMAIL_PASS", "EMAIL_PASSWORD", "GMAIL_APP_PASSWORD", "SMTP_PASS"),
    "BUYER_EMAILS": ("BUYER_EMAILS", "BUYER_EMAIL", "CASH_BUYER_EMAILS"),
    "EMAIL_FROM": ("EMAIL_FROM",),
}

_PLACEHOLDERS = frozenset(
    {
        "",
        "your_gmail_app_password",
        "xxxx_gmail_app_password_xxxx",
        "you@gmail.com",
        "buyer1@example.com, buyer2@example.com",
    }
)


def _ensure_secrets() -> None:
    try:
        from secrets_bootstrap import bootstrap_secrets

        bootstrap_secrets()
    except Exception:
        pass


def _is_bad(val: str | None) -> bool:
    raw = (val or "").strip()
    if not raw or raw in _PLACEHOLDERS:
        return True
    try:
        from secrets_bootstrap import is_placeholder_secret

        if is_placeholder_secret(raw):
            return True
    except Exception:
        pass
    if "example.com" in raw and "@" in raw:
        return True
    return False


def _env(key: str) -> str:
    """Resolve EMAIL_* from os.environ, aliases, then st.secrets (incl. [email])."""
    _ensure_secrets()
    for alt in _EMAIL_ALIASES.get(key, (key,)):
        val = (os.getenv(alt) or "").strip()
        if val and not _is_bad(val):
            if alt != key:
                os.environ[key] = val
            return val
    try:
        import streamlit as st

        secrets = getattr(st, "secrets", None)
        if secrets is None:
            return ""
        for alt in _EMAIL_ALIASES.get(key, (key,)):
            try:
                raw = secrets.get(alt) if hasattr(secrets, "get") else secrets[alt]
            except Exception:
                continue
            if raw is not None and str(raw).strip():
                cleaned = str(raw).strip().strip('"').strip("'")
                if _is_bad(cleaned):
                    continue
                os.environ[key] = cleaned
                return cleaned
        try:
            block = secrets["email"]
        except Exception:
            return ""
        nested_map = {
            "EMAIL_USER": ("user", "EMAIL_USER"),
            "EMAIL_PASS": ("pass", "password", "EMAIL_PASS"),
            "BUYER_EMAILS": ("buyers", "BUYER_EMAILS"),
            "EMAIL_FROM": ("from", "EMAIL_FROM"),
        }
        for nested_key in nested_map.get(key, ()):
            try:
                raw = block[nested_key]
            except Exception:
                continue
            if raw is not None and str(raw).strip():
                cleaned = str(raw).strip().strip('"').strip("'")
                if _is_bad(cleaned):
                    continue
                os.environ[key] = cleaned
                return cleaned
    except Exception:
        pass
    return ""


def _buyer_list() -> list[str]:
    raw = _env("BUYER_EMAILS")
    if not raw:
        return []
    return [e.strip() for e in raw.replace(";", ",").split(",") if e.strip()]


def email_configured() -> bool:
    user = _env("EMAIL_USER")
    password = _env("EMAIL_PASS")
    if _is_bad(user) or _is_bad(password):
        return False
    buyers = _buyer_list()
    if not buyers:
        return False
    # Reject leftover example buyer list
    if all(_is_bad(b) or "example.com" in b for b in buyers):
        return False
    return bool(user and password and buyers)


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
    user = _env("EMAIL_USER")
    password = _env("EMAIL_PASS")
    from_addr = (_env("EMAIL_FROM") or user).strip()

    if not buyers:
        return False, "No BUYER_EMAILS in secrets/.env"
    if not user or not password or _is_bad(user) or _is_bad(password):
        return False, "Missing or placeholder EMAIL_USER / EMAIL_PASS"

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
