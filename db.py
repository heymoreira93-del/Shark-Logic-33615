"""
Closer module — SQLite deal storage for click-to-sign + call notes + lead heat.
"""

from __future__ import annotations

import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_DEFAULT_DB = Path(__file__).resolve().parent / "deals.db"
DB_PATH = Path(os.getenv("DEALSHARK_DB_PATH") or _DEFAULT_DB)

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
    lead_temp TEXT DEFAULT 'Cold',
    lead_id INTEGER,
    deal_kind TEXT DEFAULT 'purchase',
    assignment_fee REAL DEFAULT 0,
    assignee_email TEXT DEFAULT ''
)
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_columns(conn: sqlite3.Connection) -> None:
    """Migrate older DBs that predate notes / lead_temp / lead_id / assignment fields."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(deals)").fetchall()}
    if "notes" not in cols:
        conn.execute("ALTER TABLE deals ADD COLUMN notes TEXT DEFAULT ''")
    if "lead_temp" not in cols:
        conn.execute("ALTER TABLE deals ADD COLUMN lead_temp TEXT DEFAULT 'Cold'")
    if "lead_id" not in cols:
        conn.execute("ALTER TABLE deals ADD COLUMN lead_id INTEGER")
    if "deal_kind" not in cols:
        conn.execute("ALTER TABLE deals ADD COLUMN deal_kind TEXT DEFAULT 'purchase'")
    if "assignment_fee" not in cols:
        conn.execute("ALTER TABLE deals ADD COLUMN assignment_fee REAL DEFAULT 0")
    if "assignee_email" not in cols:
        conn.execute("ALTER TABLE deals ADD COLUMN assignee_email TEXT DEFAULT ''")
    if "emd_status" not in cols:
        conn.execute("ALTER TABLE deals ADD COLUMN emd_status TEXT DEFAULT ''")
    if "stripe_session_id" not in cols:
        conn.execute("ALTER TABLE deals ADD COLUMN stripe_session_id TEXT DEFAULT ''")
    if "stripe_payment_intent" not in cols:
        conn.execute("ALTER TABLE deals ADD COLUMN stripe_payment_intent TEXT DEFAULT ''")


_PAYMENTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS emd_payments (
    id TEXT PRIMARY KEY,
    stripe_session_id TEXT NOT NULL UNIQUE,
    stripe_payment_intent TEXT DEFAULT '',
    deal_id TEXT DEFAULT '',
    address TEXT DEFAULT '',
    amount_cents INTEGER DEFAULT 0,
    status TEXT DEFAULT 'PENDING',
    mode TEXT DEFAULT '',
    checkout_url TEXT DEFAULT '',
    created_at TEXT DEFAULT '',
    paid_at TEXT DEFAULT ''
)
"""

_BLAST_SCHEMA = """
CREATE TABLE IF NOT EXISTS blast_logs (
    id TEXT PRIMARY KEY,
    address TEXT DEFAULT '',
    recipients INTEGER DEFAULT 0,
    ok INTEGER DEFAULT 0,
    message TEXT DEFAULT '',
    checkout_url TEXT DEFAULT '',
    created_at TEXT DEFAULT ''
)
"""


def init_db() -> None:
    with _connect() as conn:
        conn.execute(_SCHEMA)
        conn.execute(_PAYMENTS_SCHEMA)
        conn.execute(_BLAST_SCHEMA)
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
    lead_id: int | None = None,
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
                created_at, notes, lead_temp, lead_id
            ) VALUES (?, ?, ?, ?, 'PENDING', '', ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                lead_id,
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


def create_assignment_deal(
    address: str,
    *,
    purchase_price: float,
    assignment_fee: float,
    assignor_name: str,
    assignee_name: str,
    assignee_email: str = "",
    pdf_path: str = "",
    closing_date: str = "",
    emd: float = 2500.0,
) -> str:
    """
    PENDING assignment for buyer click-to-sign (?deal_id=).
    buyer_name = assignee; seller_name = assignor.
    """
    init_db()
    deal_id = str(uuid.uuid4())[:8]
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO deals (
                id, address, price, seller_name, status, signature,
                seller_phone, buyer_name, emd, closing_date, pdf_path,
                created_at, notes, lead_temp, lead_id, deal_kind,
                assignment_fee, assignee_email
            ) VALUES (?, ?, ?, ?, 'PENDING', '', '', ?, ?, ?, ?, ?, '', 'Hot', NULL,
                      'assignment', ?, ?)
            """,
            (
                deal_id,
                address,
                float(purchase_price),
                assignor_name,
                assignee_name,
                float(emd),
                closing_date,
                pdf_path,
                now,
                float(assignment_fee),
                (assignee_email or "").strip(),
            ),
        )
        conn.commit()
    return deal_id


def find_assignment_deal(address: str, *, signed_only: bool = False) -> dict[str, Any] | None:
    needle = (address or "").strip().lower()
    if not needle:
        return None
    street = needle.split(",")[0].strip()
    for deal in list_deals(limit=200):
        if (deal.get("deal_kind") or "purchase") != "assignment":
            continue
        if signed_only and (deal.get("status") or "") != "SIGNED":
            continue
        hay = (deal.get("address") or "").strip().lower()
        if needle in hay or (street and street in hay):
            return deal
    return None


def record_checkout_session(
    *,
    stripe_session_id: str,
    address: str = "",
    deal_id: str = "",
    amount_cents: int = 0,
    mode: str = "",
    status: str = "PENDING",
    checkout_url: str = "",
    stripe_payment_intent: str = "",
) -> str:
    """Insert or update a checkout row. Returns payment row id."""
    init_db()
    now = datetime.now(timezone.utc).isoformat()
    sid = (stripe_session_id or "").strip()
    with _connect() as conn:
        existing = conn.execute(
            "SELECT id FROM emd_payments WHERE stripe_session_id = ?",
            (sid,),
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE emd_payments
                SET address = COALESCE(NULLIF(?, ''), address),
                    deal_id = COALESCE(NULLIF(?, ''), deal_id),
                    amount_cents = CASE WHEN ? > 0 THEN ? ELSE amount_cents END,
                    status = ?,
                    mode = COALESCE(NULLIF(?, ''), mode),
                    checkout_url = COALESCE(NULLIF(?, ''), checkout_url),
                    stripe_payment_intent = COALESCE(NULLIF(?, ''), stripe_payment_intent)
                WHERE stripe_session_id = ?
                """,
                (
                    address,
                    deal_id,
                    int(amount_cents),
                    int(amount_cents),
                    status,
                    mode,
                    checkout_url,
                    stripe_payment_intent,
                    sid,
                ),
            )
            conn.commit()
            return str(existing["id"])
        row_id = str(uuid.uuid4())[:12]
        conn.execute(
            """
            INSERT INTO emd_payments (
                id, stripe_session_id, stripe_payment_intent, deal_id, address,
                amount_cents, status, mode, checkout_url, created_at, paid_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '')
            """,
            (
                row_id,
                sid,
                stripe_payment_intent,
                deal_id,
                address,
                int(amount_cents),
                status,
                mode,
                checkout_url,
                now,
            ),
        )
        conn.commit()
        return row_id


