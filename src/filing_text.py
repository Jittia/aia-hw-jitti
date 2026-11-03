"""Turn an SEC filing's HTML into the visible text a reader sees (hidden inline-XBRL facts removed),
so a number found in it is a number the company printed, not a machine tag. Moved from layer2_prep.py (Phase 1)."""
from __future__ import annotations

import html
import re


def html_to_text(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
    raw = re.sub(r"(?is)<ix:header>.*?</ix:header>", " ", raw)  # inline-XBRL hidden facts
    raw = re.sub(r"(?i)<br\s*/?>|</(p|div|tr|li|h\d)>", "\n", raw)
    txt = html.unescape(re.sub(r"<[^>]+>", " ", raw))
    txt = re.sub(r"[ \t\xa0]+", " ", txt)
    return re.sub(r"\n\s*\n+", "\n\n", txt).strip()
