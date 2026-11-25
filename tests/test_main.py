import io
import os
import sys
import unittest
from contextlib import redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bot"))

import coupang_bot  # noqa: E402

ITEM = {"title": "x", "url": "https://c.com/1", "price": 1000, "imageUrl": "https://img/1.jpg"}
ENV = {"APIFY_TOKEN": "a", "TELEGRAM_BOT_TOKEN": "b", "TELEGRAM_CHAT_ID": "-100"}


class SendItemTests(unittest.TestCase):
    def test_photo_failure_falls_back_to_message(self):
        calls = []

        def fake(token, method, payload):
            calls.append(method)
            if method == "sendPhoto":
                raise RuntimeError("bad image")
            return {"ok": True}

        with mock.patch.object(coupang_bot, "tg_call", side_effect=fake):
            self.assertTrue(coupang_bot.send_item("b", "-100", ITEM))
        self.assertEqual(calls, ["sendPhoto", "sendMessage"])

    def test_no_image_uses_message(self):
        item = {k: v for k, v in ITEM.items() if k != "imageUrl"}
        with mock.patch.object(coupang_bot, "tg_call", return_value={"ok": True}) as m:
            coupang_bot.send_item("b", "-100", item)
        self.assertEqual(m.call_args[0][1], "sendMessage")

    def test_total_failure_returns_false(self):
        with mock.patch.object(coupang_bot, "tg_call", side_effect=RuntimeError("x")):
            self.assertFalse(coupang_bot.send_item("b", "-100", ITEM))


class MainTests(unittest.TestCase):
    def setUp(self):
        p = mock.patch.dict(os.environ, ENV)
        p.start()
        self.addCleanup(p.stop)
        s = mock.patch.object(coupang_bot.time, "sleep")
        s.start()
        self.addCleanup(s.stop)

    def test_empty_fetch_returns_1_and_sends_nothing(self):
        with mock.patch.object(coupang_bot, "fetch_goldbox", return_value=[]), \
             mock.patch.object(coupang_bot, "tg_call") as tg, redirect_stdout(io.StringIO()):
            self.assertEqual(coupang_bot.main([]), 1)
        tg.assert_not_called()

    def test_fetch_error_returns_1(self):
        with mock.patch.object(coupang_bot, "fetch_goldbox", side_effect=RuntimeError("HTTP 401")), \
             mock.patch.object(coupang_bot, "tg_call") as tg, redirect_stdout(io.StringIO()):
            self.assertEqual(coupang_bot.main([]), 1)
        tg.assert_not_called()

    def test_one_failure_does_not_stop_others(self):
        items = [dict(ITEM, productId=str(i)) for i in range(3)]
        results = [False, True, True]
        with mock.patch.object(coupang_bot, "fetch_goldbox", return_value=items), \
             mock.patch.object(coupang_bot, "send_item", side_effect=results) as si, \
             redirect_stdout(io.StringIO()):
            rc = coupang_bot.main([])
        self.assertEqual(si.call_count, 3)
        self.assertEqual(rc, 0)

    def test_all_failures_returns_1(self):
        items = [dict(ITEM, productId=str(i)) for i in range(2)]
        with mock.patch.object(coupang_bot, "fetch_goldbox", return_value=items), \
             mock.patch.object(coupang_bot, "send_item", return_value=False), \
             redirect_stdout(io.StringIO()):
            self.assertEqual(coupang_bot.main([]), 1)

    def test_dry_run_sends_nothing(self):
        out = io.StringIO()
        with mock.patch.object(coupang_bot, "fetch_goldbox", return_value=[ITEM]), \
             mock.patch.object(coupang_bot, "tg_call") as tg, redirect_stdout(out):
            self.assertEqual(coupang_bot.main(["--dry-run"]), 0)
        tg.assert_not_called()
        self.assertIn("Coupang'da ko'rish", out.getvalue())

    def test_missing_env_returns_1(self):
        with mock.patch.dict(os.environ, {"APIFY_TOKEN": ""}), redirect_stdout(io.StringIO()), \
             mock.patch.object(coupang_bot, "fetch_goldbox") as f:
            self.assertEqual(coupang_bot.main([]), 1)
        f.assert_not_called()


if __name__ == "__main__":
    unittest.main()
