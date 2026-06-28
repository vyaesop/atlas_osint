"""RSS / Atom feed parsing for continuous monitoring (#19).

Parses RSS 2.0 and Atom feeds with the standard-library XML parser (no deps).
The parsed items can be screened/ingested on demand; wiring a periodic fetch is
a deployment concern (the arq worker / a cron schedule calls the ingest path).
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass

_ATOM = {"a": "http://www.w3.org/2005/Atom"}


@dataclass(slots=True)
class FeedItem:
    title: str
    summary: str
    link: str
    published: str | None


def _text(el: ET.Element | None) -> str:
    return (el.text or "").strip() if el is not None and el.text else ""


def parse_feed(xml: str) -> tuple[str, list[FeedItem]]:
    """Return ``(feed_title, items)`` for an RSS or Atom document."""
    root = ET.fromstring(xml.strip())

    rss_items = root.findall(".//item")
    if rss_items:  # RSS 2.0
        channel_title = _text(root.find(".//channel/title"))
        items = [
            FeedItem(
                title=_text(it.find("title")),
                summary=_text(it.find("description")),
                link=_text(it.find("link")),
                published=_text(it.find("pubDate")) or None,
            )
            for it in rss_items
        ]
        return channel_title, items

    # Atom
    feed_title = _text(root.find("a:title", _ATOM))
    items = []
    for e in root.findall("a:entry", _ATOM):
        link_el = e.find("a:link", _ATOM)
        link = link_el.get("href", "") if link_el is not None else ""
        items.append(FeedItem(
            title=_text(e.find("a:title", _ATOM)),
            summary=_text(e.find("a:summary", _ATOM)) or _text(e.find("a:content", _ATOM)),
            link=link,
            published=_text(e.find("a:updated", _ATOM)) or None,
        ))
    return feed_title, items
