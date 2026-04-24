import re

ANIMIXPLAY_BASE = "https://www.animixplay.net"
ANIMIXPLAY_SEARCH_ENDPOINT = f"{ANIMIXPLAY_BASE}/wp-json/wp/v2/search"

MAX_TIMEOUT = 10
SEARCH_PAGE_LIMIT = 25

REQUEST_HEADERS = {
    "Referer": f"{ANIMIXPLAY_BASE}/",
    "Origin": ANIMIXPLAY_BASE,
}

EPISODE_SEARCH_SUFFIX = " Episode"

HTML_TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")

TITLE_RE = re.compile(r'<h2 itemprop="partOfSeries">([^<]+)</h2>')
ALT_TITLES_RE = re.compile(r'<span class="alter">([^<]+)</span>')
POSTER_RE = re.compile(
    r'<div class="thumb">.*?<img[^>]+(?:data-src|src)="([^"]+)"',
    re.DOTALL,
)
YEAR_RE = re.compile(r"<b>Released:</b>\s*([^<]+)")
TYPE_RE = re.compile(r"<b>Type:</b>\s*([^<]+)")

SEARCH_RESULT_RE = re.compile(
    r'<a href="(?P<url>https://www\.animixplay\.net/anime/[^"]+/)"[^>]*rel="(?P<id>\d+)"[^>]*>.*?'
    r'<h2 itemprop="headline">(?P<title>[^<]+)</h2>',
    re.DOTALL | re.IGNORECASE,
)

EPISODE_CARD_RE = re.compile(
    r'<a href="(?P<url>https://www\.animixplay\.net/[^"]*?-episode-[^"]+/)"[^>]*title="(?P<title_attr>[^"]+)"[^>]*class="tip"[^>]*>.*?'
    r'<div class="tt">(?P<series_title>.*?)<h2 itemprop="headline">(?P<headline>[^<]+)</h2>',
    re.DOTALL | re.IGNORECASE,
)

EPISODE_NUMBER_RE = re.compile(r"Episode\s+(\d+(?:\.\d+)?)", re.IGNORECASE)
TRANSLATION_RE = re.compile(r"English\s+(Subbed|Dubbed)", re.IGNORECASE)

EMBED_IFRAME_RE = re.compile(
    r'<div class="player-embed" id="pembed">\s*<iframe[^>]+src="([^"]+)"',
    re.DOTALL | re.IGNORECASE,
)
MIRROR_OPTION_RE = re.compile(
    r'<option value="([^"]+)"[^>]*>\s*([^<]+)\s*</option>',
    re.IGNORECASE,
)
IFRAME_SRC_RE = re.compile(r'<iframe[^>]+src="([^"]+)"', re.IGNORECASE)
VIDEO_TITLE_RE = re.compile(r'<h1 class="entry-title" itemprop="name">([^<]+)</h1>')
VIDEO_TRANSLATION_RE = re.compile(r'<span class="lg">(Sub|Dub)</span>', re.IGNORECASE)
