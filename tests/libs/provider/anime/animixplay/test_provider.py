from dataclasses import dataclass
from http import HTTPStatus
from typing import Any

from viu_media.libs.provider.anime.animixplay.provider import Animixplay
from viu_media.libs.provider.anime.params import (
    AnimeParams,
    EpisodeStreamsParams,
    SearchParams,
)


@dataclass
class FakeResponse:
    text: str = ""
    data: Any = None
    status_code: int = HTTPStatus.OK
    url: str = "https://www.animixplay.net/"

    def raise_for_status(self) -> None:
        if self.status_code >= HTTPStatus.BAD_REQUEST:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> Any:
        return self.data


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


SEARCH_JSON = [
    {
        "id": 6256,
        "title": "One Piece",
        "url": "https://www.animixplay.net/anime/one-piece-2025/",
        "subtype": "anime",
    }
]

ANIME_DETAIL_HTML = """
<div class="single-info bixbox">
  <div class="thumb">
    <img data-src="https://cdn.example/one-piece.jpg" />
  </div>
  <div class="infox">
    <div class="infolimit"><h2 itemprop="partOfSeries">One Piece</h2>
      <span class="alter">One Piece, OP, ONE PIECE</span>
    </div>
    <div class="info-content"><div class="spe">
      <span><b>Status:</b> Ongoing</span>
      <span class="split"><b>Released:</b> 1999</span>
      <span><b>Type:</b> TV</span>
    </div></div>
  </div>
</div>
"""

EPISODE_SEARCH_HTML = """
<article class="bs"><div class="bsx">
<a href="https://www.animixplay.net/one-piece-episode-1-english-subbed/" itemprop="url" title="One Piece Episode 1 English Subbed" class="tip" rel="1">
<div class="tt">One Piece<h2 itemprop="headline">One Piece Episode 1 English Subbed</h2></div>
</a></div></article>
<article class="bs"><div class="bsx">
<a href="https://www.animixplay.net/one-piece-episode-2-english-dubbed/" itemprop="url" title="One Piece Episode 2 English Dubbed" class="tip" rel="2">
<div class="tt">One Piece<h2 itemprop="headline">One Piece Episode 2 English Dubbed</h2></div>
</a></div></article>
"""

EMPTY_SEARCH_HTML = "<html><body>No more results</body></html>"

EPISODE_PAGE_HTML = """
<h1 class="entry-title" itemprop="name">One Piece Episode 1 English Subbed</h1>
<span class="epx"> TV <span class="lg">Sub</span></span>
<div class="video-content">
  <div id="embed_holder" class="lowvid">
    <div class="player-embed" id="pembed">
      <iframe loading="lazy" src="https://megaplay.buzz/stream/s-2/161461/sub" height="380" width="100%"></iframe>
    </div>
  </div>
</div>
<select class="mirror" name="mirror">
  <option value="">Select Video Server</option>
  <option value="PGlmcmFtZSBzcmM9Imh0dHBzOi8vbWlycm9yLmV4YW1wbGUvc3RyZWFtLzEiPjwvaWZyYW1lPg==" data-index="1">Video</option>
  <option value="PGNlbnRlcj5WaWRlbyBOb3QgQXZhaWxhYmxlPC9jZW50ZXI+" data-index="2">Video</option>
</select>
"""

HTML_SEARCH_FALLBACK = """
<div class="listupd">
  <article class="bs"><div class="bsx">
    <a href="https://www.animixplay.net/anime/kanojo-okarishimasu-4th-season/" itemprop="url" title="Kanojo, Okarishimasu 4th Season" class="tip" rel="4361">
      <div class="tt">
        Kanojo, Okarishimasu 4th Season
        <h2 itemprop="headline">Kanojo, Okarishimasu 4th Season</h2>
      </div>
    </a>
  </div></article>
</div>
"""

SEASONLESS_EPISODE_SEARCH_HTML = """
<article class="bs"><div class="bsx">
<a href="https://www.animixplay.net/rent-a-girlfriend-episode-1-english-subbed/" itemprop="url" title="Rent-a-Girlfriend Episode 1 English Subbed" class="tip" rel="10">
<div class="tt">Rent-a-Girlfriend<h2 itemprop="headline">Rent-a-Girlfriend Episode 1 English Subbed</h2></div>
</a></div></article>
<article class="bs"><div class="bsx">
<a href="https://www.animixplay.net/rent-a-girlfriend-episode-2-english-dubbed/" itemprop="url" title="Rent-a-Girlfriend Episode 2 English Dubbed" class="tip" rel="11">
<div class="tt">Rent-a-Girlfriend<h2 itemprop="headline">Rent-a-Girlfriend Episode 2 English Dubbed</h2></div>
</a></div></article>
"""


def test_search_uses_wp_json_and_caches_anime_url() -> None:
    provider = Animixplay(FakeClient([FakeResponse(data=SEARCH_JSON)]))

    results = provider.search(SearchParams(query="One Piece"))

    assert results is not None
    assert [result.title for result in results.results] == ["One Piece"]
    assert (
        provider._anime_url_cache["6256"]
        == "https://www.animixplay.net/anime/one-piece-2025/"
    )


