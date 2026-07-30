"""
Load secrets into os.environ for local (.env) and Streamlit Cloud (st.secrets).
"""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv()

# Public production app — used when Cloud would otherwise emit localhost links.
PUBLIC_APP_BASE_URL = "https://realestateshark.streamlit.app"

SECRET_KEYS = (
    "RENTCAST_API_KEY",
    "GOOGLE_MAPS_API_KEY",
    "TWILIO_ACCOUNT_SID",
    "TWILIO_AUTH_TOKEN",
    "TWILIO_PHONE_NUMBER",
    "TWILIO_AGENT_PHONE",
    "TWILIO_VOICE_WEBHOOK",
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
    "PEOPLE_DATA_API_URL",
    "PEOPLE_DATA_API_KEY",
)

# Top-level alias → canonical env (Cloud paste typos)
SECRET_ALIASES: dict[str, tuple[str, ...]] = {
    "EMAIL_USER": ("GMAIL_USER", "SMTP_USER"),
    "EMAIL_PASS": ("EMAIL_PASSWORD", "GMAIL_APP_PASSWORD", "SMTP_PASS"),
    "BUYER_EMAILS": ("BUYER_EMAIL", "CASH_BUYER_EMAILS"),
    "STRIPE_SECRET_KEY": ("STRIPE_KEY", "STRIPE_API_KEY"),
    "APP_BASE_URL": ("BASE_URL", "STREAMLIT_APP_URL"),
}


def is_localhost_base_url(url: str | None) -> bool:
    """True when URL is empty or clearly a local-only host."""
    raw = (url or "").strip()
    if not raw:
        return True
    host = (urlparse(raw).hostname or "").lower()
    return host in {"localhost", "127.0.0.1", "0.0.0.0", "::1"} or host.endswith(".local")


def running_on_streamlit_cloud() -> bool:
    """Best-effort Streamlit Community Cloud detection."""
    if os.getenv("STREAMLIT_SHARING_MODE"):
        return True
    if (os.getenv("STREAMLIT_RUNTIME_ENV") or "").lower() == "cloud":
        return True
    host = (os.getenv("HOSTNAME") or os.getenv("SERVER_NAME") or "").lower()
    if "streamlit" in host:
        return True
    return Path("/mount/src").exists()


def app_base_url() -> str:
    """
    Base URL for Stripe returns, SMS, and email links (no trailing slash).
    Prefer APP_BASE_URL; on Streamlit Cloud never emit localhost.
    """
    raw = (os.getenv("APP_BASE_URL") or "").strip().rstrip("/")
    if raw and not is_localhost_base_url(raw):
        return raw
    if running_on_streamlit_cloud():
        return PUBLIC_APP_BASE_URL
    return raw or "http://localhost:8501"


def bootstrap_secrets() -> None:
    """Copy Streamlit Cloud secrets into the environment when present."""
    try:
        import streamlit as st

        secrets = getattr(st, "secrets", None)
        if secrets is None:
            return

        def _set(key: str, val: object) -> None:
            if val is not None and str(val).strip():
                cleaned = str(val).strip().strip('"').strip("'")
                if key == "APP_BASE_URL":
                    cleaned = cleaned.rstrip("/")
                os.environ[key] = cleaned

        for key in SECRET_KEYS:
            try:
                val = secrets.get(key) if hasattr(secrets, "get") else secrets[key]
            except Exception:
                continue
            _set(key, val)

        # Map top-level aliases → canonical names when canonical unset
        for canonical, aliases in SECRET_ALIASES.items():
            if os.getenv(canonical):
                continue
            for alt in aliases:
                try:
                    val = secrets.get(alt) if hasattr(secrets, "get") else secrets[alt]
                except Exception:
                    continue
                if val is not None and str(val).strip():
                    _set(canonical, val)
                    break

        # Flatten [connections.gsheets].spreadsheet → GOOGLE_SHEETS_URL when unset
        try:
            gsheets = secrets["connections"]["gsheets"]
            sheet_url = gsheets.get("spreadsheet") if hasattr(gsheets, "get") else gsheets["spreadsheet"]
            if sheet_url and not os.getenv("GOOGLE_SHEETS_URL"):
                _set("GOOGLE_SHEETS_URL", sheet_url)
        except Exception:
            pass

        # Nested [twilio] / [stripe] / [email] tables (common paste mistake)
        nested = {
            "twilio": {
                "TWILIO_ACCOUNT_SID": ("account_sid", "sid", "TWILIO_ACCOUNT_SID"),
                "TWILIO_AUTH_TOKEN": ("auth_token", "token", "TWILIO_AUTH_TOKEN"),
                "TWILIO_PHONE_NUMBER": (
                    "phone_number",
                    "from_number",
                    "phone",
                    "TWILIO_PHONE_NUMBER",
                ),
            },
            "stripe": {
                "STRIPE_SECRET_KEY": ("secret_key", "STRIPE_SECRET_KEY"),
            },
            "email": {
                "EMAIL_USER": ("user", "EMAIL_USER"),
                "EMAIL_PASS": ("pass", "password", "EMAIL_PASS"),
                "BUYER_EMAILS": ("buyers", "BUYER_EMAILS"),
            },
        }
        for section, mapping in nested.items():
            try:
                block = secrets[section]
            except Exception:
                continue
            for env_key, aliases in mapping.items():
                if os.getenv(env_key):
                    continue
                for alias in aliases:
                    try:
                        _set(env_key, block[alias])
                        if os.getenv(env_key):
                            break
                    except Exception:
                        continue
    except Exception:
        pass

    # Never leave Cloud sessions with localhost deal/Stripe links.
    try:
        os.environ["APP_BASE_URL"] = app_base_url()
    except Exception:
        pass
