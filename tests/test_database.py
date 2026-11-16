"""War Room lead safety rules."""

from __future__ import annotations

import unittest


class LeadSafetyRulesTest(unittest.TestCase):
    def test_do_not_contact_status_blocks_even_without_migrated_flag(self) -> None:
        from database import is_do_not_contact

        self.assertTrue(is_do_not_contact({"status": "Do Not Contact", "dnc_flag": 0}))

    def test_do_not_contact_flag_blocks_any_status(self) -> None:
        from database import is_do_not_contact

        self.assertTrue(is_do_not_contact({"status": "Interested", "dnc_flag": 1}))
        self.assertFalse(is_do_not_contact({"status": "Interested", "dnc_flag": 0}))


if __name__ == "__main__":
    unittest.main()
