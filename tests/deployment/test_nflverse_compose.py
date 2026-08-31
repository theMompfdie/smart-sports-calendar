from pathlib import Path


def test_compose_forwards_all_nflverse_settings() -> None:
    compose = (Path(__file__).parents[2] / "docker-compose.yml").read_text(
        encoding="utf-8"
    )
    expected_settings = {
        "NFLVERSE_ENABLED": "false",
        "NFLVERSE_CONNECT_TIMEOUT_SECONDS": "5",
        "NFLVERSE_READ_TIMEOUT_SECONDS": "30",
        "NFLVERSE_MAX_ATTEMPTS": "3",
        "NFLVERSE_MAX_REDIRECTS": "3",
        "NFLVERSE_MINIMUM_POLL_INTERVAL_SECONDS": "21600",
    }

    for setting, default in expected_settings.items():
        assert f"{setting}: ${{{setting}:-{default}}}" in compose
