import unittest
from unittest.mock import patch

from touchstone import auth


class AuthTests(unittest.TestCase):
    def setUp(self):
        auth.invalidate_cache()

    @patch("touchstone.auth.db.get_active_keys")
    def test_verified_key_includes_its_scopes(self, get_active_keys):
        raw_key = "test-key"
        get_active_keys.return_value = [
            {
                "name": "reviewer",
                "key_hash": auth.hash_key(raw_key),
                "scopes": ["rules:read"],
            }
        ]

        principal = auth.verify_key(raw_key)

        self.assertIsNotNone(principal)
        self.assertEqual(principal.name, "reviewer")
        self.assertEqual(principal.scopes, frozenset({"rules:read"}))

    @patch("touchstone.auth.db.get_active_keys")
    def test_invalid_key_is_rejected(self, get_active_keys):
        get_active_keys.return_value = []
        self.assertIsNone(auth.verify_key("nope"))
