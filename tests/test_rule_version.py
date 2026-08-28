import unittest
from uuid import UUID

from touchstone import db


class RuleVersionTests(unittest.TestCase):
    def test_rule_set_version_is_stable_for_same_rules(self):
        rows = [
            {
                "id": UUID("12345678-1234-5678-1234-567812345678"),
                "text": "Use specific facts.",
                "scope": "all",
                "post_type": None,
                "kind": "guidance",
                "rule_version": 1,
            }
        ]
        self.assertEqual(db.active_rule_set_version(rows), db.active_rule_set_version(rows))

    def test_rule_set_version_changes_when_rule_changes(self):
        first = [{"id": UUID("12345678-1234-5678-1234-567812345678"), "text": "A", "scope": "all", "post_type": None, "kind": "guidance", "rule_version": 1}]
        second = [{**first[0], "rule_version": 2}]
        self.assertNotEqual(db.active_rule_set_version(first), db.active_rule_set_version(second))
