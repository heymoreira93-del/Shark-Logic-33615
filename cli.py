"""
CLI Wrapper — desk mode. Instant MAO + optional PDF.

Example:
  python cli.py --arv 300000 --sqft 1500 --fee 10000 --rehab medium
  python cli.py --arv 300000 --sqft 1500 --address "123 Main St" --pdf
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta

from generator import ContractParties, generate_contract, print_success
from logic import (
    DEFAULT_MARKET_FACTOR,
    DealInputs,
    analyze_deal,
    format_comparison_table,
    parse_rehab_level,
)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Real Estate Deal Suite CLI — MAO calculator + optional contract PDF",
    )
    p.add_argument("--arv", type=float, required=True, help="After Repair Value")
    p.add_argument("--sqft", type=float, required=True, help="Property square footage")
    p.add_argument("--fee", type=float, default=10000.0, help="Wholesale fee / profit target")
    p.add_argument(
        "--rehab",
        type=str,
        default="medium",
        help="Rehab preset: light | medium | heavy",
    )
    p.add_argument(
        "--factor",
        type=float,
        default=DEFAULT_MARKET_FACTOR,
        help="Market factor (default 0.70)",
    )
    p.add_argument(
        "--rehab-total",
        type=float,
        default=None,
        help="Override rehab with a fixed dollar amount",
    )
    p.add_argument("--address", type=str, default="", help="Property address (required with --pdf)")
    p.add_argument("--buyer", type=str, default="Buyer LLC", help="Buyer name for PDF")
    p.add_argument("--seller", type=str, default="Seller Name", help="Seller name for PDF")
    p.add_argument("--earnest", type=float, default=1000.0, help="Earnest money for PDF")
    p.add_argument(
        "--closing-days",
        type=int,
        default=21,
        help="Days from today until closing (PDF)",
    )
    p.add_argument(
        "--tier",
        choices=["aggressive", "mid", "safe"],
        default="aggressive",
        help="Which offer tier becomes purchase price in the PDF",
    )
    p.add_argument("--pdf", action="store_true", help="Write contract PDF to contracts/")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if not 0.5 <= args.factor <= 1.0:
        print("Error: --factor should be between 0.5 and 1.0 (e.g. 0.70)", file=sys.stderr)
        return 1

    try:
        level = parse_rehab_level(args.rehab)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    result = analyze_deal(
        DealInputs(
            arv=args.arv,
            sqft=args.sqft,
            fee=args.fee,
            rehab_level=level,
            market_factor=args.factor,
            rehab_override=args.rehab_total,
        )
    )

    print("\n=== Deal Summary ===")
    for line in result.summary_lines():
        print(line)
    print()
    print(format_comparison_table(result))
    print()

    if args.pdf:
        if not args.address.strip():
            print("Error: --address is required when using --pdf", file=sys.stderr)
            return 1

        tier_map = {
            "aggressive": "Aggressive",
            "mid": "Mid",
            "safe": "Safe",
        }
        price = result.offers[tier_map[args.tier]]
        parties = ContractParties(
            seller_name=args.seller,
            buyer_name=args.buyer,
            property_address=args.address.strip(),
            purchase_price=price,
            earnest_money=args.earnest,
            closing_date=date.today() + timedelta(days=args.closing_days),
            expiration_date=date.today(),
        )
        path = generate_contract(parties=parties)
        print_success(path, parties)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
