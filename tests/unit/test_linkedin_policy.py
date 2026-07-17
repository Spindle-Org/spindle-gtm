"""Policy scan: no LinkedIn automation libraries or network requests to LinkedIn in src.

Imports of browser-automation libs are banned outright; a LinkedIn domain used inside an
HTTP-client call is banned. Governance blocklist *strings* (e.g. policy.py's deny regex) are
NOT flagged because they are neither imports nor HTTP calls.
"""

from __future__ import annotations

import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "spindle_gtm"

_AUTOMATION_IMPORT_RE = re.compile(
    r"^\s*(?:import|from)\s+(?:playwright|selenium|puppeteer|pyppeteer|"
    r"undetected_chromedriver|webdriver|mechanize|splinter)\b",
    re.MULTILINE,
)
_LINKEDIN_HTTP_RE = re.compile(
    r"(?i)(?:requests\.|httpx\.|aiohttp|urllib|urlopen|\.get\(|\.post\()[^\n]*"
    r"(?:linkedin\.com|lnkd\.in)"
)


def _scan(text: str) -> list[str]:
    return _AUTOMATION_IMPORT_RE.findall(text) + _LINKEDIN_HTTP_RE.findall(text)


def test_no_linkedin_automation_in_source() -> None:
    offending: dict[str, list[str]] = {}
    for path in SRC.rglob("*.py"):
        hits = _AUTOMATION_IMPORT_RE.findall(path.read_text(encoding="utf-8"))
        http = _LINKEDIN_HTTP_RE.findall(path.read_text(encoding="utf-8"))
        if hits or http:
            offending[str(path)] = hits + http
    assert not offending, offending


def test_scanner_catches_real_violations() -> None:
    assert _AUTOMATION_IMPORT_RE.search("import selenium")
    assert _AUTOMATION_IMPORT_RE.search("from playwright.sync_api import sync_playwright")
    assert _LINKEDIN_HTTP_RE.search("requests.get('https://www.linkedin.com/in/x')")


def test_scanner_ignores_blocklist_strings() -> None:
    # A governance deny-regex mentioning the domain is not an HTTP call or import.
    assert not _AUTOMATION_IMPORT_RE.search('_RE = re.compile(r"playwright|selenium")')
    assert not _LINKEDIN_HTTP_RE.search('_LINKEDIN_RE = re.compile(r"linkedin\\.com")')
