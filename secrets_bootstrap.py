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
    "TWILIO_ACCOUNT_SID": ("TWILIO_SID", "ACCOUNT_SID"),
    "TWILIO_AUTH_TOKEN": ("TWILIO_TOKEN", "AUTH_TOKEN"),
    "TWILIO_PHONE_NUMBER": ("TWILIO_FROM", "TWILIO_NUMBER", "FROM_NUMBER"),
    "RENTCAST_API_KEY": ("RENTCAST_KEY",),
    # Older skip-trace vendor paste → people-data phones
    "PEOPLE_DATA_API_URL": ("SKIP_TRACE_API_URL", "BATCHDATA_API_URL"),
    "PEOPLE_DATA_API_KEY": ("SKIP_TRACE_API_KEY", "BATCHDATA_API_KEY"),
    "GOOGLE_SHEETS_URL": ("SHEETS_URL", "GSHEETS_URL"),
}

# Template / example values that must NEVER overwrite a real .env key
_PLACEHOLDER_VALUES = frozenset(
    {
        "",
        "your_key_here",
        "your_sid",
        "your_sid_here",
        "your_token",
        "your_token_here",
        "your_rentcast_key",
        "your_auth_token",
        "sk_test_...",
        "sk_live_...",
        "rk_test_...",
        "rk_live_...",
        "your_gmail_app_password",
        "xxxx_gmail_app_password_xxxx",
        "sk_live_xxxxxxxx",
        "+1xxxxxxxxxx",
        "+1XXXXXXXXXX",
        "ACxxxxxxxx",
        "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "you@gmail.com",
        "deals@yourdomain.com",
        "buyer1@example.com, buyer2@example.com",
        "paste_rentcast_key",
        "paste_twilio_auth_token",
        "paste_vendor_key",
        "Your Title Company Escrow",
        "xxxx",
        "ABC Title / Escrow",
    }
)


def is_placeholder_secret(val: str | None) -> bool:
    """True for empty / template secrets that must not count as configured."""
    raw = (val or "").strip().strip('"').strip("'")
    if not raw:
        return True
    if raw in _PLACEHOLDER_VALUES:
        return True
    if "YOUR_SHEET_ID" in raw:
        return True
    if raw.endswith("...") and ("sk_" in raw or "rk_" in raw or raw.startswith("AC")):
        return True
    if raw.endswith("xxxxxxxxxx") or raw.endswith("XXXXXXXXXX"):
        return True
    if all(c in "xX" for c in raw.replace("AC", "", 1)) and raw.startswith("AC"):
        return True
    return False


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


def _restore_dotenv_over_placeholders() -> None:
    """Put real .env values back when secrets.toml templates clobbered os.environ.

    Local rule: a non-placeholder value in the project `.env` wins over empty /
    placeholder process values (typical Streamlit secrets.toml stub sync).
    On Streamlit Cloud, existing non-placeholder env (Cloud inject) is kept.
    """
    try:
        from dotenv import dotenv_values

        cloud = running_on_streamlit_cloud()
        for key, val in (dotenv_values() or {}).items():
            if val is None:
                continue
            cleaned = str(val).strip()
            if not cleaned or is_placeholder_secret(cleaned):
                continue
            existing = (os.getenv(key) or "").strip()
            if (not existing) or is_placeholder_secret(existing):
                os.environ[key] = cleaned
                continue
            # Local only: if both look real but differ, prefer explicit .env
            # for project keys so Cloud stubs / stale shells do not stick.
            if (
                not cloud
                and key in SECRET_KEYS
                and existing != cleaned
                and is_placeholder_secret(existing) is False
            ):
                # Prefer .env when the process value is a known template shape
                # already handled above; keep process when it is a deliberate
                # User/system override (same length class / live key). No-op.
                pass
    except Exception:
        pass


