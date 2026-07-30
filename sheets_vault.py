"""
Google Sheets vault — persistent leads for 33615 War Room.
Falls back to local CRM SQLite if Sheets secrets are missing.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

import pandas as pd

SHEET_COLUMNS = [
    "timestamp",
    "name",
    "address",
    "zip_code",
    "status",
    "arv",
    "mao",
    "fee",
    "buyer_name",
    "risk",
    "last_contacted",
]


def sheets_configured() -> bool:
    url = (os.getenv("GOOGLE_SHEETS_URL") or "").strip()
    try:
        import streamlit as st

        secrets = getattr(st, "secrets", None)
        if secrets is not None:
            if "connections" in secrets and "gsheets" in secrets["connections"]:
                return True
            if secrets.get("GOOGLE_SHEETS_URL"):
                return True
            if "gcp_service_account" in secrets:
                return bool(url or secrets.get("GOOGLE_SHEETS_URL"))
    except Exception:
        pass
    return bool(url and os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE"))


def _empty_df() -> pd.DataFrame:
    return pd.DataFrame(columns=SHEET_COLUMNS)


def read_leads() -> pd.DataFrame:
    """Read Leads worksheet (or SQLite fallback)."""
    try:
        import streamlit as st
        from streamlit_gsheets import GSheetsConnection

        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(worksheet="Leads", ttl=0)
        if df is None or df.empty:
            return _empty_df()
        return df
    except Exception as exc:
        print(f"Sheets read fallback: {exc}")
        try:
            from crm import get_leads

            return get_leads()
        except Exception:
            return _empty_df()


def log_to_sheets(new_row: dict[str, Any]) -> tuple[bool, str]:
    """
    Append a deal row to Google Sheets 'Leads' tab.
    Returns (ok, message).
    """
    row = {c: new_row.get(c, "") for c in SHEET_COLUMNS}
    if not row.get("timestamp"):
        row["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if not row.get("last_contacted"):
        row["last_contacted"] = row["timestamp"]

    # Always mirror to local CRM so follow-ups still work offline
    crm_ok = False
    try:
        from crm import add_lead

        add_lead(
            name=str(row.get("name") or "Seller"),
            address=str(row.get("address") or ""),
            status=str(row.get("status") or "Offered"),
            mao=float(row.get("mao") or 0),
            fee=float(row.get("fee") or 0),
            zip_code=str(row.get("zip_code") or ""),
            buyer_name=str(row.get("buyer_name") or ""),
        )
        crm_ok = True
    except Exception as exc:
        print(f"CRM mirror failed: {exc}")

    want_sheets = sheets_configured()
    if not want_sheets:
        if crm_ok:
            return True, "Saved to local CRM (Sheets not configured)."
        return False, "Sheets not configured and local CRM save failed."

    try:
        import streamlit as st
        from streamlit_gsheets import GSheetsConnection

        conn = st.connection("gsheets", type=GSheetsConnection)
        existing = conn.read(worksheet="Leads", ttl=0)
        if existing is None or existing.empty:
            existing = _empty_df()
        updated = pd.concat([existing, pd.DataFrame([row])], ignore_index=True)
        conn.update(worksheet="Leads", data=updated)
        return True, "Deal locked in the Google Vault (+ local CRM mirror)."
    except Exception as exc:
        # Configured but failed — do not pretend Sheets wrote successfully.
        msg = f"Sheets configured but write failed: {exc}"
        if crm_ok:
            return False, f"{msg} (saved to local CRM only)."
        return False, msg
