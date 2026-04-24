from dataclasses import dataclass
from http import HTTPStatus
from typing import Any

from viu_media.libs.provider.anime.animepahe.mappers import map_to_anime_result
from viu_media.libs.provider.anime.animepahe.provider import AnimePahe
from viu_media.libs.provider.anime.params import EpisodeStreamsParams, SearchParams
from viu_media.libs.provider.anime.types import (
    AnimeEpisodeInfo,
    AnimeEpisodes,
    SearchResult,
)


@dataclass
class FakeResponse:
    text: str = ""
    data: dict[str, Any] | None = None
    status_code: int = HTTPStatus.OK

    def raise_for_status(self) -> None:
        if self.status_code >= HTTPStatus.BAD_REQUEST:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> dict[str, Any]:
        return self.data or {}


class FakeClient:
    headers = {"User-Agent": "pytest"}

    def __init__(self, responses: list[FakeResponse]) -> None:
        self._responses = responses
        self.calls: list[dict[str, object]] = []

    def get(self, url: str, **kwargs) -> FakeResponse:
        self.calls.append({"url": url, **kwargs})
        if not self._responses:
            raise AssertionError("No fake responses left")
        return self._responses.pop(0)


def test_map_to_anime_result_splits_sub_and_dub_episodes_by_audio() -> None:
    search_result = SearchResult(
        id="rezero",
        title="Re:ZERO",
        episodes=AnimeEpisodes(sub=[], dub=[]),
    )
    anime_page = {
        "total": 2,
        "per_page": 30,
        "current_page": 1,
        "last_page": 1,
        "next_page_url": None,
        "prev_page_url": None,
        "_from": 1,
        "to": 2,
        "data": [
            {
                "id": "1",
                "anime_id": 1,
                "episode": 1,
                "episode2": 0,
                "edition": "",
                "title": "Sub Episode",
                "snapshot": "sub.jpg",
                "disc": "",
                "audio": "jpn",
                "duration": "00:24:00",
                "session": "sub-session",
                "filler": 0,
                "created_at": "",
            },
            {
                "id": "2",
                "anime_id": 1,
                "episode": 2,
                "episode2": 0,
                "edition": "",
                "title": "Dub Episode",
                "snapshot": "dub.jpg",
                "disc": "",
                "audio": "eng",
                "duration": "00:24:00",
                "session": "dub-session",
                "filler": 0,
                "created_at": "",
            },
        ],
    }

    anime = map_to_anime_result(search_result, anime_page)

    assert anime.episodes.sub == ["1"]
    assert anime.episodes.dub == ["2"]


def test_episode_streams_returns_empty_when_requested_translation_is_unavailable(
    monkeypatch,
) -> None:
    provider = AnimePahe(
        FakeClient(
            [
                FakeResponse(
                    text="""
                    <div id="resolutionMenu">
                      <a class="dropdown-item" data-src="https://kwik.cx/e/sub" data-audio="jpn" data-resolution="720"></a>
                    </div>
                    """
                )
            ]
        )
    )
    monkeypatch.setattr(
        provider,
        "_get_episode_info",
        lambda params: AnimeEpisodeInfo(
            id="1",
            session_id="episode-session",
            episode="1",
            title="Episode 1",
        ),
    )

    streams = list(
        provider.episode_streams(
            EpisodeStreamsParams(
                anime_id="rezero",
                query="Re:ZERO",
                episode="1",
                translation_type="dub",
            )
        )
    )

    assert streams == []


def test_search_returns_none_when_animepahe_serves_html_challenge() -> None:
    provider = AnimePahe(
        FakeClient(
            [
                FakeResponse(
                    text="<html><title>DDoS-Guard</title></html>",
                    data=None,
                )
            ]
        )
    )

    results = provider.search(SearchParams(query="Rent-a-Girlfriend Season 4"))

    assert results is None
