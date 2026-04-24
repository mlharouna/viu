from viu_media.libs.provider.anime.provider import create_provider
from viu_media.libs.provider.anime.types import ProviderName


def test_create_provider_loads_animesama() -> None:
    provider = create_provider(ProviderName.ANIMESAMA)

    assert provider.__class__.__name__ == "AnimeSama"
