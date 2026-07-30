"""
Assignment contract PDF — assignor fee for wholesaling deals.
Includes Disbursement Authorization + escrow wire instructions.
Saves to contracts/ as a deal ledger.
"""

from __future__ import annotations

import datetime
import os
import re
from pathlib import Path
from typing import Any

from fpdf import FPDF

CONTRACTS_DIR = Path(__file__).resolve().parent / "contracts"


def _safe_name(address: str) -> str:
    cleaned = re.sub(r"[^\w\s\-]", "", address or "Property")
    cleaned = re.sub(r"\s+", "_", cleaned.strip())
    return cleaned[:80] or "Property"


def _wire_info() -> dict[str, str]:
    return {
        "bank": (os.getenv("WIRE_BANK") or "Title Company Escrow - SEE CLOSING AGENT").strip(),
        "account": (os.getenv("WIRE_ACCOUNT") or "[PROVIDE AT CLOSING]").strip(),
        "routing": (os.getenv("WIRE_ROUTING") or "[PROVIDE AT CLOSING]").strip(),
        "title_company": (os.getenv("TITLE_COMPANY_NAME") or "Title Agent / Escrow Officer").strip(),
    }


def add_disbursement_page(
    pdf: FPDF,
    assignment_fee: float,
    your_name: str,
    address: str,
    wire_info: dict[str, Any] | None = None,
) -> None:
    """Title-company instruction page: pay Assignor fee from buyer proceeds."""
    info = wire_info or _wire_info()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "DISBURSEMENT AUTHORIZATION", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)
    pdf.set_font("Helvetica", size=11)
    body = (
        f"TO: {info.get('title_company', 'TITLE AGENT / ESCROW OFFICER')}\n\n"
        f"This document serves as formal authorization to disburse funds from the "
        f"closing of the property located at:\n\n{address}\n\n"
        f"On the closing date, you are hereby directed to pay {your_name} the sum of "
        f"${assignment_fee:,.2f} as an Assignment Fee.\n\n"
        f"These funds are to be paid directly to the Assignor from the Buyer's "
        f"side of the settlement statement (HUD-1 / Closing Disclosure).\n\n"
        f"WIRE / ESCROW INSTRUCTIONS:\n"
        f"Bank: {info.get('bank', '')}\n"
        f"Account Name: {your_name}\n"
        f"Account Number: {info.get('account', '')}\n"
        f"Routing Number: {info.get('routing', '')}\n\n"
        f"This page is an operational template. Confirm final wire instructions "
        f"with your title company before funding."
    )
    pdf.multi_cell(0, 6, body)
    pdf.ln(10)
    # Red wire callout (fpdf uses RGB 0-255)
    pdf.set_text_color(180, 0, 0)
    pdf.set_font("Helvetica", "B", 11)
    pdf.multi_cell(
        0,
        6,
        "IMPORTANT: Do not release Assignment Fee to any party other than the "
        f"named Assignor ({your_name}) without written amendment.",
    )
    pdf.set_text_color(0, 0, 0)


def generate_assignment_pdf(
    address: str,
    buyer_name: str,
    assignment_fee: float,
    *,
    assignor_name: str = "DealShark Acquisitions",
    purchase_price: float | None = None,
    output_dir: Path | None = None,
    include_disbursement: bool = True,
    flood_insurance_required: bool = False,
) -> Path:
    """
    Build Assignment of Real Estate Purchase Contract PDF.
    Returns path under contracts/.
    """
    out_dir = output_dir or CONTRACTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(
        0,
        10,
        "ASSIGNMENT OF REAL ESTATE PURCHASE CONTRACT",
        align="C",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "DealShark Acquisitions - Shark Logic Terms", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)

    if flood_insurance_required:
        pdf.set_text_color(180, 0, 0)
        pdf.set_font("Helvetica", "B", 12)
        pdf.multi_cell(
            0,
            6,
            "WARNING: FLOOD INSURANCE REQUIRED - High Risk Flood Zone (AE). "
            "Offer / MAO includes a $15,000 flood-risk buffer. Assignee must verify premiums.",
        )
        pdf.set_text_color(0, 0, 0)
        pdf.ln(4)

    date_str = datetime.date.today().strftime("%B %d, %Y")
    pdf.set_font("Helvetica", size=11)

    price_line = ""
    if purchase_price is not None:
        price_line = f"Underlying Purchase Price (MAO / Contract Price): ${purchase_price:,.2f}\n\n"

    body = (
        f"This Assignment is made on {date_str}.\n\n"
        f"Assignor ({assignor_name}) hereby assigns all rights, title, and interest "
        f"in and to the real estate purchase contract for the property located at:\n\n"
        f"{address}\n\n"
        f"To Assignee (The Cash Buyer): {buyer_name or 'TBD'}\n\n"
        f"{price_line}"
        f"The Assignee agrees to pay an Assignment Fee of: ${assignment_fee:,.2f}\n"
        f"This fee is to be paid in full at the time of closing and shall appear on "
        f"the settlement statement (HUD-1 / Closing Disclosure).\n\n"
        f"Shark Logic terms: Property is assigned AS-IS. Assignor makes no warranty "
        f"regarding flood zone, insurance premiums, or condition. Assignee acknowledges "
        f"independent due diligence, including flood and insurance review for Tampa Bay "
        f"zips including 33615 (Town 'N' Country / Rocky Point).\n\n"
        f"This document is a simplified operational template. Consult a Florida-licensed "
        f"attorney and title company before relying on it for a live closing."
    )
    pdf.multi_cell(0, 6, body)
    pdf.ln(16)

    pdf.set_font("Helvetica", size=11)
    pdf.cell(95, 8, "_______________________________", new_x="RIGHT")
    pdf.cell(0, 8, "_______________________________", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(95, 6, "Assignor Signature", new_x="RIGHT")
    pdf.cell(0, 6, "Assignee Signature", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)
    pdf.cell(95, 8, "_______________________________", new_x="RIGHT")
    pdf.cell(0, 8, "_______________________________", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(95, 6, "Date", new_x="RIGHT")
    pdf.cell(0, 6, "Date", new_x="LMARGIN", new_y="NEXT")

    # Escrow wire callout on page 1 (red)
    wire = _wire_info()
    pdf.ln(12)
    pdf.set_text_color(180, 0, 0)
    pdf.set_font("Helvetica", "B", 10)
    pdf.multi_cell(
        0,
        5,
        (
            f"TITLE / ESCROW WIRE (for Assignment Fee at closing):\n"
            f"Bank: {wire['bank']} | Routing: {wire['routing']} | "
            f"Acct: {wire['account']} | Pay to: {assignor_name}"
        ),
    )
    pdf.set_text_color(0, 0, 0)

    if include_disbursement:
        add_disbursement_page(pdf, assignment_fee, assignor_name, address, wire)

    file_name = f"Assignment_{_safe_name(address)}.pdf"
    path = out_dir / file_name
    pdf.output(str(path))
    return path
