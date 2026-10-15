"""UI pagination is deterministic and independent of Tk's display server."""

import unittest

from autoclicker.gui.paging import DEFAULT_PAGE_SIZE, select_template_page


class PaginationTests(unittest.TestCase):
    def test_large_list_never_creates_more_than_one_page(self):
        items = [f"image-{n:04d}.png" for n in range(503)]
        first, page, pages, total = select_template_page(items)
        self.assertEqual((page, pages, total), (0, 26, 503))
        self.assertEqual(len(first), DEFAULT_PAGE_SIZE)
        last, page, pages, total = select_template_page(items, page=100)
        self.assertEqual((page, pages, total), (25, 26, 503))
        self.assertEqual(len(last), 3)
        self.assertEqual(last[0], (500, "image-0500.png"))

    def test_casefold_search_preserves_original_priority(self):
        items = ["a.PNG", "LOGIN.PNG", "button.png", "login-confirm.png"]
        result, page, pages, total = select_template_page(
            items, "login", page_size=1, page=1
        )
        self.assertEqual(result, [(3, "login-confirm.png")])
        self.assertEqual((page, pages, total), (1, 2, 2))

    def test_empty_search_and_page_clamping(self):
        result, page, pages, total = select_template_page(
            ["yes.png"], query="not-found", page=-5
        )
        self.assertEqual(result, [])
        self.assertEqual((page, pages, total), (0, 1, 0))

    def test_invalid_page_size_rejected(self):
        with self.assertRaises(ValueError):
            select_template_page(["a.png"], page_size=0)


if __name__ == "__main__":
    unittest.main()
