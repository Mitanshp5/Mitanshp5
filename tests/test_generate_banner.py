import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "generate_banner.py"


def load_module():
    spec = importlib.util.spec_from_file_location("generate_banner", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_banner_uses_the_track_cover_instead_of_the_generic_mask():
    module = load_module()
    track_cover = "data:image/jpeg;base64,dHJhY2stY292ZXI="

    svg = module.banner(
        {
            "title": "A Live Track",
            "artist": "An Artist",
            "mode": "NOW PLAYING · SPOTIFY",
            "cover": track_cover,
        }
    )

    assert track_cover in svg
    assert 'x="122" y="215" width="328" height="328"' in svg
    assert 'M282 260 C208 284' not in svg
    assert '<animate attributeName="height"' in svg
    assert 'repeatCount="indefinite"' in svg


def test_banner_truncates_long_track_text_and_uses_track_accent_color():
    module = load_module()
    long_title = "An Extremely Long Track Title That Must Never Escape The Music Card"
    long_artist = "A Very Long List Of Artists That Must Remain Inside The Music Card"

    svg = module.banner(
        {
            "title": long_title,
            "artist": long_artist,
            "mode": "NOW PLAYING · SPOTIFY",
            "cover": "data:image/jpeg;base64,dGVzdA==",
            "bar_color": "#12a4f0",
        }
    )

    assert f">{long_title}</text>" not in svg
    assert f">by {long_artist}</text>" not in svg
    assert "…" in svg
    assert 'textLength="850"' in svg
    assert 'class="artist" textLength=' not in svg
    assert '.bar { fill: #12a4f0; }' in svg


def test_now_playing_returns_spotify_album_art_url(monkeypatch):
    module = load_module()
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "id")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "secret")
    monkeypatch.setenv("SPOTIFY_REFRESH_TOKEN", "refresh")
    responses = iter(
        [
            (200, {"access_token": "access"}),
            (
                200,
                {
                    "is_playing": True,
                    "item": {
                        "name": "A Live Track",
                        "artists": [{"name": "An Artist"}],
                        "album": {"images": [{"url": "https://cover.example/live.jpg"}]},
                    },
                },
            ),
        ]
    )
    monkeypatch.setattr(module, "request_json", lambda *args, **kwargs: next(responses))

    assert module.now_playing()["cover_url"] == "https://cover.example/live.jpg"
