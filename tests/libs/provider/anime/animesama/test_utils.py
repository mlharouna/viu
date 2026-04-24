import pytest
from dataclasses import dataclass
from http import HTTPStatus

from viu_media.libs.provider.anime.animesama.provider import AnimeSama
from viu_media.libs.provider.anime.animesama.utils import (
    extract_episode_names,
    extract_players,
    filter_season_links_for_query,
    merge_episode_languages,
    normalize_search_query,
    parse_catalogue_cards,
    parse_season_links,
    requested_season_from_query,
    search_query_candidates,
)
from viu_media.libs.provider.anime.params import AnimeParams
from viu_media.libs.provider.anime.params import EpisodeStreamsParams
from viu_media.libs.provider.anime.params import SearchParams


@dataclass
class FakeResponse:
    text: str
    status_code: int = HTTPStatus.OK

    def raise_for_status(self) -> None:
        if self.status_code >= HTTPStatus.BAD_REQUEST:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeClient:
    def __init__(self, responses: list[str]) -> None:
        self._responses = [FakeResponse(text=response) for response in responses]
        self.calls: list[dict[str, object]] = []

    def get(self, url: str, **kwargs) -> FakeResponse:
        self.calls.append({"url": url, **kwargs})
        if not self._responses:
            raise AssertionError("No fake responses left")
        return self._responses.pop(0)


def test_parse_catalogue_cards_filters_to_anime() -> None:
    page = """
    <div class="shrink-0 catalog-card card-base">
      <a href="/catalogue/one-piece/">
        <img class="card-image" src="https://cdn.example/one-piece.jpg" alt="One Piece">
        <h2 class="card-title">One Piece</h2>
        <p class="alternate-titles">OP</p>
        <span class="info-label">Genres</span><p class="info-value">Action, Aventure</p>
        <span class="info-label">Types</span><p class="info-value">Anime, Scans</p>
        <span class="info-label">Langues</span><p class="info-value">VOSTFR, VF</p>
        <div class="synopsis-content">Pirates.</div>
      </a>
    </div>
    <div class="shrink-0 catalog-card card-base">
      <a href="/catalogue/one-piece/scan/vf">
        <img class="card-image" src="https://cdn.example/one-piece.jpg" alt="One Piece Scan">
        <h2 class="card-title">One Piece Scan</h2>
        <p class="alternate-titles"></p>
        <span class="info-label">Genres</span><p class="info-value">Action</p>
        <span class="info-label">Types</span><p class="info-value">Scans</p>
        <span class="info-label">Langues</span><p class="info-value">VF</p>
        <div class="synopsis-content">Scans.</div>
      </a>
    </div>
    """

    results = parse_catalogue_cards(page)

    assert len(results) == 1
    assert results[0]["id"] == "one-piece"
    assert results[0]["title"] == "One Piece"
    assert results[0]["other_titles"] == ["OP"]
    assert results[0]["languages"] == ["VOSTFR", "VF"]


def test_parse_catalogue_cards_accepts_absolute_catalogue_links() -> None:
    page = """
    <div class="shrink-0 catalog-card card-base">
      <a href="https://anime-sama.to/catalogue/one-piece/">
        <img class="card-image" src="https://cdn.example/one-piece.jpg" alt="One Piece">
        <h2 class="card-title">One Piece</h2>
        <p class="alternate-titles"></p>
        <span class="info-label">Genres</span><p class="info-value">Action, Aventure</p>
        <span class="info-label">Types</span><p class="info-value">Anime, Scans</p>
        <span class="info-label">Langues</span><p class="info-value">VOSTFR, VF</p>
        <div class="synopsis-content">Pirates.</div>
      </a>
    </div>
    """

    results = parse_catalogue_cards(page)

    assert len(results) == 1
    assert results[0]["id"] == "one-piece"
    assert results[0]["title"] == "One Piece"


