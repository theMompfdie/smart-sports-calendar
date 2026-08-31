from app.database.sports_repository import Sport, SportsRepository


def initialize_sports_catalog(
    repository: SportsRepository,
) -> list[Sport]:
    return [
        repository.upsert(
            sport_key="football",
            name="Football",
            icon="⚽",
            metadata={
                "category": "team_sport",
            },
        ),
        repository.upsert(
            sport_key="american_football",
            name="American Football",
            icon="🏈",
            metadata={"category": "team_sport"},
        ),
    ]
