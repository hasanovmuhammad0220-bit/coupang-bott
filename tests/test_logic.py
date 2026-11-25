import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bot"))

from coupang_bot import find_image, format_caption, pick_top, to_number  # noqa: E402


class ToNumberTests(unittest.TestCase):
    def test_variants(self):
        self.assertEqual(to_number(45), 45)
        self.assertEqual(to_number("45%"), 45)
        self.assertEqual(to_number("21,900"), 21900)
        self.assertEqual(to_number("21,900원"), 21900)
        self.assertIsNone(to_number(None))
        self.assertIsNone(to_number(""))
        self.assertIsNone(to_number("abc"))


class PickTopTests(unittest.TestCase):
    def test_sorts_by_discount_and_limits(self):
        items = [
            {"title": "t", "productId": "1", "discountPercentage": 10},
            {"title": "t", "productId": "2", "discountPercentage": "45%"},
            {"title": "t", "productId": "3", "discountPercentage": None},
            {"title": "t", "productId": "4"},
            {"title": "t", "productId": "5", "discountPercentage": 30},
        ]
        top = pick_top(items, 3)
        self.assertEqual([i["productId"] for i in top], ["2", "5", "1"])

    def test_dedupes_by_product_id(self):
        items = [
            {"title": "t", "productId": "1", "discountPercentage": 50},
            {"title": "t", "productId": "1", "discountPercentage": 50},
            {"title": "t", "productId": "2", "discountPercentage": 20},
        ]
        self.assertEqual([i["productId"] for i in pick_top(items, 5)], ["1", "2"])

    def test_skips_items_without_url_or_title(self):
        items = [{"title": "t", "productId": "1", "discountPercentage": 50, "title": "", "url": ""}]
        # items lacking title AND url are useless
        self.assertEqual(pick_top(items, 5), [])


class FormatCaptionTests(unittest.TestCase):
    def test_full_caption(self):
        item = {
            "title": "a <b>",
            "url": "https://www.coupang.com/vp/products/1",
            "price": "21,900",
            "listPrice": 39900,
            "discountPercentage": 45,
        }
        c = format_caption(item)
        self.assertIn("-45%", c)
        self.assertIn("21,900₩", c)
        self.assertIn("<s>39,900₩</s>", c)
        self.assertIn("a &lt;b&gt;", c)
        self.assertIn('href="https://www.coupang.com/vp/products/1"', c)

    def test_no_old_price_when_missing_or_not_higher(self):
        item = {"title": "x", "url": "https://c.com/1", "price": 1000}
        self.assertNotIn("<s>", format_caption(item))
        item["listPrice"] = 1000
        self.assertNotIn("<s>", format_caption(item))

    def test_price_fallback_keys(self):
        item = {"title": "x", "url": "https://c.com/1", "finalPrice": 5000}
        self.assertIn("5,000₩", format_caption(item))

    def test_no_discount_badge_when_zero(self):
        item = {"title": "x", "url": "https://c.com/1", "price": 1000}
        self.assertNotIn("-0%", format_caption(item))


class FindImageTests(unittest.TestCase):
    def test_finds_known_key(self):
        self.assertEqual(find_image({"imageUrl": "https://img/1.jpg"}), "https://img/1.jpg")
        self.assertEqual(find_image({"thumbnail": "//img/2.jpg"}), "https://img/2.jpg")

    def test_none_when_absent_or_invalid(self):
        self.assertIsNone(find_image({}))
        self.assertIsNone(find_image({"image": "not a url"}))


if __name__ == "__main__":
    unittest.main()