def test_normalize_search_query_strips_trailing_season_number() -> None:
    assert (
        normalize_search_query("Wistoria: Wand and Sword Season 2")
        == "Wistoria: Wand and Sword"
    )


def test_normalize_search_query_strips_final_season() -> None:
    assert normalize_search_query("Attack on Titan Final Season") == "Attack on Titan"


def test_normalize_search_query_keeps_base_title() -> None:
    assert normalize_search_query("ONE PIECE") == "ONE PIECE"


def test_search_query_candidates_strip_season_and_dash_subtitle() -> None:
    assert search_query_candidates(
        "Re:ZERO -Starting Life in Another World- Season 4"
    ) == [
        "Re:ZERO -Starting Life in Another World- Season 4",
        "Re:ZERO -Starting Life in Another World",
        "Re:ZERO",
        "Re ZERO -Starting Life in Another World- Season 4",
        "Re ZERO -Starting Life in Another World",
        "Re ZERO",
    ]


def test_requested_season_from_query_extracts_numeric_suffix() -> None:
    assert requested_season_from_query("Wistoria: Wand and Sword Season 2") == "saison2"


def test_filter_season_links_for_query_keeps_only_requested_numeric_season() -> None:
    links = [
        {
            "name": "Saison 1",
            "season": "saison1",
            "lang_id": "vostfr",
            "url": "https://anime-sama.to/s1",
        },
        {
            "name": "Saison 2",
            "season": "saison2",
            "lang_id": "vostfr",
            "url": "https://anime-sama.to/s2",
        },
        {
            "name": "Saison 2 VF",
            "season": "saison2",
            "lang_id": "vf",
            "url": "https://anime-sama.to/s2vf",
        },
    ]

    filtered = filter_season_links_for_query(links, "Wistoria: Wand and Sword Season 2")

    assert [(link["season"], link["lang_id"]) for link in filtered] == [
        ("saison2", "vostfr"),
        ("saison2", "vf"),
    ]


def test_filter_season_links_for_query_uses_highest_numeric_season_for_final() -> None:
    links = [
        {
            "name": "Saison 1",
            "season": "saison1",
            "lang_id": "vostfr",
            "url": "https://anime-sama.to/s1",
        },
        {
            "name": "Saison 3",
            "season": "saison3",
            "lang_id": "vostfr",
            "url": "https://anime-sama.to/s3",
        },
        {
            "name": "Film",
            "season": "film",
            "lang_id": "vostfr",
            "url": "https://anime-sama.to/film",
        },
    ]

    filtered = filter_season_links_for_query(links, "Attack on Titan Final Season")

    assert [(link["season"], link["lang_id"]) for link in filtered] == [
        ("saison3", "vostfr")
    ]


def test_parse_season_links_prefers_old_panel_markup() -> None:
    page = """
    <script>
      panneauAnime("Saison 1", "saison1/vostfr");
      panneauAnime("Saison 1", "saison1/vf");
      panneauAnime("Saison 2", "saison2/vostfr");
    </script>
    """

    links = parse_season_links(page, "one-piece", "https://anime-sama.si")

    assert [(link["season"], link["lang_id"]) for link in links] == [
        ("saison1", "vostfr"),
        ("saison1", "vf"),
        ("saison2", "vostfr"),
    ]
    assert links[0]["url"] == "https://anime-sama.si/catalogue/one-piece/saison1/"


