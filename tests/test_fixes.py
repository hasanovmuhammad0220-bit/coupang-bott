import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bot"))

import coupang_bot  # noqa: E402
from coupang_bot import HttpError, format_caption, pick_top, to_number  # noqa: E402


class ToNumberFirstNumberTests(unittest.TestCase):
    def test_unit_price_suffix_ignored(self):
        self.assertEqual(to_number("21,900원 (10g당 1,234원)"), 21900)

    def test_range_takes_first(self):
        self.assertEqual(to_number("21,900~25,900원"), 21900)

    def test_existing_forms_still_work(self):
        self.assertEqual(to_number("₩21,900"), 21900)
        self.assertEqual(to_number("21,900.00"), 21900)
        self.assertEqual(to_number("-45%"), 45)


class DiscountFromPricesTests(unittest.TestCase):
    def test_missing_discount_computed_from_prices(self):
        items = [
            {"title": "a", "price": 9000, "listPrice": 10000},   # 10%
            {"title": "b", "price": 5000, "listPrice": 10000},   # 50%
        ]
        self.assertEqual([i["title"] for i in pick_top(items, 2)], ["b", "a"])
        self.assertIn("-50%", format_caption(items[1]))


class TelegramRetryTests(unittest.TestCase):
    def test_429_waits_and_retries_once(self):
        err = HttpError(429, '{"ok":false,"parameters":{"retry_after":7}}')
        with mock.patch.object(coupang_bot, "_post_json", side_effect=[err, {"ok": True}]) as p, \
             mock.patch.object(coupang_bot.time, "sleep") as sl:
            self.assertEqual(coupang_bot.tg_call("t", "sendMessage", {}), {"ok": True})
        self.assertEqual(p.call_count, 2)
        sl.assert_called_once_with(8)

    def test_migrated_group_reports_new_id(self):
        err = HttpError(400, '{"ok":false,"description":"group chat was upgraded",'
                             '"parameters":{"migrate_to_chat_id":-1009876}}')
        with mock.patch.object(coupang_bot, "_post_json", side_effect=err):
            with self.assertRaises(RuntimeError) as cm:
                coupang_bot.tg_call("t", "sendMessage", {})
        self.assertIn("-1009876", str(cm.exception))


class ApifyRetryTests(unittest.TestCase):
    def test_408_retried_once(self):
        with mock.patch.object(coupang_bot, "_post_json",
                               side_effect=[HttpError(408, "timeout"), [{"title": "x"}]]) as p:
            self.assertEqual(coupang_bot.fetch_goldbox("tok"), [{"title": "x"}])
        self.assertEqual(p.call_count, 2)
        self.assertGreater(p.call_args.kwargs["timeout"], 300)

    def test_bearer_header_used(self):
        with mock.patch.object(coupang_bot, "_post_json", return_value=[]) as p:
            coupang_bot.fetch_goldbox("tok")
        self.assertEqual(p.call_args.kwargs["headers"], {"Authorization": "Bearer tok"})


if __name__ == "__main__":
    unittest.main()
