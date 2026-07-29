"""
Bulk CSV importer — runs Flood Guard + 70% MAO, saves to Tampa War Room.
"""

from __future__ import annotations

import argparse
import sys

import pandas as pd

from database import init_db, save_lead
from rehab import apply_tampa_risk_adjustments


def import_leads_csv(
    file_path: str,
    *,
    default_rehab: float = 15000.0,
    fee: float = 10000.0,
    market_factor: float = 0.70,
) -> int:
    """
    CSV columns (case-insensitive): Address, Zip, ARV
    Optional: Phone, Seller, Status
    """
    init_db()
    df = pd.read_csv(file_path)
    cols = {c.lower().strip(): c for c in df.columns}

    def col(*names: str) -> str | None:
        for n in names:
            if n in cols:
                return cols[n]
        return None

    addr_c = col("address", "property_address", "property")
    zip_c = col("zip", "zip_code", "zipcode")
    arv_c = col("arv", "value", "estimate")
    phone_c = col("phone", "mobile", "seller_phone")
    seller_c = col("seller", "owner", "seller_name", "name")
    status_c = col("status")

    if not addr_c or not arv_c:
        raise ValueError("CSV must include Address and ARV columns.")

    count = 0
    for _, row in df.iterrows():
        address = str(row[addr_c]).strip()
        if not address or address.lower() == "nan":
            continue
        zip_code = str(row[zip_c]).strip()[:5] if zip_c else ""
        if zip_code.endswith(".0"):
            zip_code = zip_code[:-2]
        arv = float(row[arv_c])
        base = arv * market_factor
        hazard = apply_tampa_risk_adjustments(zip_code, base)
        final_mao = base - default_rehab - float(hazard["buffer_deduction"]) - fee
        phone = str(row[phone_c]).strip() if phone_c else ""
        if phone.lower() == "nan":
            phone = ""
        seller = str(row[seller_c]).strip() if seller_c else ""
        if seller.lower() == "nan":
            seller = ""
        status = str(row[status_c]).strip() if status_c else "New Lead"
        if status.lower() == "nan":
            status = "New Lead"

        save_lead(
            address=address,
            zip_code=zip_code,
            arv=arv,
            mao=final_mao,
            fee=fee,
            risk=hazard["risk_level"],
            flood_risk=bool(hazard.get("is_flood_zip")),
            status=status if status else "New Lead",
            seller_name=seller,
            seller_phone=phone,
        )
        count += 1

    print(f"{count} leads imported and analyzed!")
    return count


def import_33615_list(file_path: str) -> int:
    """Convenience wrapper for Town 'N' Country lists."""
    return import_leads_csv(file_path)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Import Tampa leads CSV into War Room")
    p.add_argument("csv", help="Path to CSV with Address, Zip, ARV")
    p.add_argument("--rehab", type=float, default=15000.0)
    p.add_argument("--fee", type=float, default=10000.0)
    args = p.parse_args(argv)
    import_leads_csv(args.csv, default_rehab=args.rehab, fee=args.fee)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
