"""
Assignment contract PDF — assignor fee for wholesaling deals.
Saves to contracts/ as a deal ledger.
"""

from __future__ import annotations

import datetime
import re
from pathlib import Path

from fpdf import FPDF

CONTRACTS_DIR = Path(__file__).resolve().parent / "contracts"


def _safe_name(address: str) -> str:
    cleaned = re.sub(r"[^\w\s\-]", "", address or "Property")
    cleaned = re.sub(r"\s+", "_", cleaned.strip())
    return cleaned[:80] or "Property"


def generate_assignment_pdf(
    address: str,
    buyer_name: str,
    assignment_fee: float,
    *,
    assignor_name: str = "DealShark Acquisitions",
    purchase_price: float | None = None,
    output_dir: Path | None = None,
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

    file_name = f"Assignment_{_safe_name(address)}.pdf"
    path = out_dir / file_name
    pdf.output(str(path))
    return path
