import logging
import signal
from datetime import UTC, datetime
from threading import Event
from types import FrameType

from app.config.settings import Settings, load_settings
from app.database.database import Database
from app.graph.authentication import GraphTokenProvider
from app.graph.client import GraphClient
from app.logging.logger import configure_logging
from app.scheduler.scheduler import Scheduler


class ApplicationContainer:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or load_settings()
        self.logger: logging.Logger = configure_logging(self.settings.log_level)

        self.database = Database(self.settings.database_path)
        self.graph_token_provider = GraphTokenProvider(
            tenant_id=self.settings.m365_tenant_id,
            client_id=self.settings.m365_client_id,
            client_secret=self.settings.m365_client_secret,
        )
        self.graph_client = GraphClient(
            base_url=self.settings.graph_base_url,
            user_id=self.settings.m365_user_id,
            token_provider=self.graph_token_provider,
        )
        self.scheduler = Scheduler(
            interval_seconds=self.settings.heartbeat_interval,
            logger=self.logger,
        )
        self.stop_event = Event()

    def run(self) -> None:
        self._register_signal_handlers()

        self.database.initialize()
        self.database.record_startup()

        self.logger.info("SMART Sports Calendar container started")
        self.logger.info("Database path: %s", self.settings.database_path)

        self.graph_token_provider.get_access_token()
        self.logger.info("Microsoft Graph authentication successful")

        calendar = self.graph_client.find_calendar_by_name(
            self.settings.outlook_calendar_name
        )
        self.logger.info(
            "Outlook calendar reachable: %s",
            calendar.name,
        )

        self.scheduler.run(
            task=self._heartbeat,
            stop_event=self.stop_event,
        )

        self.logger.info("SMART Sports Calendar container stopped")

    def _register_signal_handlers(self) -> None:
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)

    def _handle_shutdown(
        self,
        signum: int,
        _frame: FrameType | None,
    ) -> None:
        signal_name = signal.Signals(signum).name
        self.logger.info("Shutdown signal received: %s", signal_name)
        self.stop_event.set()

    def _heartbeat(self) -> None:
        self.logger.info(
            "Heartbeat: %s",
            datetime.now(UTC).isoformat(),
        )
