from __future__ import annotations

import logging
import re
from functools import lru_cache
from urllib.parse import quote_plus

from ..base import BaseAnimeProvider
from ..params import AnimeParams, EpisodeStreamsParams, SearchParams
from ..types import Anime, AnimeEpisodeInfo, SearchResult, SearchResults
from ..utils.debug import debug_provider
from .constants import (
    ANIMIXPLAY_BASE,
    ANIMIXPLAY_SEARCH_ENDPOINT,
    EPISODE_CARD_RE,
    EPISODE_NUMBER_RE,
    EPISODE_SEARCH_SUFFIX,
    MAX_TIMEOUT,
    REQUEST_HEADERS,
    SEARCH_PAGE_LIMIT,
    SEARCH_RESULT_RE,
    TRANSLATION_RE,
)
from .extractor import (
    clean_text,
    extract_detail_info,
    extract_episode_page_info,
    extract_iframe_sources,
    normalize_title,
)
from .mappers import map_to_anime, map_to_search_results, map_to_server

logger = logging.getLogger(__name__)

SEASON_SUFFIX_RE = re.compile(
    r"\s+(?:(?:season\s+\d+)|(?:\d+(?:st|nd|rd|th)\s+season)|(?:final\s+season))\s*$",
    re.IGNORECASE,
)


