from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.database.event_results_repository import EventResult
from app.database.event_statistics_repository import EventStatistic
from app.database.synchronization_query_repository import (
    SynchronizationEvent,
    SynchronizationParticipant,
)


@dataclass(frozen=True)
class OutlookDateTime:
    date_time: str
    time_zone: str

    def to_graph_dict(self) -> dict[str, str]:
        return {"dateTime": self.date_time, "timeZone": self.time_zone}


@dataclass(frozen=True)
class OutlookEventPresentation:
    categories: tuple[str, ...] = ("SMART Sports Calendar",)
    reminder_minutes_before_start: int = 15
    default_duration_minutes: int = 120
    show_as: str = "busy"
    cancelled_prefix: str = "[CANCELLED]"
    cancelled_category: str = "Cancelled"

    def __post_init__(self) -> None:
        if self.reminder_minutes_before_start < 0:
            raise ValueError("Reminder minutes must not be negative.")
        if self.default_duration_minutes <= 0:
            raise ValueError("Default duration minutes must be positive.")


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

    def to_graph_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "subject": self.subject,
            "body": {"contentType": "text", "content": self.body},
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
    ) -> None:
        self._presentation = presentation or OutlookEventPresentation()

    def build(self, synchronization_event: SynchronizationEvent) -> OutlookEventPayload:
        event = synchronization_event.event
        is_cancelled = event.status.casefold() == "cancelled"
        start = self._build_date_time(event.start_time, event.timezone)

        return OutlookEventPayload(
            subject=self._build_subject(event.title, is_cancelled),
            body=self._build_body(synchronization_event, is_cancelled),
            start=start,
            end=(
                self._build_date_time(event.end_time, event.timezone)
                if event.end_time is not None
                else self._build_fallback_end(event.start_time, event.timezone)
            ),
            location=self._build_location(
                event.venue_name,
                event.city,
                event.country_code,
            ),
            categories=self._build_categories(synchronization_event, is_cancelled),
            is_all_day=False,
            is_reminder_on=True,
            reminder_minutes_before_start=(
                self._presentation.reminder_minutes_before_start
            ),
            show_as="free" if is_cancelled else self._presentation.show_as,
        )

    def _build_subject(self, title: str, is_cancelled: bool) -> str:
        if not is_cancelled:
            return title

        return f"{self._presentation.cancelled_prefix} {title}"

    def _build_body(
        self,
        synchronization_event: SynchronizationEvent,
        is_cancelled: bool,
    ) -> str:
        event = synchronization_event.event
        lines = [
            f"Status: {'Cancelled' if is_cancelled else event.status}",
            f"Sport: {synchronization_event.sport.name}",
        ]

        if synchronization_event.competition is not None:
            lines.append(f"Competition: {synchronization_event.competition.name}")
        if synchronization_event.season is not None:
            lines.append(f"Season: {synchronization_event.season.name}")
        if synchronization_event.parent_event is not None:
            lines.append(f"Parent event: {synchronization_event.parent_event.title}")
        if event.stage is not None:
            lines.append(f"Stage: {event.stage}")
        if event.round_name is not None:
            lines.append(f"Round: {event.round_name}")

        participants = sorted(
            synchronization_event.participants,
            key=self._participant_sort_key,
        )
        if participants:
            lines.extend(("", "Participants:"))
            lines.extend(
                f"- {participant.role}: {participant.participant.name}"
                for participant in participants
            )

        participant_names = {
            participant.participant.id: participant.participant.name
            for participant in synchronization_event.participants
        }
        results = sorted(synchronization_event.results, key=self._result_sort_key)
        if results:
            lines.extend(("", "Results:"))
            lines.extend(
                self._render_result(result, participant_names) for result in results
            )

        statistics = sorted(
            synchronization_event.statistics,
            key=self._statistic_sort_key,
        )
        if statistics:
            lines.extend(("", "Statistics:"))
            lines.extend(
                self._render_statistic(statistic, participant_names)
                for statistic in statistics
            )

        if synchronization_event.operator_notice is not None:
            lines.extend(("", f"Notice: {synchronization_event.operator_notice.text}"))

        if synchronization_event.source_attribution is not None:
            lines.extend(("", f"Source: {synchronization_event.source_attribution}"))

        return "\n".join(lines)

    def _build_categories(
        self,
        synchronization_event: SynchronizationEvent,
        is_cancelled: bool,
    ) -> tuple[str, ...]:
        categories = {
            category.strip()
            for category in self._presentation.categories
            if category.strip()
        }
        categories.add(synchronization_event.sport.name)

        if synchronization_event.competition is not None:
            categories.add(synchronization_event.competition.name)
        if is_cancelled:
            categories.add(self._presentation.cancelled_category)

        return tuple(sorted(categories, key=lambda value: (value.casefold(), value)))

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
            zoned_start.astimezone(UTC)
            + timedelta(minutes=self._presentation.default_duration_minutes)
        ).astimezone(zone)
        return OutlookDateTime(
            date_time=end.replace(tzinfo=None).isoformat(timespec="seconds"),
            time_zone=time_zone,
        )

    @staticmethod
    def _build_location(*parts: str | None) -> str | None:
        values = tuple(value.strip() for value in parts if value and value.strip())
        return ", ".join(dict.fromkeys(values)) or None

    @staticmethod
    def _participant_sort_key(
        participant: SynchronizationParticipant,
    ) -> tuple[bool, int, str, int]:
        return (
            participant.position_number is None,
            participant.position_number or 0,
            participant.role.casefold(),
            participant.participant.id,
        )

    @staticmethod
    def _result_sort_key(result: EventResult) -> tuple[bool, int, str, int, int]:
        return (
            result.position_number is None,
            result.position_number or 0,
            result.result_type.casefold(),
            result.participant_id or 0,
            result.id,
        )

    @staticmethod
    def _statistic_sort_key(
        statistic: EventStatistic,
    ) -> tuple[bool, int, str, str, int]:
        return (
            statistic.participant_id is None,
            statistic.participant_id or 0,
            statistic.statistic_key.casefold(),
            statistic.recorded_at or "",
            statistic.id,
        )

    @classmethod
    def _render_result(
        cls,
        result: EventResult,
        participant_names: dict[int, str],
    ) -> str:
        label = (
            result.result_type
            if result.participant_id is None
            else participant_names.get(result.participant_id, result.result_type)
        )
        value = cls._render_value(result.value_number, result.value_text)
        final_suffix = " (final)" if result.is_final else ""
        return f"- {label}: {value}{final_suffix}"

    @classmethod
    def _render_statistic(
        cls,
        statistic: EventStatistic,
        participant_names: dict[int, str],
    ) -> str:
        name = statistic.statistic_name or statistic.statistic_key
        participant = (
            None
            if statistic.participant_id is None
            else participant_names.get(statistic.participant_id)
        )
        label = f"{participant} – {name}" if participant is not None else name
        value = cls._render_value(statistic.value_number, statistic.value_text)
        unit = f" {statistic.unit}" if statistic.unit is not None else ""
        period = f" ({statistic.period})" if statistic.period is not None else ""
        return f"- {label}: {value}{unit}{period}"

    @staticmethod
    def _render_value(value_number: float | None, value_text: str | None) -> str:
        if value_text is not None:
            return value_text
        if value_number is None:
            return "n/a"
        return f"{value_number:g}"
