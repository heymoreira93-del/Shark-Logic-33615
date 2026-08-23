"""Payment confirmation rules — no live charges, no secret values."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class PaymentRulesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "deals.db"
        os.environ["DEALSHARK_DB_PATH"] = str(self.db)
        # Force a clean import path for db path
        import db as dbmod

        dbmod.DB_PATH = self.db
        dbmod.init_db()

    def tearDown(self) -> None:
        try:
            self.tmp.cleanup()
        except PermissionError:
            pass

    def test_mode_off_without_key(self) -> None:
        with patch.dict(os.environ, {"STRIPE_SECRET_KEY": ""}, clear=False):
            from payments import stripe_mode

            self.assertEqual(stripe_mode(), "off")

    def test_query_flag_is_not_paid(self) -> None:
        from payments import session_is_paid

        self.assertFalse(session_is_paid(None))
        self.assertFalse(session_is_paid({"payment_status": "unpaid"}))
        self.assertTrue(session_is_paid({"payment_status": "paid"}))

    def test_confirm_rejects_bad_session_id(self) -> None:
        from payments import confirm_checkout_session

        result = confirm_checkout_session("emd_paid=1")
        self.assertFalse(result["paid"])
        self.assertFalse(result["ok"])

    def test_paid_persist_is_idempotent(self) -> None:
        from db import list_emd_payments, mark_emd_paid_from_stripe

        first = mark_emd_paid_from_stripe(
            stripe_session_id="cs_test_abc123",
            address="1 Test St",
            deal_id="deadbeef",
            amount_cents=250000,
            mode="test",
            stripe_payment_intent="pi_test_1",
        )
        second = mark_emd_paid_from_stripe(
            stripe_session_id="cs_test_abc123",
            address="1 Test St",
            deal_id="deadbeef",
            amount_cents=250000,
            mode="test",
            stripe_payment_intent="pi_test_1",
        )
        self.assertEqual(first, second)
        rows = [r for r in list_emd_payments() if r["stripe_session_id"] == "cs_test_abc123"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "PAID")


if __name__ == "__main__":
    unittest.main()