def test_parse_season_links_keeps_distinct_live_season_ids() -> None:
    page = """
    <script>
      panneauAnime("Saga 1 (East Blue)", "saison1/vostfr");
      panneauAnime("Saga 2 (Alabasta)", "saison2/vostfr");
      panneauAnime("Saga 12 (Elbaf)", "saison12/vostfr");
      panneauAnime("Films", "film/vostfr");
      panneauAnime("Fan Letter", "oav/vostfr");
      panneauAnime("One Piece Log: Fish-Man Island Saga", "saison1hs/vostfr");
      panneauAnime("Kai - Saga 1", "kai/vostfr");
      panneauAnime("Kai - Saga 2", "kai2/vostfr");
      panneauAnime("Saga 2 VF", "saison2/vf");
    </script>
    """

    links = parse_season_links(page, "one-piece", "https://anime-sama.to")

    assert [(link["season"], link["lang_id"]) for link in links] == [
        ("film", "vostfr"),
        ("kai", "vostfr"),
        ("kai2", "vostfr"),
        ("oav", "vostfr"),
        ("saison1", "vostfr"),
        ("saison1hs", "vostfr"),
        ("saison2", "vostfr"),
        ("saison2", "vf"),
        ("saison12", "vostfr"),
    ]
    assert any(link["name"] == "Saga 12 (Elbaf)" for link in links)


def test_extract_episode_names_handles_standard_builders() -> None:
    page = """
    <script>
      resetListe();
      creerListe(1, 2);
      newSPF("Film 1");
      finirListe(3);
    }
    </script>
    """

    names = extract_episode_names(page, number_of_episodes=4, number_of_episodes_max=4)

    assert names == ["Episode 1", "Episode 2", "Film 1", "Episode 3"]


def test_extract_players_swaps_first_two_sources() -> None:
    episodes_js = """
    var eps1 = ['https://one.example/embed-1', 'https://one.example/embed-2'];
    var eps2 = ['https://two.example/embed-1', 'https://two.example/embed-2'];
    """

    players = extract_players(episodes_js)

    assert players == [
        ["https://two.example/embed-1", "https://one.example/embed-1"],
        ["https://two.example/embed-2", "https://one.example/embed-2"],
    ]


def test_merge_episode_languages_combines_sources_by_name() -> None:
    merged = merge_episode_languages(
        [],
        ["Episode 1", "Episode 2"],
        [["https://vostfr.example/1"], ["https://vostfr.example/2"]],
        "vostfr",
        "saison1",
    )
    merged = merge_episode_languages(
        merged,
        ["Episode 1", "Episode 2"],
        [["https://vf.example/1"], ["https://vf.example/2"]],
        "vf",
        "saison1",
    )

    assert merged[0]["episode"] == "1"
    assert sorted(merged[0]["sources"]) == ["vf", "vostfr"]


def test_merge_episode_languages_keeps_same_episode_number_from_other_seasons_distinct() -> (
    None
):
    merged = merge_episode_languages(
        [],
        ["Episode 10"],
        [["https://s1.example/10"]],
        "vostfr",
        "saison1",
    )
    merged = merge_episode_languages(
        merged,
        ["Episode 10"],
        [["https://s4.example/10"]],
        "vostfr",
        "saison4",
    )

    assert [(entry["season"], entry["episode"]) for entry in merged] == [
        ("saison1", "10"),
        ("saison4", "10"),
    ]


def test_search_retries_with_normalized_query_when_original_returns_no_results() -> (
    None
):
    empty_results = "<html><body>No results</body></html>"
    matching_results = """
    <div class="shrink-0 catalog-card card-base">
      <a href="https://anime-sama.to/catalogue/tsue-to-tsurugi-no-wistoria/">
        <img class="card-image" src="https://cdn.example/wistoria.jpg" alt="Tsue To Tsurugi No Wistoria">
        <h2 class="card-title">Tsue To Tsurugi No Wistoria</h2>
        <p class="alternate-titles">Wistoria: Wand and Sword</p>
        <span class="info-label">Genres</span><p class="info-value">Action</p>
        <span class="info-label">Types</span><p class="info-value">Anime</p>
        <span class="info-label">Langues</span><p class="info-value">VOSTFR</p>
        <div class="synopsis-content">Magic.</div>
      </a>
    </div>
    """
    client = FakeClient([empty_results, matching_results])
    provider = AnimeSama(client)

    results = provider.search(SearchParams(query="Wistoria: Wand and Sword Season 2"))

    assert results is not None
    assert [result.id for result in results.results] == ["tsue-to-tsurugi-no-wistoria"]
    assert [call["params"] for call in client.calls] == [
        {"search": "Wistoria: Wand and Sword Season 2"},
        {"search": "Wistoria: Wand and Sword"},
    ]


