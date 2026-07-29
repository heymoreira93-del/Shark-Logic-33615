"""
Closer module — SQLite deal storage for click-to-sign + call notes + lead heat.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parent / "deals.db"

LEAD_TEMPS = ("Cold", "Warm", "Hot")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS deals (
    id TEXT PRIMARY KEY,
    address TEXT,
    price REAL,
    seller_name TEXT,
    status TEXT,
    signature TEXT,
    seller_phone TEXT DEFAULT '',
    buyer_name TEXT DEFAULT '',
    emd REAL DEFAULT 1000,
    closing_date TEXT DEFAULT '',
    pdf_path TEXT DEFAULT '',
    signed_at TEXT DEFAULT '',
    created_at TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    lead_temp TEXT DEFAULT 'Cold'
)
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_columns(conn: sqlite3.Connection) -> None:
    """Migrate older DBs that predate notes / lead_temp."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(deals)").fetchall()}
    if "notes" not in cols:
        conn.execute("ALTER TABLE deals ADD COLUMN notes TEXT DEFAULT ''")
    if "lead_temp" not in cols:
        conn.execute("ALTER TABLE deals ADD COLUMN lead_temp TEXT DEFAULT 'Cold'")


def init_db() -> None:
    with _connect() as conn:
        conn.execute(_SCHEMA)
        _ensure_columns(conn)
        conn.commit()


def create_deal(
    address: str,
    price: float,
    seller_name: str,
    *,
    seller_phone: str = "",
    buyer_name: str = "",
    emd: float = 1000.0,
    closing_date: str = "",
    pdf_path: str = "",
    notes: str = "",
    lead_temp: str = "Cold",
) -> str:
    """Insert a PENDING deal. Returns short UUID for the signing URL."""
    init_db()
    deal_id = str(uuid.uuid4())[:8]
    now = datetime.now(timezone.utc).isoformat()
    temp = lead_temp if lead_temp in LEAD_TEMPS else "Cold"
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO deals (
                id, address, price, seller_name, status, signature,
                seller_phone, buyer_name, emd, closing_date, pdf_path,
                created_at, notes, lead_temp
            ) VALUES (?, ?, ?, ?, 'PENDING', '', ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                deal_id,
                address,
                float(price),
                seller_name,
                seller_phone,
                buyer_name,
                float(emd),
                closing_date,
                pdf_path,
                now,
                notes or "",
                temp,
            ),
        )
        conn.commit()
    return deal_id


def get_deal(deal_id: str) -> dict[str, Any] | None:
    init_db()
    with _connect() as conn:
        row = conn.execute("SELECT * FROM deals WHERE id = ?", (deal_id,)).fetchone()
    return dict(row) if row else None


def list_deals(limit: int = 50) -> list[dict[str, Any]]:
    """Newest deals first — Hot leads bubble via sort in the UI."""
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM deals
            ORDER BY
                CASE lead_temp WHEN 'Hot' THEN 0 WHEN 'Warm' THEN 1 ELSE 2 END,
                created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def sign_deal(deal_id: str, signature: str) -> bool:
    init_db()
    signature = (signature or "").strip()
    if not signature:
        return False
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        cur = conn.execute(
            """
            UPDATE deals
            SET status = 'SIGNED', signature = ?, signed_at = ?
            WHERE id = ? AND status = 'PENDING'
            """,
            (signature, now, deal_id),
        )
        conn.commit()
        return cur.rowcount > 0


def mark_as_signed(deal_id: str, signature: str) -> bool:
    return sign_deal(deal_id, signature)


def update_lead_temp(deal_id: str, lead_temp: str) -> bool:
    if lead_temp not in LEAD_TEMPS:
        return False
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE deals SET lead_temp = ? WHERE id = ?",
            (lead_temp, deal_id),
        )
        conn.commit()
        return cur.rowcount > 0


def append_note(deal_id: str, note: str) -> bool:
    """Append a timestamped call/conversation note."""
    note = (note or "").strip()
    if not note:
        return False
    init_db()
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    entry = f"[{stamp}] {note}"
    with _connect() as conn:
        row = conn.execute("SELECT notes FROM deals WHERE id = ?", (deal_id,)).fetchone()
        if not row:
            return False
        existing = (row["notes"] or "").strip()
        combined = f"{existing}\n{entry}".strip() if existing else entry
        conn.execute("UPDATE deals SET notes = ? WHERE id = ?", (combined, deal_id))
        conn.commit()
    return True


def set_notes(deal_id: str, notes: str) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE deals SET notes = ? WHERE id = ?",
            (notes or "", deal_id),
        )
        conn.commit()
        return cur.rowcount > 0


def update_pdf_path(deal_id: str, pdf_path: str) -> None:
    init_db()
    with _connect() as conn:
        conn.execute("UPDATE deals SET pdf_path = ? WHERE id = ?", (pdf_path, deal_id))
        conn.commit()
