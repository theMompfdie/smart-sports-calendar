from pathlib import Path
from unittest.mock import patch

from app.application.container import ApplicationContainer
from app.config.settings import Settings
from app.database.synchronization_query_repository import (
    SynchronizationQueryRepository,
)
from app.synchronization.event_synchronizer import EventSynchronizer
from app.synchronization.outlook_event_payload_builder import (
    OutlookEventPayloadBuilder,
)


def create_settings(
    database_path: Path,
) -> Settings:
    return Settings(
        database_path=database_path,
        log_level="INFO",
        heartbeat_interval=300,
        m365_tenant_id="test-tenant",
        m365_client_id="test-client",
        m365_client_secret="test-secret",
        m365_user_id="test-user",
        outlook_calendar_name="SMART Sports Calendar",
        graph_base_url="https://graph.microsoft.com/v1.0",
        graph_startup_validation_enabled=False,
    )


def test_run_initializes_sports_catalog(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "sports.db"
    container = ApplicationContainer(
        settings=create_settings(database_path),
    )

    with (
        patch.object(container, "_register_signal_handlers"),
        patch.object(container.scheduler, "run") as scheduler_run,
    ):
        container.run()

    football = container.sports_repository.get_by_key("football")

    assert football is not None
    assert football.sport_key == "football"
    assert football.name == "Football"
    assert football.icon == "⚽"
    assert football.metadata == {
        "category": "team_sport",
    }

    scheduler_run.assert_called_once_with(
        task=container._heartbeat,
        stop_event=container.stop_event,
    )


def test_run_can_be_repeated_without_duplicate_sports(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "sports.db"
    container = ApplicationContainer(
        settings=create_settings(database_path),
    )

    with (
        patch.object(container, "_register_signal_handlers"),
        patch.object(container.scheduler, "run"),
    ):
        container.run()
        first_football = container.sports_repository.get_by_key("football")

        container.run()
        second_football = container.sports_repository.get_by_key("football")

    assert first_football is not None
    assert second_football is not None
    assert second_football.id == first_football.id
    assert second_football.created_at == first_football.created_at


def test_container_provides_synchronization_query_repository(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "sports.db"

    container = ApplicationContainer(
        settings=create_settings(database_path),
    )

    assert isinstance(
        container.synchronization_query_repository,
        SynchronizationQueryRepository,
    )

    assert container.synchronization_query_repository.database_path == database_path


def test_container_provides_event_synchronizer(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "sports.db"

    container = ApplicationContainer(
        settings=create_settings(database_path),
    )

    assert isinstance(
        container.outlook_event_payload_builder,
        OutlookEventPayloadBuilder,
    )
    assert isinstance(
        container.event_synchronizer,
        EventSynchronizer,
    )

    assert (
        container.event_synchronizer._payload_builder
        is container.outlook_event_payload_builder
    )
    assert container.event_synchronizer._graph_client is container.graph_client
    assert (
        container.event_synchronizer._mappings_repository
        is container.calendar_event_mappings_repository
    )
