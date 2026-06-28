"""Pure regex selector extraction for OSINT text (#17).

Extracts the common "selectors" an analyst pivots on — emails, domains, URLs,
IPv4 addresses, phone numbers, crypto addresses, and file hashes — from free
text. No dependencies, no network; fully unit-tested.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_URL = re.compile(r"https?://[^\s)>\]\"']+", re.IGNORECASE)
_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_BTC = re.compile(r"\b(?:bc1[a-z0-9]{25,90}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})\b")
_ETH = re.compile(r"\b0x[a-fA-F0-9]{40}\b")
_PHONE = re.compile(r"(?<![\w.])\+?\d[\d\s().-]{7,}\d(?![\w.])")
_MD5 = re.compile(r"\b[a-fA-F0-9]{32}\b")
_SHA1 = re.compile(r"\b[a-fA-F0-9]{40}\b")
_SHA256 = re.compile(r"\b[a-fA-F0-9]{64}\b")
# A domain not part of an email/URL: label(s) + TLD.
_DOMAIN = re.compile(r"\b(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}\b")


@dataclass(slots=True, frozen=True)
class Selector:
    kind: str
    value: str


def _valid_ipv4(value: str) -> bool:
    parts = value.split(".")
    return len(parts) == 4 and all(p.isdigit() and 0 <= int(p) <= 255 for p in parts)


def extract_selectors(text: str) -> list[Selector]:
    """Return de-duplicated selectors found in ``text`` (stable order)."""
    if not text:
        return []

    found: list[Selector] = []
    seen: set[tuple[str, str]] = set()

    def add(kind: str, value: str) -> None:
        key = (kind, value.lower())
        if key not in seen:
            seen.add(key)
            found.append(Selector(kind=kind, value=value))

    emails = set(_EMAIL.findall(text))
    for v in emails:
        add("email", v)

    urls = set(_URL.findall(text))
    for v in urls:
        add("url", v.rstrip(".,);"))

    # ETH addresses double as 40-hex, so claim them before sha1/domain checks.
    for v in set(_ETH.findall(text)):
        add("eth_address", v)
    for v in set(_BTC.findall(text)):
        add("btc_address", v)

    for v in set(_IPV4.findall(text)):
        if _valid_ipv4(v):
            add("ipv4", v)

    # Hashes: longest first so a sha256 isn't mis-tagged as md5/sha1.
    eth_values = {s.value.lower()[2:] for s in found if s.kind == "eth_address"}
    for v in set(_SHA256.findall(text)):
        add("sha256", v)
    for v in set(_SHA1.findall(text)):
        if v.lower() not in eth_values:
            add("sha1", v)
    claimed = {s.value.lower() for s in found if s.kind in {"sha256", "sha1"}}
    for v in set(_MD5.findall(text)):
        if v.lower() not in claimed:
            add("md5", v)

    # Domains, excluding those already captured inside emails/URLs.
    email_domains = {e.split("@", 1)[1].lower() for e in emails}
    for v in set(_DOMAIN.findall(text)):
        low = v.lower()
        if low in email_domains:
            continue
        if any(low in u.lower() for u in urls):
            continue
        if _valid_ipv4(v):
            continue
        add("domain", v)

    for v in set(_PHONE.findall(text)):
        digits = re.sub(r"\D", "", v)
        if 8 <= len(digits) <= 15:
            add("phone", v.strip())

    return found