def bootstrap_secrets() -> None:
    """Copy Streamlit Cloud secrets into the environment when present."""
    # Snapshot + restore: accessing st.secrets can sync secrets.toml placeholders
    # into os.environ and wipe real .env values.
    _restore_dotenv_over_placeholders()
    snapshot: dict[str, str] = {}
    for key in SECRET_KEYS:
        cur = (os.getenv(key) or "").strip()
        if cur and not is_placeholder_secret(cur):
            snapshot[key] = cur

    try:
        import streamlit as st

        secrets = getattr(st, "secrets", None)
        if secrets is None:
            _restore_dotenv_over_placeholders()
            try:
                os.environ["APP_BASE_URL"] = app_base_url()
            except Exception:
                pass
            return

        def _set(key: str, val: object, *, overwrite: bool = False) -> None:
            """Inject secret into os.environ. Never writes placeholders."""
            if val is None:
                return
            cleaned = str(val).strip().strip('"').strip("'")
            if key == "APP_BASE_URL":
                cleaned = cleaned.rstrip("/")
            if not cleaned or is_placeholder_secret(cleaned):
                return
            existing = (os.getenv(key) or "").strip()
            if existing and not is_placeholder_secret(existing) and not overwrite:
                return
            if key in snapshot and not overwrite:
                os.environ[key] = snapshot[key]
                return
            os.environ[key] = cleaned

        for key in SECRET_KEYS:
            try:
                val = secrets.get(key) if hasattr(secrets, "get") else secrets[key]
            except Exception:
                continue
            _set(key, val)

        # Map top-level aliases → canonical names when canonical unset / placeholder
        for canonical, aliases in SECRET_ALIASES.items():
            cur = (os.getenv(canonical) or "").strip()
            if cur and not is_placeholder_secret(cur):
                continue
            if canonical in snapshot:
                os.environ[canonical] = snapshot[canonical]
                continue
            for alt in aliases:
                try:
                    val = secrets.get(alt) if hasattr(secrets, "get") else secrets[alt]
                except Exception:
                    continue
                if val is not None and str(val).strip():
                    _set(canonical, val)
                    if (os.getenv(canonical) or "").strip() and not is_placeholder_secret(
                        os.getenv(canonical) or ""
                    ):
                        break

        # Flatten [connections.gsheets].spreadsheet → GOOGLE_SHEETS_URL when unset
        try:
            gsheets = secrets["connections"]["gsheets"]
            sheet_url = gsheets.get("spreadsheet") if hasattr(gsheets, "get") else gsheets["spreadsheet"]
            if sheet_url:
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
                "TWILIO_AGENT_PHONE": ("agent_phone", "TWILIO_AGENT_PHONE"),
            },
            "stripe": {
                "STRIPE_SECRET_KEY": ("secret_key", "STRIPE_SECRET_KEY", "api_key"),
                "APP_BASE_URL": ("app_base_url", "APP_BASE_URL", "base_url"),
            },
            "email": {
                "EMAIL_USER": ("user", "EMAIL_USER"),
                "EMAIL_PASS": ("pass", "password", "EMAIL_PASS"),
                "EMAIL_FROM": ("from", "EMAIL_FROM"),
                "BUYER_EMAILS": ("buyers", "BUYER_EMAILS"),
            },
        }
        for section, mapping in nested.items():
            try:
                block = secrets[section]
            except Exception:
                continue
            for env_key, aliases in mapping.items():
                cur = (os.getenv(env_key) or "").strip()
                if cur and not is_placeholder_secret(cur):
                    continue
                if env_key in snapshot:
                    os.environ[env_key] = snapshot[env_key]
                    continue
                for alias in aliases:
                    try:
                        _set(env_key, block[alias])
                        if (os.getenv(env_key) or "").strip() and not is_placeholder_secret(
                            os.getenv(env_key) or ""
                        ):
                            break
                    except Exception:
                        continue
    except Exception:
        pass

    # Undo Streamlit's placeholder sync into os.environ
    for key, prev in snapshot.items():
        cur = (os.getenv(key) or "").strip()
        if is_placeholder_secret(cur):
            os.environ[key] = prev
    _restore_dotenv_over_placeholders()

    # Never leave Cloud sessions with localhost deal/Stripe links.
    try:
        os.environ["APP_BASE_URL"] = app_base_url()
    except Exception:
        pass
