def test_catalog_fixture_metadata_documents_provenance_and_sanitization() -> None:
    from tests.providers.api_football.catalog_test_support import load_envelope

    metadata = load_envelope("catalog_metadata.json")

    assert metadata["api_version"] == "3.9.3"
    assert metadata["prepared_on"] == "2026-08-08"
    assert "No live provider request was made" in metadata["provenance"]
    assert set(metadata["fixtures"]) == {
        "premier_league.json",
        "premier_league_teams.json",
        "premier_league_fixtures.json",
    }
    assert metadata["source_documentation"]
    assert metadata["sanitization"]
    assert "api_key" not in str(metadata).casefold()
    assert "authorization" not in str(metadata).casefold()
