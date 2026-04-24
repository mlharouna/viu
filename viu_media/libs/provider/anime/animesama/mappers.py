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
from .types import AnimeSamaCatalogueItem, AnimeSamaEpisodeEntry


def map_to_search_results(data: list[AnimeSamaCatalogueItem]) -> SearchResults:
    return SearchResults(
        page_info=PageInfo(total=len(data)),
        results=[
            SearchResult(
                id=item["id"],
                title=item["title"],
                episodes=AnimeEpisodes(
                    sub=[],
                    dub=[],
                ),
                other_titles=item["other_titles"],
                poster=item["poster"],
            )
            for item in data
        ],
    )


def map_to_anime_result(
    search_result: SearchResult,
    episodes: list[AnimeSamaEpisodeEntry],
    poster: str | None = None,
) -> Anime:
    sub_episodes = [
        episode["episode"]
        for episode in episodes
        if any(lang.startswith("vo") for lang in episode["sources"])
    ]
    dub_episodes = [
        episode["episode"]
        for episode in episodes
        if any(lang.startswith("vf") for lang in episode["sources"])
    ]

    return Anime(
        id=search_result.id,
        title=search_result.title,
        episodes=AnimeEpisodes(sub=sub_episodes, dub=dub_episodes),
        episodes_info=[
            AnimeEpisodeInfo(
                id=f"{search_result.id}:{episode['episode']}",
                episode=episode["episode"],
                title=episode["title"],
            )
            for episode in episodes
        ],
        poster=poster or search_result.poster,
    )


def map_to_server(
    name: str,
    url: str,
    translation_type: str,
    episode_title: str | None,
) -> Server:
    return Server(
        name=name,
        links=[
            EpisodeStream(
                link=url,
                quality="1080",
                translation_type=MediaTranslationType(translation_type),
                hls=url.endswith(".m3u8"),
                mp4=url.endswith(".mp4"),
            )
        ],
        episode_title=episode_title,
    )