def mark_emd_paid_from_stripe(
    *,
    stripe_session_id: str,
    address: str = "",
    deal_id: str = "",
    amount_cents: int = 0,
    mode: str = "",
    stripe_payment_intent: str = "",
) -> str:
    """Idempotent paid write. Same session_id never creates a second paid event."""
    init_db()
    now = datetime.now(timezone.utc).isoformat()
    sid = (stripe_session_id or "").strip()
    with _connect() as conn:
        existing = conn.execute(
            "SELECT id, status, paid_at FROM emd_payments WHERE stripe_session_id = ?",
            (sid,),
        ).fetchone()
        if existing and (existing["status"] or "").upper() == "PAID":
            return str(existing["id"])
        if existing:
            conn.execute(
                """
                UPDATE emd_payments
                SET status = 'PAID',
                    paid_at = ?,
                    stripe_payment_intent = COALESCE(NULLIF(?, ''), stripe_payment_intent),
                    address = COALESCE(NULLIF(?, ''), address),
                    deal_id = COALESCE(NULLIF(?, ''), deal_id),
                    amount_cents = CASE WHEN ? > 0 THEN ? ELSE amount_cents END,
                    mode = COALESCE(NULLIF(?, ''), mode)
                WHERE stripe_session_id = ?
                """,
                (
                    now,
                    stripe_payment_intent,
                    address,
                    deal_id,
                    int(amount_cents),
                    int(amount_cents),
                    mode,
                    sid,
                ),
            )
            row_id = str(existing["id"])
        else:
            row_id = str(uuid.uuid4())[:12]
            conn.execute(
                """
                INSERT INTO emd_payments (
                    id, stripe_session_id, stripe_payment_intent, deal_id, address,
                    amount_cents, status, mode, checkout_url, created_at, paid_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'PAID', ?, '', ?, ?)
                """,
                (
                    row_id,
                    sid,
                    stripe_payment_intent,
                    deal_id,
                    address,
                    int(amount_cents),
                    mode,
                    now,
                    now,
                ),
            )
        if deal_id:
            conn.execute(
                """
                UPDATE deals
                SET emd_status = 'PAID',
                    stripe_session_id = ?,
                    stripe_payment_intent = ?
                WHERE id = ?
                """,
                (sid, stripe_payment_intent, deal_id),
            )
        conn.commit()
        return row_id


def list_emd_payments(limit: int = 40) -> list[dict[str, Any]]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM emd_payments
            ORDER BY
                CASE status WHEN 'PAID' THEN 0 ELSE 1 END,
                created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def latest_paid_emd(address: str = "") -> dict[str, Any] | None:
    init_db()
    with _connect() as conn:
        if address.strip():
            row = conn.execute(
                """
                SELECT * FROM emd_payments
                WHERE status = 'PAID' AND lower(address) LIKE ?
                ORDER BY paid_at DESC LIMIT 1
                """,
                (f"%{address.strip().lower()}%",),
            ).fetchone()
        else:
            row = conn.execute(
                """
                SELECT * FROM emd_payments
                WHERE status = 'PAID'
                ORDER BY paid_at DESC LIMIT 1
                """
            ).fetchone()
    return dict(row) if row else None


def record_blast(
    *,
    address: str,
    ok: bool,
    message: str,
    recipients: int = 0,
    checkout_url: str = "",
) -> str:
    init_db()
    row_id = str(uuid.uuid4())[:12]
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO blast_logs (id, address, recipients, ok, message, checkout_url, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (row_id, address, int(recipients), 1 if ok else 0, message[:500], checkout_url, now),
        )
        conn.commit()
    return row_id


def list_blast_logs(limit: int = 20) -> list[dict[str, Any]]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM blast_logs ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]