class Animixplay(BaseAnimeProvider):
    HEADERS = REQUEST_HEADERS

    def __init__(self, client) -> None:
        super().__init__(client)
        self._search_result_cache: dict[str, SearchResult] = {}
        self._anime_url_cache: dict[str, str] = {}

    @debug_provider
    def search(self, params: SearchParams) -> SearchResults | None:
        return self._search(params)

    @lru_cache()
    def _search(self, params: SearchParams) -> SearchResults | None:
        response = self.client.get(
            ANIMIXPLAY_SEARCH_ENDPOINT,
            params={"search": params.query, "page": params.current_page},
            timeout=MAX_TIMEOUT,
        )
        response.raise_for_status()
        records = [
            record for record in response.json() if record.get("subtype") == "anime"
        ]
        if not records:
            records = self._search_html(params)
        if not records:
            return None

        results = map_to_search_results(records)
        for record, result in zip(records, results.results):
            self._search_result_cache[result.id] = result
            self._anime_url_cache[result.id] = record["url"]
        return results

    def _search_html(self, params: SearchParams) -> list[dict[str, str]]:
        response = self.client.get(
            self._episode_search_url(params.query, params.current_page),
            timeout=MAX_TIMEOUT,
        )
        response.raise_for_status()

        records: list[dict[str, str]] = []
        seen_ids: set[str] = set()
        for match in SEARCH_RESULT_RE.finditer(response.text):
            result_id = match.group("id")
            if result_id in seen_ids:
                continue
            seen_ids.add(result_id)
            records.append(
                {
                    "id": result_id,
                    "title": clean_text(match.group("title")),
                    "url": match.group("url"),
                    "subtype": "anime",
                }
            )
        return records

    def _fallback_details_from_search_result(
        self, search_result: SearchResult
    ) -> dict[str, str | list[str] | None]:
        return {
            "title": search_result.title,
            "alt_titles": [title for title in search_result.other_titles if title],
            "poster": search_result.poster,
            "year": search_result.year,
            "type": search_result.media_type,
        }

    @debug_provider
    def get(self, params: AnimeParams) -> Anime | None:
        return self._get_anime(params)

    @lru_cache()
    def _get_search_result(self, params: AnimeParams) -> SearchResult | None:
        if cached := self._search_result_cache.get(params.id):
            return cached

        results = self._search(SearchParams(query=params.query))
        if not results:
            return None

        for result in results.results:
            if result.id == params.id:
                return result
        return None

    @lru_cache()
    def _get_anime(self, params: AnimeParams) -> Anime | None:
        search_result = self._get_search_result(params)
        if not search_result:
            logger.error(f"No search result found for ID {params.id}")
            return None

        anime_url = self._anime_url_cache.get(params.id)
        if not anime_url:
            logger.error(f"No URL found for anime ID {params.id}")
            return None

        details = self._fallback_details_from_search_result(search_result)
        try:
            response = self.client.get(anime_url, timeout=MAX_TIMEOUT)
            response.raise_for_status()
            extracted_details = extract_detail_info(response.text)
            if extracted_details["title"]:
                details = extracted_details
            else:
                logger.debug(
                    "Animixplay detail page missing structured anime metadata: %s",
                    anime_url,
                )
        except Exception as exc:
            logger.debug("Animixplay detail fetch failed for %s: %s", anime_url, exc)

        episodes = self._load_episode_entries(
            search_result.title,
            tuple([search_result.title, *search_result.other_titles, params.query]),
            anime_url,
        )
        anime = map_to_anime(params.id, details, episodes)
        if not anime.episodes.sub:
            logger.warning(
                "Animixplay resolved anime=%s query=%r but found no sub episodes",
                params.id,
                params.query,
            )
        return anime

    def _episode_search_url(self, query: str, page: int) -> str:
        if page <= 1:
            return f"{ANIMIXPLAY_BASE}/?s={quote_plus(query)}"
        return f"{ANIMIXPLAY_BASE}/page/{page}/?s={quote_plus(query)}"

    def _base_title_variants(self, *titles: str) -> list[str]:
        variants: list[str] = []
        for title in titles:
            cleaned = clean_text(title)
            if not cleaned:
                continue
            stripped = SEASON_SUFFIX_RE.sub("", cleaned).strip(" -:")
            for candidate in (cleaned, stripped):
                if candidate and candidate not in variants:
                    variants.append(candidate)
        return variants

    def _episode_search_queries(
        self,
        primary_title: str,
        raw_titles: tuple[str, ...] | list[str],
        anime_url: str | None,
    ) -> list[str]:
        queries: list[str] = []
        titles = self._base_title_variants(primary_title, *raw_titles)
        for title in titles:
            query = f"{title}{EPISODE_SEARCH_SUFFIX}"
            if query not in queries:
                queries.append(query)

        if anime_url:
            slug = anime_url.rstrip("/").rsplit("/", 1)[-1].replace("-", " ").strip()
            for title in self._base_title_variants(slug):
                query = f"{title}{EPISODE_SEARCH_SUFFIX}"
                if query not in queries:
                    queries.append(query)

        return queries

    @lru_cache()
    def _load_episode_entries(
        self,
        primary_title: str,
        raw_titles: tuple[str, ...] | list[str],
        anime_url: str | None = None,
    ) -> list[dict[str, str]]:
        candidate_titles = {normalize_title(primary_title)}
        candidate_titles.update(normalize_title(title) for title in raw_titles if title)
        candidate_titles.update(
            normalize_title(title)
            for title in self._base_title_variants(primary_title, *raw_titles)
        )
        candidate_titles.discard("")

        found: dict[tuple[str, str], dict[str, str]] = {}
        search_queries = self._episode_search_queries(
            primary_title, raw_titles, anime_url
        )

        for search_query in search_queries:
            empty_pages = 0
            for page in range(1, SEARCH_PAGE_LIMIT + 1):
                try:
                    response = self.client.get(
                        self._episode_search_url(search_query, page),
                        timeout=MAX_TIMEOUT,
                    )
                    response.raise_for_status()
                except Exception:
                    break

                page_matches = list(EPISODE_CARD_RE.finditer(response.text))
                if not page_matches:
                    empty_pages += 1
                    if empty_pages >= 2:
                        break
                    continue

                page_added = 0
                for match in page_matches:
                    headline = clean_text(match.group("headline"))
                    episode_number_match = EPISODE_NUMBER_RE.search(headline)
                    if not episode_number_match:
                        continue

                    prefix = headline[: episode_number_match.start()].strip(" -")
                    if normalize_title(prefix) not in candidate_titles:
                        continue

                    translation_match = TRANSLATION_RE.search(headline)
                    translation = (
                        "dub"
                        if translation_match
                        and translation_match.group(1).lower() == "dubbed"
                        else "sub"
                    )
                    episode_number = episode_number_match.group(1)

                    entry = {
                        "url": match.group("url"),
                        "title": headline,
                        "episode": episode_number,
                        "translation": translation,
                    }
                    key = (entry["episode"], entry["translation"])
                    if key not in found:
                        found[key] = entry
                        page_added += 1

                if page_added == 0:
                    empty_pages += 1
                    if empty_pages >= 2:
                        break
                else:
                    empty_pages = 0

            if found:
                logger.debug(
                    "Animixplay episode search matched %s entries using query %r",
                    len(found),
                    search_query,
                )
                break

        def sort_key(item: dict[str, str]) -> tuple[float, str]:
            return (float(item["episode"]), item["translation"])

        entries = sorted(found.values(), key=sort_key)
        if not entries:
            logger.warning(
                "Animixplay found anime result but no episode posts for title=%r queries=%r candidates=%r",
                primary_title,
                search_queries,
                sorted(candidate_titles),
            )
        return entries

    @lru_cache()
    def _get_episode_info(
        self, params: EpisodeStreamsParams
    ) -> AnimeEpisodeInfo | None:
        anime = self._get_anime(AnimeParams(id=params.anime_id, query=params.query))
        if not anime or not anime.episodes_info:
            return None

        for episode in anime.episodes_info:
            if episode.episode == params.episode:
                return episode
        return None

    @debug_provider
    def episode_streams(self, params: EpisodeStreamsParams):
        episode = self._get_episode_info(params)
        if not episode:
            logger.error(
                f"Episode {params.episode} doesn't exist for anime {params.anime_id}"
            )
            return

        response = self.client.get(str(episode.id), timeout=MAX_TIMEOUT)
        response.raise_for_status()

        page_info = extract_episode_page_info(response.text)
        if (
            page_info["translation"]
            and page_info["translation"] != params.translation_type
        ):
            return

        links = extract_iframe_sources(response.text)
        if not links:
            return

        yield map_to_server(
            links=links,
            episode_title=page_info["title"] or episode.title,
            translation_type=params.translation_type,
            headers={
                "Referer": f"{ANIMIXPLAY_BASE}/",
                "Origin": ANIMIXPLAY_BASE,
                "User-Agent": self.client.headers.get("User-Agent", ""),
            },
        )


if __name__ == "__main__":
    from ..utils.debug import test_anime_provider

    test_anime_provider(Animixplay)
