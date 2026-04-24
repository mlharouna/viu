from __future__ import annotations

import base64
import binascii
from html import unescape
from urllib.parse import urljoin

from .constants import (
    ALT_TITLES_RE,
    ANIMIXPLAY_BASE,
    EMBED_IFRAME_RE,
    HTML_TAG_RE,
    IFRAME_SRC_RE,
    MIRROR_OPTION_RE,
    POSTER_RE,
    TITLE_RE,
    TRANSLATION_RE,
    TYPE_RE,
    VIDEO_TITLE_RE,
    VIDEO_TRANSLATION_RE,
    WHITESPACE_RE,
    YEAR_RE,
)


def clean_text(value: str) -> str:
    return WHITESPACE_RE.sub(" ", unescape(HTML_TAG_RE.sub(" ", value))).strip()


def normalize_title(value: str) -> str:
    return "".join(ch.lower() for ch in clean_text(value) if ch.isalnum())


def extract_detail_info(html: str) -> dict[str, str | list[str] | None]:
    alt_titles = []
    if alt_match := ALT_TITLES_RE.search(html):
        alt_titles = [clean_text(title) for title in alt_match.group(1).split(",")]

    return {
        "title": clean_text(TITLE_RE.search(html).group(1))
        if TITLE_RE.search(html)
        else None,
        "alt_titles": [title for title in alt_titles if title],
        "poster": POSTER_RE.search(html).group(1) if POSTER_RE.search(html) else None,
        "year": clean_text(YEAR_RE.search(html).group(1))
        if YEAR_RE.search(html)
        else None,
        "type": clean_text(TYPE_RE.search(html).group(1))
        if TYPE_RE.search(html)
        else None,
    }


def extract_episode_page_info(html: str) -> dict[str, str | None]:
    translation = None
    if match := VIDEO_TRANSLATION_RE.search(html):
        translation = match.group(1).lower()
    elif match := TRANSLATION_RE.search(html):
        translation = "dub" if match.group(1).lower() == "dubbed" else "sub"

    return {
        "title": clean_text(VIDEO_TITLE_RE.search(html).group(1))
        if VIDEO_TITLE_RE.search(html)
        else None,
        "translation": translation,
    }


def decode_mirror_option(value: str) -> str | None:
    try:
        padding = (-len(value)) % 4
        decoded = base64.b64decode(value + ("=" * padding)).decode(
            "utf-8", errors="ignore"
        )
    except (binascii.Error, ValueError):
        return None
    return decoded


def extract_iframe_sources(html: str) -> list[str]:
    links: list[str] = []

    if match := EMBED_IFRAME_RE.search(html):
        links.append(urljoin(ANIMIXPLAY_BASE, match.group(1)))

    for encoded_value, _label in MIRROR_OPTION_RE.findall(html):
        decoded = decode_mirror_option(encoded_value)
        if not decoded:
            continue
        iframe_match = IFRAME_SRC_RE.search(decoded)
        if not iframe_match:
            continue
        links.append(urljoin(ANIMIXPLAY_BASE, iframe_match.group(1)))

    deduped: list[str] = []
    seen: set[str] = set()
    for link in links:
        if link in seen:
            continue
        seen.add(link)
        deduped.append(link)
    return deduped
