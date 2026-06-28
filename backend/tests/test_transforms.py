"""Unit tests for OSINT selector extraction (#17), pure functions."""
from __future__ import annotations

from app.transforms.selectors import extract_selectors


def _kinds(text):
    return {(s.kind, s.value) for s in extract_selectors(text)}


def test_extracts_email_and_domain():
    sels = _kinds("Contact jane.doe@example.com or visit acme-corp.org for info.")
    assert ("email", "jane.doe@example.com") in sels
    assert ("domain", "acme-corp.org") in sels
    # The email's own domain is not double-reported as a bare domain.
    assert ("domain", "example.com") not in sels


def test_extracts_ipv4_and_rejects_bad_octets():
    sels = _kinds("server at 192.168.1.10, not 999.1.1.1")
    assert ("ipv4", "192.168.1.10") in sels
    assert ("ipv4", "999.1.1.1") not in sels


def test_extracts_crypto_addresses():
    eth = "0x52908400098527886E0F7030069857D2E4169EE7"
    btc = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
    sels = _kinds(f"send to {eth} or {btc}")
    assert ("eth_address", eth) in sels
    assert ("btc_address", btc) in sels


def test_extracts_url_and_phone():
    sels = _kinds("see https://example.com/path?q=1 call +1 (202) 555-0142")
    assert any(k == "url" and "example.com/path" in v for k, v in sels)
    assert any(k == "phone" for k, _ in sels)


def test_hashes_disambiguated_by_length():
    sha256 = "a" * 64
    md5 = "b" * 32
    sels = _kinds(f"{sha256} and {md5}")
    assert ("sha256", sha256) in sels
    assert ("md5", md5) in sels


def test_empty_text():
    assert extract_selectors("") == []
