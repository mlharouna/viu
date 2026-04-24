from __future__ import annotations

from html import unescape

from ..types import (
    Anime,
    AnimeEpisodeInfo,
    AnimeEpisodes,
    EpisodeStream,
    MediaTranslationType,
    PageInfo,
    SearchResult,
    SearchResults,
    Server,
)
from .extractor import clean_text


def map_to_search_results(records: list[dict]) -> SearchResults:
    results = [
        SearchResult(
            id=str(record["id"]),
            title=clean_text(record["title"]),
            episodes=AnimeEpisodes(sub=[]),
        )
        for record in records
    ]

    return SearchResults(page_info=PageInfo(total=len(results)), results=results)


def map_to_anime(
    anime_id: str,
    details: dict[str, str | list[str] | None],
    episodes: list[dict[str, str]],
) -> Anime:
    sub_episodes = [
        episode["episode"] for episode in episodes if episode["translation"] == "sub"
    ]
    dub_episodes = [
        episode["episode"] for episode in episodes if episode["translation"] == "dub"
    ]

    return Anime(
        id=anime_id,
        title=str(details["title"] or "Unknown"),
        episodes=AnimeEpisodes(sub=sub_episodes, dub=dub_episodes),
        episodes_info=[
            AnimeEpisodeInfo(
                id=episode["url"],
                episode=episode["episode"],
                title=episode["title"],
            )
            for episode in episodes
        ],
        type=str(details["type"]) if details["type"] else None,
        poster=str(details["poster"]) if details["poster"] else None,
        year=str(details["year"]) if details["year"] else None,
    )


def map_to_server(
    links: list[str],
    episode_title: str | None,
    translation_type: str,
    headers: dict[str, str],
) -> Server:
    mapped_links = [
        EpisodeStream(
            link=unescape(link),
            title=episode_title,
            quality="1080",
            translation_type=MediaTranslationType(translation_type),
        )
        for link in links
    ]

    return Server(
        name="video",
        links=mapped_links,
        episode_title=episode_title,
        headers=headers,
    )
