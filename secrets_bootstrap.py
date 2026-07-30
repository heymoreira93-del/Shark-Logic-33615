"""
Load secrets into os.environ for local (.env) and Streamlit Cloud (st.secrets).
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

SECRET_KEYS = (
    "RENTCAST_API_KEY",
    "GOOGLE_MAPS_API_KEY",
    "TWILIO_ACCOUNT_SID",
    "TWILIO_AUTH_TOKEN",
    "TWILIO_PHONE_NUMBER",
    "NOTIFY_PHONE",
    "APP_BASE_URL",
    "SKIP_TRACE_API_URL",
    "SKIP_TRACE_API_KEY",
    "STRIPE_SECRET_KEY",
    "STRIPE_EMD_CENTS",
    "EMAIL_USER",
    "EMAIL_PASS",
    "EMAIL_FROM",
    "BUYER_EMAILS",
    "SMTP_HOST",
    "SMTP_PORT",
    "GOOGLE_SHEETS_URL",
    "WIRE_BANK",
    "WIRE_ACCOUNT",
    "WIRE_ROUTING",
    "TITLE_COMPANY_NAME",
)


def bootstrap_secrets() -> None:
    """Copy Streamlit Cloud secrets into the environment when present."""
    try:
        import streamlit as st

        secrets = getattr(st, "secrets", None)
        if secrets is None:
            return
        for key in SECRET_KEYS:
            try:
                val = secrets.get(key) if hasattr(secrets, "get") else secrets[key]
            except Exception:
                continue
            if val is not None and str(val).strip():
                os.environ[key] = str(val).strip()
    except Exception:
        pass
