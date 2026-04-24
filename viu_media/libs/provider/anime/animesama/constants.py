import os
import re

from .....core.utils.networking import TIMEOUT

ANIMESAMA_PROVIDER_URL = "https://anime-sama.pw/"
ANIMESAMA_BASE_URL = os.environ.get("VIU_ANIMESAMA_BASE_URL", "https://anime-sama.to")
ANIMESAMA_CATALOGUE_URL = f"{ANIMESAMA_BASE_URL.rstrip('/')}/catalogue/"

REQUEST_HEADERS = {
    "Referer": ANIMESAMA_BASE_URL,
}

REQUEST_TIMEOUT = TIMEOUT

SUPPORTED_TRANSLATION_LANG_IDS = {
    "vostfr": "sub",
    "vf": "dub",
    "vf1": "dub",
    "vf2": "dub",
}

CATALOG_CARD_REGEX = re.compile(
    r'<div class="shrink-0 catalog-card card-base">.*?<a href="(?P<href>(?:https?://[^"]+)?/catalogue/[^"]+)".*?'
    r'<img\s+class="card-image"\s+src="(?P<poster>[^"]+)".*?alt="(?P<alt>[^"]*)".*?'
    r'<h2 class="card-title">(?P<title>.*?)</h2>.*?'
    r'<p class="alternate-titles">(?P<other_titles>.*?)</p>.*?'
    r'<span class="info-label">Genres</span>\s*<p class="info-value">(?P<genres>.*?)</p>.*?'
    r'<span class="info-label">Types</span>\s*<p class="info-value">(?P<types>.*?)</p>.*?'
    r'<span class="info-label">Langues</span>\s*<p class="info-value">(?P<languages>.*?)</p>.*?'
    r'<div class="synopsis-content">(?P<synopsis>.*?)</div>',
    re.DOTALL,
)
OLD_SEASON_REGEX = re.compile(
    r'panneauAnime\("(?P<name>.+?)", *"(?P<link>.+?)(?P<lang>vostfr|vf(?:1|2)?)"\);'
)
SEASON_LINK_REGEX_TEMPLATE = (
    r'/catalogue/{slug}/(?P<season>[^"/]+?)/(?P<lang>vostfr|vf(?:1|2)?)/?'
)
EPISODES_SCRIPT_REGEX = re.compile(r"episodes\.js\?filever=\d+")
PLAYERS_LIST_REGEX = re.compile(r"eps(\d+) ?= ?\[([\W\w]+?)\]")
EPISODE_BLOCK_REGEX = re.compile(
    r"resetListe\(\); *[\n\r]+\t*(.*?)}",
    re.DOTALL,
)
FLAG_VO_REGEX = re.compile(r'src=".+flag_(.+?)\.png".*?[\n\t]*<p.*?>VO</p>')