def test_search_retries_rezero_dash_title_until_base_candidate_matches() -> None:
    empty_results = "<html><body>No results</body></html>"
    matching_results = """
    <div class="shrink-0 catalog-card card-base">
      <a href="https://anime-sama.to/catalogue/re-zero/">
        <img class="card-image" src="https://cdn.example/re-zero.jpg" alt="Re:Zero">
        <h2 class="card-title">Re:Zero</h2>
        <p class="alternate-titles">Re:ZERO,Starting Life in Another World-, ReZero</p>
        <span class="info-label">Genres</span><p class="info-value">Fantasy</p>
        <span class="info-label">Types</span><p class="info-value">Anime</p>
        <span class="info-label">Langues</span><p class="info-value">VOSTFR, VF</p>
        <div class="synopsis-content">Return by death.</div>
      </a>
    </div>
    """
    client = FakeClient([empty_results, empty_results, matching_results])
    provider = AnimeSama(client)

    results = provider.search(
        SearchParams(query="Re:ZERO -Starting Life in Another World- Season 4")
    )

    assert results is not None
    assert [result.id for result in results.results] == ["re-zero"]
    assert [call["params"] for call in client.calls] == [
        {"search": "Re:ZERO -Starting Life in Another World- Season 4"},
        {"search": "Re:ZERO -Starting Life in Another World"},
        {"search": "Re:ZERO"},
    ]


def test_search_does_not_retry_when_original_query_has_results() -> None:
    matching_results = """
    <div class="shrink-0 catalog-card card-base">
      <a href="https://anime-sama.to/catalogue/one-piece/">
        <img class="card-image" src="https://cdn.example/one-piece.jpg" alt="One Piece">
        <h2 class="card-title">One Piece</h2>
        <p class="alternate-titles">OP</p>
        <span class="info-label">Genres</span><p class="info-value">Action</p>
        <span class="info-label">Types</span><p class="info-value">Anime</p>
        <span class="info-label">Langues</span><p class="info-value">VOSTFR</p>
        <div class="synopsis-content">Pirates.</div>
      </a>
    </div>
    """
    client = FakeClient([matching_results])
    provider = AnimeSama(client)

    results = provider.search(SearchParams(query="ONE PIECE"))

    assert results is not None
    assert [result.id for result in results.results] == ["one-piece"]
    assert [call["params"] for call in client.calls] == [{"search": "ONE PIECE"}]


