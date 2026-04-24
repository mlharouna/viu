from typing import TypedDict


class AnimeSamaCatalogueItem(TypedDict):
    id: str
    title: str
    other_titles: list[str]
    genres: list[str]
    types: list[str]
    languages: list[str]
    poster: str | None
    synopsis: str | None


class AnimeSamaSeasonLink(TypedDict):
    name: str
    season: str
    lang_id: str
    url: str


class AnimeSamaEpisodeSource(TypedDict):
    name: str
    players: list[str]


class AnimeSamaEpisodeEntry(TypedDict):
    season: str
    episode: str
    title: str
    sources: dict[str, AnimeSamaEpisodeSource]
