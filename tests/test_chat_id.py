import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bot"))

from get_chat_id import extract_chats  # noqa: E402


class ExtractChatsTests(unittest.TestCase):
    def test_finds_group_from_member_update_and_skips_private(self):
        updates = [
            {"my_chat_member": {"chat": {"id": -100123, "type": "supergroup", "title": "Skidka"}}},
            {"message": {"chat": {"id": 55, "type": "private"}}},
            {"message": {"chat": {"id": -42, "type": "group", "title": "G"}}},
        ]
        self.assertEqual(extract_chats(updates),
                         {-100123: ("supergroup", "Skidka"), -42: ("group", "G")})

    def test_empty(self):
        self.assertEqual(extract_chats([]), {})


if __name__ == "__main__":
    unittest.main()