def test_get_filters_to_requested_season_before_loading_episodes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    empty_results = "<html><body>No results</body></html>"
    matching_results = """
    <div class="shrink-0 catalog-card card-base">
      <a href="https://anime-sama.to/catalogue/tsue-to-tsurugi-no-wistoria/">
        <img class="card-image" src="https://cdn.example/wistoria.jpg" alt="Tsue To Tsurugi No Wistoria">
        <h2 class="card-title">Tsue To Tsurugi No Wistoria</h2>
        <p class="alternate-titles">Wistoria: Wand and Sword</p>
        <span class="info-label">Genres</span><p class="info-value">Action</p>
        <span class="info-label">Types</span><p class="info-value">Anime</p>
        <span class="info-label">Langues</span><p class="info-value">VOSTFR</p>
        <div class="synopsis-content">Magic.</div>
      </a>
    </div>
    """
    catalogue_page = """
    <div class="shrink-0 catalog-card card-base">
      <a href="https://anime-sama.to/catalogue/tsue-to-tsurugi-no-wistoria/">
        <img class="card-image" src="https://cdn.example/wistoria.jpg" alt="Tsue To Tsurugi No Wistoria">
        <h2 class="card-title">Tsue To Tsurugi No Wistoria</h2>
        <p class="alternate-titles">Wistoria: Wand and Sword</p>
        <span class="info-label">Genres</span><p class="info-value">Action</p>
        <span class="info-label">Types</span><p class="info-value">Anime</p>
        <span class="info-label">Langues</span><p class="info-value">VOSTFR</p>
        <div class="synopsis-content">Magic.</div>
      </a>
    </div>
    <script>
      panneauAnime("Season 1", "saison1/vostfr");
      panneauAnime("Season 2", "saison2/vostfr");
      panneauAnime("Season 2 VF", "saison2/vf");
    </script>
    """
    client = FakeClient([empty_results, matching_results, catalogue_page])
    provider = AnimeSama(client)
    captured: dict[str, object] = {}

    def fake_load_episodes(
        slug: str, season_links: list[dict[str, str]]
    ) -> list[dict[str, object]]:
        captured["slug"] = slug
        captured["season_links"] = season_links
        return []

    monkeypatch.setattr(provider, "_load_episodes", fake_load_episodes)

    anime = provider.get(
        AnimeParams(
            id="tsue-to-tsurugi-no-wistoria",
            query="Wistoria: Wand and Sword Season 2",
        )
    )

    assert anime is not None
    assert captured["slug"] == "tsue-to-tsurugi-no-wistoria"
    assert [(link["season"], link["lang_id"]) for link in captured["season_links"]] == [
        ("saison2", "vostfr"),
        ("saison2", "vf"),
    ]


def test_episode_streams_reuses_cached_sources_for_same_query() -> None:
    matching_results = """
    <div class="shrink-0 catalog-card card-base">
      <a href="https://anime-sama.to/catalogue/rent-a-girlfriend/">
        <img class="card-image" src="https://cdn.example/rag.jpg" alt="Rent a Girlfriend">
        <h2 class="card-title">Rent a Girlfriend</h2>
        <p class="alternate-titles">Kanojo Okarishimasu</p>
        <span class="info-label">Genres</span><p class="info-value">Romance</p>
        <span class="info-label">Types</span><p class="info-value">Anime</p>
        <span class="info-label">Langues</span><p class="info-value">VOSTFR</p>
        <div class="synopsis-content">Rental romance.</div>
      </a>
    </div>
    """
    catalogue_page = """
    <div class="shrink-0 catalog-card card-base">
      <a href="https://anime-sama.to/catalogue/rent-a-girlfriend/">
        <img class="card-image" src="https://cdn.example/rag.jpg" alt="Rent a Girlfriend">
        <h2 class="card-title">Rent a Girlfriend</h2>
        <p class="alternate-titles">Kanojo Okarishimasu</p>
        <span class="info-label">Genres</span><p class="info-value">Romance</p>
        <span class="info-label">Types</span><p class="info-value">Anime</p>
        <span class="info-label">Langues</span><p class="info-value">VOSTFR</p>
        <div class="synopsis-content">Rental romance.</div>
      </a>
    </div>
    <script>
      panneauAnime("Saison 4", "saison4/vostfr");
    </script>
    """
    provider = AnimeSama(FakeClient([matching_results, catalogue_page]))

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        provider,
        "_load_episodes",
        lambda slug, season_links: [
            {
                "season": "saison4",
                "episode": "10",
                "title": "Episode 10",
                "sources": {
                    "vostfr": {
                        "name": "vidmoly.net",
                        "players": ["https://vidmoly.net/embed-10.html"],
                    }
                },
            }
        ],
    )

    anime = provider.get(
        AnimeParams(id="rent-a-girlfriend", query="Rent a Girlfriend Season 4")
    )
    assert anime is not None

    streams = list(
        provider.episode_streams(
            EpisodeStreamsParams(
                anime_id="rent-a-girlfriend",
                query="Rent a Girlfriend Season 4",
                episode="10",
                translation_type="sub",
            )
        )
    )

    monkeypatch.undo()

    assert [server.name for server in streams] == ["vidmoly.net"]
