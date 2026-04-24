import logging
import re
from functools import lru_cache
from typing import Iterator

from ..base import BaseAnimeProvider
from ..params import AnimeParams, EpisodeStreamsParams, SearchParams
from ..types import Anime, AnimeEpisodeInfo, SearchResult, SearchResults, Server
from ..utils.debug import debug_provider
from .constants import (
    ANIMESAMA_BASE_URL,
    ANIMESAMA_CATALOGUE_URL,
    REQUEST_HEADERS,
)
from .mappers import map_to_anime_result, map_to_search_results, map_to_server
from .types import AnimeSamaEpisodeEntry, AnimeSamaSeasonLink
from .utils import (
    detect_missing_lang_id,
    episode_script_path,
    extract_episode_names,
    extract_players,
    filter_season_links_for_query,
    merge_episode_languages,
    normalize_base_url,
    parse_catalogue_cards,
    parse_catalogue_item,
    parse_season_links,
    search_query_candidates,
    source_name_from_url,
    translation_from_lang_id,
)

logger = logging.getLogger(__name__)


class AnimeSama(BaseAnimeProvider):
    HEADERS = REQUEST_HEADERS

    def __init__(self, client) -> None:
        super().__init__(client)
        self.base_url = normalize_base_url(ANIMESAMA_BASE_URL)
        self.catalogue_url = ANIMESAMA_CATALOGUE_URL

    @debug_provider
    def search(self, params: SearchParams) -> SearchResults | None:
        items = []
        for query in search_query_candidates(params.query):
            if query != params.query:
                logger.info(
                    "Anime-Sama search fallback query: %r -> %r",
                    params.query,
                    query,
                )
            items = self._search_items(query)
            if items:
                break
        if not items:
            return None
        return map_to_search_results(items)

    def _search_items(self, query: str):
        response = self.client.get(
            self.catalogue_url,
            params={"search": query},
            follow_redirects=True,
        )
        response.raise_for_status()
        return parse_catalogue_cards(response.text)

    @debug_provider
    def get(self, params: AnimeParams) -> Anime | None:
        return self._get_anime(params)

    @lru_cache()
    def _search_result(self, params: AnimeParams) -> SearchResult | None:
        search_results = self.search(SearchParams(query=params.query))
        if not search_results:
            return None
        return next(
            (result for result in search_results.results if result.id == params.id),
            None,
        )

    @lru_cache()
    def _get_anime(self, params: AnimeParams) -> Anime | None:
        search_result = self._search_result(params)
        if not search_result:
            logger.error("No Anime-Sama search result found for ID %s", params.id)
            return None

        response = self.client.get(
            f"{self.catalogue_url}{params.id}/",
            follow_redirects=True,
        )
        response.raise_for_status()
        page = response.text
        catalogue_item = parse_catalogue_item(page, params.id)
        season_links = filter_season_links_for_query(
            parse_season_links(page, params.id, self.base_url),
            params.query,
        )

        episodes = self._load_episodes(params.id, season_links)
        if not episodes:
            return Anime(
                id=search_result.id,
                title=search_result.title,
                episodes=search_result.episodes,
                poster=catalogue_item["poster"]
                if catalogue_item
                else search_result.poster,
            )

        episodes.sort(key=lambda episode: self._episode_sort_key(episode["episode"]))
        return map_to_anime_result(
            search_result,
            episodes,
            poster=catalogue_item["poster"] if catalogue_item else search_result.poster,
        )

    def _load_episodes(
        self,
        slug: str,
        season_links: list[AnimeSamaSeasonLink],
    ) -> list[AnimeSamaEpisodeEntry]:
        merged_episodes: list[AnimeSamaEpisodeEntry] = []
        by_season: dict[str, list[AnimeSamaSeasonLink]] = {}
        for link in season_links:
            by_season.setdefault(link["season"], []).append(link)

        for links in by_season.values():
            pages = {
                link["lang_id"]: self._load_season_lang_page(
                    link["url"],
                    link["lang_id"],
                )
                for link in links
            }
            if "vostfr" in pages and (
                missing_lang := detect_missing_lang_id(pages["vostfr"][0])
            ):
                pages.setdefault(missing_lang, pages["vostfr"])

            players_by_lang = {
                lang_id: extract_players(script)
                for lang_id, (_, script) in pages.items()
                if script and translation_from_lang_id(lang_id)
            }
            if not players_by_lang:
                continue

            max_episodes = max(len(players) for players in players_by_lang.values())
            for lang_id, (html_page, _) in pages.items():
                if lang_id not in players_by_lang:
                    continue
                episode_names = extract_episode_names(
                    html_page,
                    len(players_by_lang[lang_id]),
                    max_episodes,
                )
                merged_episodes = merge_episode_languages(
                    merged_episodes,
                    episode_names,
                    players_by_lang[lang_id],
                    lang_id,
                )

        return merged_episodes

    @lru_cache()
    def _load_season_lang_page(self, season_url: str, lang_id: str) -> tuple[str, str]:
        page_url = f"{season_url}{lang_id}/"
        response = self.client.get(page_url, follow_redirects=True)
        response.raise_for_status()
        html_page = response.text
        script_path = episode_script_path(html_page)
        if not script_path:
            return html_page, ""

        script_response = self.client.get(
            f"{page_url}{script_path}",
            follow_redirects=True,
        )
        script_response.raise_for_status()
        return html_page, script_response.text

    def _episode_sort_key(self, value: str) -> tuple[int, float]:
        if re.fullmatch(r"\d+(?:\.\d+)?", value):
            return 0, float(value)
        return 1, float("inf")

    @lru_cache()
    def _get_episode_info(
        self, params: EpisodeStreamsParams
    ) -> AnimeEpisodeInfo | None:
        anime = self._get_anime(AnimeParams(id=params.anime_id, query=params.query))
        if not anime or not anime.episodes_info:
            return None
        return next(
            (
                episode
                for episode in anime.episodes_info
                if episode.episode == params.episode
            ),
            None,
        )

    @lru_cache()
    def _get_episode_sources(
        self, params: EpisodeStreamsParams
    ) -> dict[str, list[str]]:
        page = self.client.get(
            f"{self.catalogue_url}{params.anime_id}/",
            follow_redirects=True,
        )
        page.raise_for_status()
        season_links = filter_season_links_for_query(
            parse_season_links(page.text, params.anime_id, self.base_url),
            params.query,
        )
        episodes = self._load_episodes(params.anime_id, season_links)
        for episode in episodes:
            if episode["episode"] == params.episode:
                sources: dict[str, list[str]] = {}
                for lang_id, source in episode["sources"].items():
                    translation = translation_from_lang_id(lang_id)
                    if translation:
                        sources.setdefault(translation, []).extend(source["players"])
                return sources
        return {}

    @debug_provider
    def episode_streams(self, params: EpisodeStreamsParams) -> Iterator[Server] | None:
        episode_info = self._get_episode_info(params)
        if not episode_info:
            logger.error(
                "Episode %s doesn't exist for Anime-Sama anime %s",
                params.episode,
                params.anime_id,
            )
            return None

        sources = self._get_episode_sources(params)
        for url in sources.get(params.translation_type, []):
            yield map_to_server(
                source_name_from_url(url),
                url,
                params.translation_type,
                episode_info.title,
            )


if __name__ == "__main__":
    from ..utils.debug import test_anime_provider

    test_anime_provider(AnimeSama)
