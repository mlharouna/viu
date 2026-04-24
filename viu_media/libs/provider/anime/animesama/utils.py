import html
import re
from ast import literal_eval
from itertools import zip_longest
from urllib.parse import urlparse

from .constants import (
    CATALOG_CARD_REGEX,
    EPISODE_BLOCK_REGEX,
    EPISODES_SCRIPT_REGEX,
    FLAG_VO_REGEX,
    OLD_SEASON_REGEX,
    PLAYERS_LIST_REGEX,
    SEASON_LINK_REGEX_TEMPLATE,
    SUPPORTED_TRANSLATION_LANG_IDS,
)
from .types import (
    AnimeSamaCatalogueItem,
    AnimeSamaEpisodeEntry,
    AnimeSamaEpisodeSource,
    AnimeSamaSeasonLink,
)

FLAG_ID_TO_LANG_ID = {
    "fr": "vf",
    "jp": "vostfr",
}

ANIMESAMA_SEASON_SUFFIX_REGEX = re.compile(
    r"\s+(?:(?:season\s+\d+)|(?:\d+(?:st|nd|rd|th)\s+season)|(?:final\s+season))\s*$",
    re.IGNORECASE,
)
ANIMESAMA_TRAILING_SEASON_NUMBER_REGEX = re.compile(
    r"\s+season\s+(?P<number>\d+)\s*$", re.IGNORECASE
)
ANIMESAMA_TRAILING_ORDINAL_SEASON_REGEX = re.compile(
    r"\s+(?P<number>\d+)(?:st|nd|rd|th)\s+season\s*$",
    re.IGNORECASE,
)
ANIMESAMA_FINAL_SEASON_REGEX = re.compile(r"\s+final\s+season\s*$", re.IGNORECASE)


def normalize_base_url(url: str) -> str:
    return url.rstrip("/")


def normalize_search_query(query: str) -> str:
    normalized = re.sub(r"\s+", " ", query).strip()
    stripped = ANIMESAMA_SEASON_SUFFIX_REGEX.sub("", normalized).rstrip(" :-")
    collapsed = re.sub(r"\s+", " ", stripped).strip()
    return collapsed or normalized


