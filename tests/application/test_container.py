from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.application.container import ApplicationContainer
from app.config.settings import ApiFootballSettings, Settings
from app.database.synchronization_query_repository import (
    SynchronizationQueryRepository,
)
from app.synchronization.event_synchronizer import EventSynchronizer
from app.synchronization.outlook_event_payload_builder import (
    OutlookEventPayloadBuilder,
)
from app.synchronization.synchronization_orchestrator import (
    SynchronizationOrchestrator,
)
from app.synchronization.synchronization_runtime_service import (
    SynchronizationRuntimeService,
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
        outlook_calendar_id="calendar-1",
        synchronization_batch_limit=100,
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
    api_football_source = container.data_sources_repository.get_by_key("api_football")
    assert api_football_source is not None
    assert api_football_source.is_active is False
    assert api_football_source.metadata == {
        "api_version_family": "v3",
        "authentication": "x-apisports-key",
        "provider": "API-Football",
    }

    scheduler_run.assert_called_once_with(
        task=container._run_synchronization,
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


def test_container_disables_api_football_client_by_default(
    tmp_path: Path,
) -> None:
    container = ApplicationContainer(
        settings=create_settings(tmp_path / "sports.db"),
    )

    assert container.api_football_client is None
    assert container.api_football_catalog_adapter is None
    assert container.api_football_catalog_service is None
    assert container.api_football_fixture_adapter is None
    assert container.api_football_fixture_normalization_service is None


def test_container_provides_enabled_api_football_client(
    tmp_path: Path,
) -> None:
    settings = create_settings(tmp_path / "sports.db")
    enabled_settings = replace(
        settings,
        api_football=ApiFootballSettings(
            enabled=True,
            api_key="provider-secret",
        ),
    )

    container = ApplicationContainer(settings=enabled_settings)

    assert container.api_football_client is not None
    assert container.api_football_client._settings is enabled_settings.api_football
    assert container.api_football_catalog_adapter is not None
    assert container.api_football_catalog_service is not None
    assert container.api_football_fixture_adapter is not None
    assert container.api_football_fixture_normalization_service is not None


def test_container_never_logs_api_football_key(
    tmp_path: Path,
) -> None:
    settings = replace(
        create_settings(tmp_path / "sports.db"),
        api_football=ApiFootballSettings(
            enabled=True,
            api_key="provider-secret",
        ),
    )
    container = ApplicationContainer(settings=settings)
    container.logger = MagicMock()

    with (
        patch.object(container, "_register_signal_handlers"),
        patch.object(container.scheduler, "run"),
    ):
        container.run()

    assert "provider-secret" not in str(container.logger.method_calls)


def test_run_registers_enabled_api_football_source_without_live_call(
    tmp_path: Path,
) -> None:
    settings = replace(
        create_settings(tmp_path / "sports.db"),
        api_football=ApiFootballSettings(
            enabled=True,
            api_key="provider-secret",
        ),
    )
    container = ApplicationContainer(settings=settings)

    with (
        patch.object(container, "_register_signal_handlers"),
        patch.object(container.scheduler, "run"),
        patch.object(container.api_football_client, "get_all") as provider_get_all,
    ):
        container.run()

    source = container.data_sources_repository.get_by_key("api_football")
    assert source is not None
    assert source.is_active is True
    provider_get_all.assert_not_called()


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


def test_container_provides_synchronization_orchestrator(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "sports.db"

    container = ApplicationContainer(
        settings=create_settings(database_path),
    )

    assert isinstance(
        container.synchronization_orchestrator,
        SynchronizationOrchestrator,
    )
    assert (
        container.synchronization_orchestrator._query_repository
        is container.synchronization_query_repository
    )
    assert (
        container.synchronization_orchestrator._event_synchronizer
        is container.event_synchronizer
    )
    assert (
        container.synchronization_orchestrator._sync_runs_repository
        is container.sync_runs_repository
    )


def test_container_provides_synchronization_runtime_service(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "sports.db"

    container = ApplicationContainer(
        settings=create_settings(database_path),
    )

    assert isinstance(
        container.synchronization_runtime_service,
        SynchronizationRuntimeService,
    )
    assert (
        container.synchronization_runtime_service._orchestrator
        is container.synchronization_orchestrator
    )
    assert (
        container.synchronization_runtime_service._sync_runs_repository
        is container.sync_runs_repository
    )
    assert container.synchronization_runtime_service._logger is container.logger


def test_run_synchronization_uses_configured_calendar_and_limit(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "sports.db"
    container = ApplicationContainer(
        settings=create_settings(database_path),
    )

    with patch.object(
        container.synchronization_runtime_service,
        "run",
    ) as runtime_run:
        container._run_synchronization()

    runtime_run.assert_called_once_with(
        calendar_id="calendar-1",
        limit=100,
    )
