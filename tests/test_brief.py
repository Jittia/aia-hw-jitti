"""Company brief from SEC 10-K text (dashboard pivot, Task 1). Run: .venv/bin/python -m unittest discover tests"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from mm_brief import founded_phrase, item1_description, website  # noqa: E402

PROSE = ("Acme Widgets, Inc. designs and sells industrial widgets used by manufacturers in more than forty countries. "
         "We operate two segments, Industrial and Consumer, and sell through distributors and our own sales force. "
         "Our products are known for durability and are protected by more than 300 patents worldwide. "
         "In fiscal 2025 we served over 12,000 customers and generated most of our revenue in North America. ")


class Description(unittest.TestCase):
    def test_skips_table_of_contents(self):
        html = ("<p>TABLE OF CONTENTS</p><p>Item 1. Business 4</p><p>Item 1A. Risk Factors 12</p>"
                "<p>PART I</p><p>Item 1. Business</p><p>Overview</p><p>" + PROSE + "</p><p>Item 1A. Risk Factors</p><p>Risky.</p>")
        d = item1_description(html)
        self.assertTrue(d.startswith("Acme Widgets, Inc. designs"), d)
        self.assertNotIn("Risk Factors", d)
        self.assertTrue(d.endswith("."))

    def test_none_when_no_section(self):
        self.assertIsNone(item1_description("<p>Item 1. Business 4</p><p>Item 1A. Risk Factors 12</p>"))

    def test_cut_at_whole_sentence(self):
        d = item1_description("<p>Item 1. Business</p><p>" + PROSE * 5 + "</p><p>Item 1A. Risk Factors</p>", max_chars=300)
        self.assertLessEqual(len(d), 300)
        self.assertTrue(d.endswith("."))


    def test_keeps_company_name_after_inc(self):
        body = ('Walmart Inc. ("Walmart," the "Company" or "we") is a people-led, technology-powered omnichannel retailer '
                "serving customers around the world in stores and online. " + PROSE)
        d = item1_description("<p>Item 1. Business</p><p>General</p><p>" + body + "</p><p>Item 1A. Risk Factors</p>")
        self.assertTrue(d.startswith("Walmart Inc. (") and "omnichannel retailer" in d, d)

    def test_drops_company_background_heading(self):
        d = item1_description("<p>Item 1. Business</p><p>Company Background</p><p>" + PROSE + "</p><p>Item 1A.</p>")
        self.assertTrue(d.startswith("Acme Widgets"), d)


    def test_toc_with_item_1a_in_brackets_or_dots(self):  # Halliburton "Item 1(a).", Rollins "Item 1.A."
        for sub in ("Item 1(a). Risk Factors 9 Item 1(b). Unresolved Staff Comments 19 Item 1(c). Cybersecurity 19",
                    "Item 1.A. Risk Factors. 11 Item 1.B. Unresolved Staff Comments. 19 Item 1.C. Cybersecurity 19"):
            toc = "<p>Item 1. Business 1 " + sub + " Item 2. Properties 20 " + "Item 3. Legal Proceedings 20 " * 30 + "</p>"
            d = item1_description(toc + "<p>Item 1. Business.</p><p>" + PROSE + "</p><p>" + sub.split(" Risk")[0] + " Risk Factors</p>")
            self.assertTrue(d and d.startswith("Acme Widgets"), d)

    def test_skips_quoted_cross_reference(self):  # Avista: see “Item 1. Business – Electric Operations”
        text = ("<p>For details see “Item 1. Business – Electric Operations”. The following is a summary of contracts as of "
                "December 31, 2025 with many words that go on for a while to pass the length check. " * 8 + "</p>"
                "<p>Item 1. Business</p><p>" + PROSE + "</p><p>Item 1A. Risk Factors</p>")
        self.assertTrue(item1_description(text).startswith("Acme Widgets"))

    def test_rejects_mid_sentence_start(self):
        d = item1_description("<p>Item 1. Business</p><p>is a Wisconsin corporation that sells power to customers in the state. " * 6 + "</p><p>Item 1A.</p>")
        self.assertIsNone(d)

    def test_skips_forward_looking_boilerplate(self):
        body = ("Our results are inherently uncertain and actual results could differ materially from expectations. " + PROSE)
        d = item1_description("<p>Item 1. Business</p><p>" + body + "</p><p>Item 1A. Risk Factors</p>")
        self.assertTrue(d.startswith("Acme Widgets"), d)


    def test_skips_definitions_and_page_number(self):
        body = ("Unless otherwise indicated or the context otherwise requires, “we” means Acme. "
                "This report includes amounts translated into US dollars from foreign currencies. " + PROSE)
        d = item1_description("<p>Item 1. Business</p><p>4 Business Overview " + body + "</p><p>Item 1A.</p>")
        self.assertTrue(d.startswith("Acme Widgets"), d)


    def test_skips_cross_reference_with_part_prefix(self):  # Avista: “Part 1 – Item 1. Business – …”
        text = ("<p>See “Part 1 – Item 1. Business – Electric Operations”. The following is a summary of contracts "
                "with many more words to pass the length check easily. " * 8 + "</p>")
        self.assertIsNone(item1_description(text))

    def test_boilerplate_quoting_item_1_is_one_sentence(self):  # Alpha: references in this “Item 1. Business” section …
        body = ("Unless otherwise indicated or the context otherwise requires, references in this “Item 1. Business” section "
                "to “we” refer to Acme. " + PROSE)
        d = item1_description("<p>Part I Item 1. Business</p><p>" + body + "</p><p>Item 1A. Risk Factors</p>")
        self.assertTrue(d.startswith("Acme Widgets"), d)

    def test_skips_trademark_and_definition_lines(self):
        body = "“Fiscal 2026” means the 52 weeks ended May 2, 2026. “Acme®” is our trademark. " + PROSE
        d = item1_description("<p>Item 1. Business</p><p>" + body + "</p><p>Item 1A.</p>")
        self.assertTrue(d.startswith("Acme Widgets"), d)


    def test_strips_zero_width_spaces_and_heading(self):  # Walmart / Ecolab: "\u200b General \u200b We are …"
        d = item1_description("<p>Item 1. Business</p><p>\u200b General \u200b " + PROSE + "</p><p>Item 1A.</p>")
        self.assertTrue(d.startswith("Acme Widgets"), repr(d[:20]))


class Facts(unittest.TestCase):
    def test_founded_phrase(self):
        self.assertEqual(founded_phrase("The company was founded in 1998 in Ohio.", 2026)["year"], 1998)
        self.assertEqual(founded_phrase("We were incorporated in Delaware in 2004.", 2026)["year"], 2004)
        self.assertIsNone(founded_phrase("We expect to open a plant in 2030.", 2026))
        self.assertIsNone(founded_phrase("Our notes were issued in 2019.", 2026))

    def test_website(self):
        self.assertEqual(website("Our website address is www.example.com. Information on it is not part of this report."), "www.example.com")
        self.assertEqual(website("our internet website at https://investors.acme.com/sec, free of charge"), "investors.acme.com")
        self.assertIsNone(website("available on the SEC's website at www.sec.gov"))


if __name__ == "__main__":
    unittest.main()