def search_query_candidates(query: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", query).strip()
    candidates = [normalized, normalize_search_query(normalized)]
    candidates.extend(strip_title_suffix(candidate) for candidate in tuple(candidates))
    candidates.extend(
        normalize_title_punctuation(candidate) for candidate in tuple(candidates)
    )

    unique_candidates: list[str] = []
    for candidate in candidates:
        if candidate and candidate not in unique_candidates:
            unique_candidates.append(candidate)
    return unique_candidates


def strip_title_suffix(query: str) -> str:
    return re.split(r"\s+[–—-]\s*", query, maxsplit=1)[0].strip() or query


def normalize_title_punctuation(query: str) -> str:
    return re.sub(r"\s+", " ", query.replace(":", " ")).strip()


def requested_season_from_query(query: str) -> str | None:
    normalized = re.sub(r"\s+", " ", query).strip()
    if match := ANIMESAMA_TRAILING_SEASON_NUMBER_REGEX.search(normalized):
        return f"saison{int(match.group('number'))}"
    if match := ANIMESAMA_TRAILING_ORDINAL_SEASON_REGEX.search(normalized):
        return f"saison{int(match.group('number'))}"
    if ANIMESAMA_FINAL_SEASON_REGEX.search(normalized):
        return "final"
    return None


def filter_season_links_for_query(
    season_links: list[AnimeSamaSeasonLink],
    query: str,
) -> list[AnimeSamaSeasonLink]:
    requested_season = requested_season_from_query(query)
    if not requested_season:
        return season_links

    if requested_season == "final":
        numeric_links = [
            link for link in season_links if re.fullmatch(r"saison\d+", link["season"])
        ]
        if not numeric_links:
            return season_links

        highest_number = max(
            int(re.search(r"\d+", link["season"]).group(0)) for link in numeric_links
        )
        filtered = [
            link for link in season_links if link["season"] == f"saison{highest_number}"
        ]
        return filtered or season_links

    filtered = [link for link in season_links if link["season"] == requested_season]
    return filtered or season_links


def strip_comments(value: str) -> str:
    value = re.sub(r"/\*[\W\w]*?\*/", "", value)
    return re.sub(r"<!--[\W\w]*?-->", "", value)


def split_and_strip(value: str, delimiters: tuple[str, ...]) -> list[str]:
    parts = [value]
    for delimiter in delimiters:
        parts = sum((part.split(delimiter) for part in parts), [])
    return [part.strip() for part in parts]


def zip_varlen(*iterables: list[list[str]]) -> list[list[str]]:
    sentinel = object()
    return [
        [entry for entry in iterable if entry is not sentinel]
        for iterable in zip_longest(*iterables, fillvalue=sentinel)
    ]


def clean_text(value: str) -> str:
    return html.unescape(re.sub(r"\s+", " ", value)).strip()


def slug_from_href(href: str) -> str:
    match = re.search(r"/catalogue/(?P<slug>[^/]+)/?$", href)
    if not match:
        raise ValueError(f"Unsupported Anime-Sama catalogue href: {href}")
    return match.group("slug")


def parse_catalogue_cards(page: str) -> list[AnimeSamaCatalogueItem]:
    items: list[AnimeSamaCatalogueItem] = []
    for match in CATALOG_CARD_REGEX.finditer(page):
        raw_types = [
            clean_text(item) for item in match.group("types").split(",") if item
        ]
        if "Anime" not in raw_types:
            continue

        href = clean_text(match.group("href"))
        items.append(
            AnimeSamaCatalogueItem(
                id=slug_from_href(href),
                title=clean_text(match.group("title") or match.group("alt")),
                other_titles=[
                    clean_text(title)
                    for title in match.group("other_titles").split(",")
                    if clean_text(title)
                ],
                genres=[
                    clean_text(genre)
                    for genre in re.split(r",| - ", match.group("genres"))
                    if clean_text(genre)
                ],
                types=raw_types,
                languages=[
                    clean_text(language)
                    for language in match.group("languages").split(",")
                    if clean_text(language)
                ],
                poster=clean_text(match.group("poster")) or None,
                synopsis=clean_text(match.group("synopsis")) or None,
            )
        )
    return items


def parse_catalogue_item(page: str, slug: str) -> AnimeSamaCatalogueItem | None:
    for item in parse_catalogue_cards(page):
        if item["id"] == slug:
            return item
    return None


def parse_season_links(
    page: str, slug: str, base_url: str
) -> list[AnimeSamaSeasonLink]:
    normalized_base = normalize_base_url(base_url)
    links: dict[tuple[str, str], AnimeSamaSeasonLink] = {}
    page_without_comments = strip_comments(page)

    for match in OLD_SEASON_REGEX.finditer(page_without_comments):
        lang_id = match.group("lang")
        if lang_id not in SUPPORTED_TRANSLATION_LANG_IDS:
            continue
        season_path = match.group("link").strip("/")
        season_name = clean_text(match.group("name"))
        season = season_id_from_path(season_path, lang_id)
        links[(season, lang_id)] = AnimeSamaSeasonLink(
            name=season_name,
            season=season,
            lang_id=lang_id,
            url=f"{normalized_base}/catalogue/{slug}/{season}/",
        )

    fallback_regex = re.compile(SEASON_LINK_REGEX_TEMPLATE.format(slug=re.escape(slug)))
    for match in fallback_regex.finditer(page):
        lang_id = match.group("lang")
        season = match.group("season")
        links[(season, lang_id)] = AnimeSamaSeasonLink(
            name=season.replace("-", " ").title(),
            season=season,
            lang_id=lang_id,
            url=f"{normalized_base}/catalogue/{slug}/{season}/",
        )

    return sorted(
        links.values(),
        key=lambda item: season_sort_key(item["season"], item["lang_id"]),
    )


def season_sort_key(season: str, lang_id: str) -> tuple[tuple[int | str, ...], int]:
    parts: list[int | str] = []
    for part in re.split(r"(\d+)", season):
        if not part:
            continue
        parts.append(int(part) if part.isdigit() else part)
    return tuple(parts), 0 if lang_id == "vostfr" else 1


def season_id_from_path(season_path: str, lang_id: str) -> str:
    suffix = f"/{lang_id}"
    if season_path.endswith(suffix):
        season_path = season_path[: -len(suffix)]
    return season_path.strip("/")


def detect_missing_lang_id(vostfr_page: str) -> str | None:
    match = FLAG_VO_REGEX.search(strip_comments(vostfr_page))
    if not match:
        return None
    return FLAG_ID_TO_LANG_ID.get(match.group(1))


def episode_script_path(page: str) -> str | None:
    if match := EPISODES_SCRIPT_REGEX.search(page):
        return match.group(0)
    return None


def normalize_players(players: list[str]) -> list[str]:
    normalized = [player.replace("vidmoly.to", "vidmoly.net") for player in players]
    if len(normalized) > 1:
        normalized[0], normalized[1] = normalized[1], normalized[0]
    return normalized


def extract_players(episodes_js: str) -> list[list[str]]:
    players = sorted(
        PLAYERS_LIST_REGEX.findall(strip_comments(episodes_js)),
        key=lambda item: int(item[0]),
    )
    player_groups = [re.findall(r"'(.+?)'", payload) for _, payload in players]
    return [normalize_players(group) for group in zip_varlen(*player_groups)]


def extract_episode_names(
    page: str, number_of_episodes: int, number_of_episodes_max: int
) -> list[str]:
    matches = EPISODE_BLOCK_REGEX.findall(strip_comments(page))
    if not matches:
        return [f"Episode {index}" for index in range(1, number_of_episodes + 1)]

    functions_list = split_and_strip(matches[-1], (";", "\n"))[:-1]

    def padding(value: int) -> str:
        return " " * (len(str(number_of_episodes_max)) - len(str(value)))

    def episode_name_range(start: int, stop: int) -> list[str]:
        return [f"Episode {index}{padding(index)}" for index in range(start, stop)]

    episode_names: list[str] = []
    for function in functions_list:
        if function.startswith("//"):
            continue

        call_start = function.find("(")
        name = function[:call_start]
        args_string = function[call_start + 1 : -1]
        if args_string:
            args = literal_eval(args_string + ",")
            if not isinstance(args, tuple):
                continue
        else:
            args = ()

        match name:
            case "":
                continue
            case "creerListe":
                if len(args) < 2:
                    continue
                episode_names.extend(episode_name_range(int(args[0]), int(args[1]) + 1))
            case "finirListe" | "finirListeOP":
                if not args:
                    break
                episode_names.extend(
                    episode_name_range(
                        int(args[0]),
                        int(args[0]) + number_of_episodes - len(episode_names),
                    )
                )
                break
            case "newSP":
                if args:
                    episode_names.append(f"Episode {args[0]}")
            case "newSPF":
                if args:
                    episode_names.append(clean_text(str(args[0])))
            case _:
                continue

    if not episode_names:
        return [f"Episode {index}" for index in range(1, number_of_episodes + 1)]
    return [clean_text(name) for name in episode_names]


def translation_from_lang_id(lang_id: str) -> str | None:
    return SUPPORTED_TRANSLATION_LANG_IDS.get(lang_id)


def parse_episode_number(name: str, fallback: int) -> str:
    if match := re.search(r"Episode\s+(\d+(?:\.\d+)?)", name, re.IGNORECASE):
        return match.group(1)
    return str(fallback)


def source_name_from_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.hostname:
        return parsed.hostname.replace("www.", "")
    return "player"


def merge_episode_languages(
    episodes: list[AnimeSamaEpisodeEntry],
    names: list[str],
    players_by_episode: list[list[str]],
    lang_id: str,
    season: str,
) -> list[AnimeSamaEpisodeEntry]:
    merged = list(episodes)
    for index, (name, players) in enumerate(
        zip(names, players_by_episode, strict=False), start=1
    ):
        normalized_name = clean_text(name)
        episode_number = parse_episode_number(normalized_name, index)
        existing = next(
            (
                episode
                for episode in merged
                if episode["season"] == season and episode["episode"] == episode_number
            ),
            None,
        )
        source = AnimeSamaEpisodeSource(
            name=source_name_from_url(players[0]) if players else "player",
            players=players,
        )
        if existing:
            existing["sources"][lang_id] = source
            continue

        merged.append(
            AnimeSamaEpisodeEntry(
                season=season,
                episode=episode_number,
                title=normalized_name,
                sources={lang_id: source},
            )
        )
    return merged
