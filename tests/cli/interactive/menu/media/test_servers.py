from viu_media.cli.interactive.menu.media.servers import _collect_servers


def test_collect_servers_returns_empty_list_for_empty_top_iterator() -> None:
    assert _collect_servers(iter(()), use_top_server=True) == []


def test_collect_servers_returns_first_server_for_top_iterator() -> None:
    assert _collect_servers(iter(["kwik", "backup"]), use_top_server=True) == ["kwik"]


def test_collect_servers_returns_all_servers_when_top_is_disabled() -> None:
    assert _collect_servers(iter(["kwik", "backup"]), use_top_server=False) == [
        "kwik",
        "backup",
    ]