def test_search_falls_back_to_html_when_wp_json_returns_no_results() -> None:
    provider = Animixplay(
        FakeClient(
            [
                FakeResponse(data=[]),
                FakeResponse(text=HTML_SEARCH_FALLBACK),
            ]
        )
    )

    results = provider.search(SearchParams(query="Rent-a-Girlfriend Season 4"))

    assert results is not None
    assert [result.title for result in results.results] == [
        "Kanojo, Okarishimasu 4th Season"
    ]
    assert provider._anime_url_cache["4361"] == (
        "https://www.animixplay.net/anime/kanojo-okarishimasu-4th-season/"
    )


def test_get_parses_anime_details_and_splits_sub_and_dub_episodes() -> None:
    provider = Animixplay(
        FakeClient(
            [
                FakeResponse(data=SEARCH_JSON),
                FakeResponse(text=ANIME_DETAIL_HTML),
                FakeResponse(text=EPISODE_SEARCH_HTML),
                FakeResponse(text=EMPTY_SEARCH_HTML),
                FakeResponse(text=EMPTY_SEARCH_HTML),
            ]
        )
    )

    anime = provider.get(AnimeParams(id="6256", query="One Piece"))

    assert anime is not None
    assert anime.title == "One Piece"
    assert anime.poster == "https://cdn.example/one-piece.jpg"
    assert anime.episodes.sub == ["1"]
    assert anime.episodes.dub == ["2"]


def test_get_falls_back_to_search_result_when_detail_page_has_no_anime_metadata() -> (
    None
):
    provider = Animixplay(
        FakeClient(
            [
                FakeResponse(
                    data=[],
                ),
                FakeResponse(text=HTML_SEARCH_FALLBACK),
                FakeResponse(text="<html><body>Homepage fallback</body></html>"),
                FakeResponse(text=EMPTY_SEARCH_HTML),
            ]
        )
    )

    anime = provider.get(AnimeParams(id="4361", query="Rent-a-Girlfriend Season 4"))

    assert anime is not None
    assert anime.title == "Kanojo, Okarishimasu 4th Season"
    assert anime.episodes.sub == []
    assert anime.episodes_info == []


def test_get_stops_cleanly_when_episode_search_pagination_ends_with_http_error() -> (
    None
):
    provider = Animixplay(
        FakeClient(
            [
                FakeResponse(data=SEARCH_JSON),
                FakeResponse(text=ANIME_DETAIL_HTML),
                FakeResponse(text=EPISODE_SEARCH_HTML),
                FakeResponse(text="", status_code=HTTPStatus.NOT_FOUND),
            ]
        )
    )

    anime = provider.get(AnimeParams(id="6256", query="One Piece"))

    assert anime is not None
    assert anime.title == "One Piece"
    assert anime.episodes.sub == ["1"]
    assert anime.episodes.dub == ["2"]


def test_get_retries_episode_discovery_with_seasonless_title_variants() -> None:
    provider = Animixplay(
        FakeClient(
            [
                FakeResponse(data=[]),
                FakeResponse(text=HTML_SEARCH_FALLBACK),
                FakeResponse(text="<html><body>Homepage fallback</body></html>"),
                FakeResponse(text=EMPTY_SEARCH_HTML),
                FakeResponse(text=SEASONLESS_EPISODE_SEARCH_HTML),
            ]
        )
    )

    anime = provider.get(AnimeParams(id="4361", query="Rent-a-Girlfriend Season 4"))

    assert anime is not None
    assert anime.episodes.sub == ["1"]
    assert anime.episodes.dub == ["2"]
    search_urls = [
        call["url"] for call in provider.client.calls if isinstance(call["url"], str)
    ]
    assert any("4th+Season+Episode" in url for url in search_urls)
    assert any("Okarishimasu" in url and "Episode" in url for url in search_urls)


def test_episode_streams_extracts_primary_and_mirror_iframe_links() -> None:
    provider = Animixplay(
        FakeClient(
            [
                FakeResponse(data=SEARCH_JSON),
                FakeResponse(text=ANIME_DETAIL_HTML),
                FakeResponse(text=EPISODE_SEARCH_HTML),
                FakeResponse(text=EMPTY_SEARCH_HTML),
                FakeResponse(text=EMPTY_SEARCH_HTML),
                FakeResponse(text=EPISODE_PAGE_HTML),
            ]
        )
    )

    servers = list(
        provider.episode_streams(
            EpisodeStreamsParams(
                anime_id="6256",
                query="One Piece",
                episode="1",
                translation_type="sub",
            )
        )
    )

    assert len(servers) == 1
    assert [link.link for link in servers[0].links] == [
        "https://megaplay.buzz/stream/s-2/161461/sub",
        "https://mirror.example/stream/1",
    ]


def test_episode_streams_returns_empty_when_translation_does_not_match() -> None:
    provider = Animixplay(
        FakeClient(
            [
                FakeResponse(data=SEARCH_JSON),
                FakeResponse(text=ANIME_DETAIL_HTML),
                FakeResponse(text=EPISODE_SEARCH_HTML),
                FakeResponse(text=EMPTY_SEARCH_HTML),
                FakeResponse(text=EMPTY_SEARCH_HTML),
                FakeResponse(text=EPISODE_PAGE_HTML),
            ]
        )
    )

    servers = list(
        provider.episode_streams(
            EpisodeStreamsParams(
                anime_id="6256",
                query="One Piece",
                episode="1",
                translation_type="dub",
            )
        )
    )

    assert servers == []
