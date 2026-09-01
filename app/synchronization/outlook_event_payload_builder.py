from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.database.synchronization_query_repository import SynchronizationEvent
from app.synchronization.outlook_html_event_body_renderer import (
    OutlookHtmlEventBodyRenderer,
)


@dataclass(frozen=True)
class OutlookDateTime:
    date_time: str
    time_zone: str

    def to_graph_dict(self) -> dict[str, str]:
        return {"dateTime": self.date_time, "timeZone": self.time_zone}


@dataclass(frozen=True)
class OutlookEventPresentation:
    fallback_category: str = "SMART Sports Calendar"
    reminder_minutes_before_start: int = 15
    default_duration_minutes: int = 120
    fallback_duration_minutes_by_sport: tuple[tuple[str, int], ...] = (
        ("american_football", 180),
    )
    show_as: str = "busy"
    cancelled_prefix: str = "[CANCELLED]"

    def __post_init__(self) -> None:
        if (
            not self.fallback_category
            or self.fallback_category != self.fallback_category.strip()
        ):
            raise ValueError("Fallback category must be normalized and non-empty.")
        if self.reminder_minutes_before_start < 0:
            raise ValueError("Reminder minutes must not be negative.")
        if self.default_duration_minutes <= 0:
            raise ValueError("Default duration minutes must be positive.")
        sport_keys: set[str] = set()
        for sport_key, duration_minutes in self.fallback_duration_minutes_by_sport:
            if not sport_key or sport_key != sport_key.strip():
                raise ValueError("Fallback-duration sport keys must be normalized.")
            if sport_key in sport_keys:
                raise ValueError("Fallback-duration sport keys must be unique.")
            if duration_minutes <= 0:
                raise ValueError("Fallback duration minutes must be positive.")
            sport_keys.add(sport_key)

    def fallback_duration_minutes_for(self, sport_key: str) -> int:
        return next(
            (
                duration_minutes
                for configured_sport_key, duration_minutes in (
                    self.fallback_duration_minutes_by_sport
                )
                if configured_sport_key == sport_key
            ),
            self.default_duration_minutes,
        )


@dataclass(frozen=True)
class OutlookEventPayload:
    subject: str
    body: str
    start: OutlookDateTime
    end: OutlookDateTime | None
    location: str | None
    categories: tuple[str, ...]
    is_all_day: bool
    is_reminder_on: bool
    reminder_minutes_before_start: int
    show_as: str
    body_content_type: Literal["html", "text"] = "html"

    def to_graph_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "subject": self.subject,
            "body": {"contentType": self.body_content_type, "content": self.body},
            "start": self.start.to_graph_dict(),
            "categories": list(self.categories),
            "isAllDay": self.is_all_day,
            "isReminderOn": self.is_reminder_on,
            "reminderMinutesBeforeStart": self.reminder_minutes_before_start,
            "showAs": self.show_as,
        }

        if self.end is not None:
            payload["end"] = self.end.to_graph_dict()

        if self.location is not None:
            payload["location"] = {"displayName": self.location}

        return payload


class OutlookEventPayloadBuilder:
    def __init__(
        self,
        presentation: OutlookEventPresentation | None = None,
        body_renderer: OutlookHtmlEventBodyRenderer | None = None,
    ) -> None:
        self._presentation = presentation or OutlookEventPresentation()
        self._body_renderer = body_renderer or OutlookHtmlEventBodyRenderer()

    def build(self, synchronization_event: SynchronizationEvent) -> OutlookEventPayload:
        event = synchronization_event.event
        is_cancelled = event.status.casefold() == "cancelled"
        start = self._build_date_time(event.start_time, event.timezone)
        location = self._build_location(
            event.venue_name,
            event.city,
            event.country_code,
        )

        return OutlookEventPayload(
            subject=self._build_subject(
                event.title,
                synchronization_event.sport.icon,
                is_cancelled,
            ),
            body=self._body_renderer.render(
                synchronization_event,
                is_cancelled=is_cancelled,
                location=location,
            ),
            start=start,
            end=(
                self._build_date_time(event.end_time, event.timezone)
                if event.end_time is not None
                else self._build_fallback_end(
                    event.start_time,
                    event.timezone,
                    self._presentation.fallback_duration_minutes_for(
                        synchronization_event.sport.sport_key
                    ),
                )
            ),
            location=location,
            categories=self._build_categories(synchronization_event),
            is_all_day=False,
            is_reminder_on=True,
            reminder_minutes_before_start=(
                self._presentation.reminder_minutes_before_start
            ),
            show_as="free" if is_cancelled else self._presentation.show_as,
        )

    def _build_subject(
        self,
        title: str,
        sport_icon: str | None,
        is_cancelled: bool,
    ) -> str:
        normalized_icon = sport_icon.strip() if sport_icon is not None else ""
        subject = f"{normalized_icon} {title}" if normalized_icon else title

        if not is_cancelled:
            return subject

        return f"{self._presentation.cancelled_prefix} {subject}"

    def _build_categories(
        self,
        synchronization_event: SynchronizationEvent,
    ) -> tuple[str, ...]:
        competition = synchronization_event.competition
        if competition is not None and competition.name.strip():
            return (competition.name,)

        return (self._presentation.fallback_category,)

    @staticmethod
    def _build_date_time(value: str, time_zone: str) -> OutlookDateTime:
        try:
            zone = ZoneInfo(time_zone)
        except ZoneInfoNotFoundError as error:
            raise ValueError(f"Unknown event time zone: {time_zone}") from error

        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as error:
            raise ValueError(f"Invalid event date-time: {value}") from error

        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(zone).replace(tzinfo=None)

        return OutlookDateTime(
            date_time=parsed.isoformat(timespec="seconds"),
            time_zone=time_zone,
        )

    def _build_fallback_end(
        self,
        start_value: str,
        time_zone: str,
        duration_minutes: int,
    ) -> OutlookDateTime:
        try:
            zone = ZoneInfo(time_zone)
        except ZoneInfoNotFoundError as error:
            raise ValueError(f"Unknown event time zone: {time_zone}") from error

        try:
            parsed_start = datetime.fromisoformat(start_value)
        except ValueError as error:
            raise ValueError(f"Invalid event date-time: {start_value}") from error

        if parsed_start.tzinfo is None:
            zoned_start = parsed_start.replace(tzinfo=zone)
        else:
            zoned_start = parsed_start.astimezone(zone)

        end = (
            zoned_start.astimezone(UTC) + timedelta(minutes=duration_minutes)
        ).astimezone(zone)
        return OutlookDateTime(
            date_time=end.replace(tzinfo=None).isoformat(timespec="seconds"),
            time_zone=time_zone,
        )

    @staticmethod
    def _build_location(*parts: str | None) -> str | None:
        values = tuple(value.strip() for value in parts if value and value.strip())
        return ", ".join(dict.fromkeys(values)) or None
