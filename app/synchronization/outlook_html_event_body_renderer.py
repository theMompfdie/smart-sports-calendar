"""Safe, deterministic HTML rendering for Outlook sports events."""

from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.database.event_results_repository import EventResult
from app.database.event_statistics_repository import EventStatistic
from app.database.synchronization_query_repository import (
    SynchronizationEvent,
    SynchronizationParticipant,
)

_CONTAINER_STYLE = (
    "font-family:'Segoe UI',Arial,sans-serif;color:#242424;line-height:1.4;"
)
_HEADER_TABLE_STYLE = "border-collapse:collapse;margin:0 0 16px;width:100%;"
_HEADER_CELL_STYLE = (
    "background:#f3f6fb;border-left:4px solid #2563eb;padding:12px 16px;"
)
_SECTION_HEADING_STYLE = "font-size:16px;margin:16px 0 6px;"
_TABLE_STYLE = "border-collapse:collapse;margin:0 0 12px;width:100%;"
_LABEL_CELL_STYLE = (
    "border-bottom:1px solid #e5e7eb;font-weight:600;padding:4px 12px 4px 0;"
    "vertical-align:top;width:120px;"
)
_VALUE_CELL_STYLE = "border-bottom:1px solid #e5e7eb;padding:4px 0;vertical-align:top;"


class OutlookHtmlEventBodyRenderer:
    """Render canonical synchronization data as conservative Outlook HTML."""

    def __init__(self, display_time_zone: str = "Europe/Vienna") -> None:
        try:
            self._display_zone = ZoneInfo(display_time_zone)
        except ZoneInfoNotFoundError as error:
            raise ValueError(
                f"Unknown body display time zone: {display_time_zone}"
            ) from error
        self._display_time_zone = display_time_zone

    def render(
        self,
        synchronization_event: SynchronizationEvent,
        *,
        is_cancelled: bool,
        location: str | None,
    ) -> str:
        """Return one complete fragment with all dynamic text HTML-escaped."""

        sections = [
            f'<div style="{_CONTAINER_STYLE}">',
            self._render_header(synchronization_event),
            self._render_event_details(
                synchronization_event,
                is_cancelled=is_cancelled,
                location=location,
            ),
        ]

        participants = sorted(
            synchronization_event.participants,
            key=self._participant_sort_key,
        )
        if participants:
            sections.append(self._render_participants(participants))

        participant_names = {
            participant.participant.id: participant.participant.name
            for participant in synchronization_event.participants
        }
        results = sorted(synchronization_event.results, key=self._result_sort_key)
        if results:
            sections.append(self._render_results(results, participant_names))

        statistics = sorted(
            synchronization_event.statistics,
            key=self._statistic_sort_key,
        )
        if statistics:
            sections.append(self._render_statistics(statistics, participant_names))

        if synchronization_event.operator_notice is not None:
            sections.append(
                '<p style="background:#fff8e1;border-left:4px solid #f59e0b;'
                'margin:16px 0 0;padding:10px 12px;">'
                "<strong>Notice:</strong> "
                f"{self._text(synchronization_event.operator_notice.text)}</p>"
            )

        if synchronization_event.source_attribution is not None:
            sections.append(
                '<p style="color:#5f6368;font-size:12px;margin:16px 0 0;">'
                "<strong>Source:</strong> "
                f"{self._text(synchronization_event.source_attribution)}</p>"
            )

        sections.append("</div>")
        return "\n".join(sections)

    def _render_header(self, synchronization_event: SynchronizationEvent) -> str:
        event = synchronization_event.event
        context = (
            synchronization_event.competition.name
            if synchronization_event.competition is not None
            else synchronization_event.sport.name
        )
        return (
            f'<table role="presentation" style="{_HEADER_TABLE_STYLE}"><tbody><tr>'
            f'<td style="{_HEADER_CELL_STYLE}">'
            '<div style="font-size:20px;font-weight:600;margin:0 0 2px;">'
            f"{self._text(event.title)}</div>"
            '<div style="color:#5f6368;font-size:13px;">'
            f"{self._text(context)}</div>"
            "</td></tr></tbody></table>"
        )

    def _render_event_details(
        self,
        synchronization_event: SynchronizationEvent,
        *,
        is_cancelled: bool,
        location: str | None,
    ) -> str:
        event = synchronization_event.event
        rows: list[tuple[str, str]] = [
            ("Status", "Cancelled" if is_cancelled else event.status),
            ("Sport", synchronization_event.sport.name),
        ]

        if synchronization_event.competition is not None:
            rows.append(("Competition", synchronization_event.competition.name))
        if synchronization_event.season is not None:
            rows.append(("Season", synchronization_event.season.name))
        if synchronization_event.parent_event is not None:
            rows.append(("Parent event", synchronization_event.parent_event.title))
        if event.stage is not None:
            rows.append(("Stage", event.stage))
        if event.round_name is not None:
            rows.append(("Round", event.round_name))

        rows.append(
            (
                "Kickoff",
                self._format_start_time(event.start_time, event.timezone),
            )
        )
        if location is not None:
            rows.append(("Location", location))

        return self._render_table("Event details", rows)

    def _render_participants(
        self,
        participants: list[SynchronizationParticipant],
    ) -> str:
        rows = [
            (participant.role, participant.participant.name)
            for participant in participants
        ]
        return self._render_table("Participants", rows)

    def _render_results(
        self,
        results: list[EventResult],
        participant_names: dict[int, str],
    ) -> str:
        rows: list[tuple[str, str]] = []
        for result in results:
            label = (
                result.result_type
                if result.participant_id is None
                else participant_names.get(result.participant_id, result.result_type)
            )
            value = self._render_value(result.value_number, result.value_text)
            if result.is_final:
                value = f"{value} (final)"
            rows.append((label, value))
        return self._render_table("Results", rows)

    def _render_statistics(
        self,
        statistics: list[EventStatistic],
        participant_names: dict[int, str],
    ) -> str:
        rows: list[tuple[str, str]] = []
        for statistic in statistics:
            name = statistic.statistic_name or statistic.statistic_key
            participant = (
                None
                if statistic.participant_id is None
                else participant_names.get(statistic.participant_id)
            )
            label = f"{participant} – {name}" if participant is not None else name
            value = self._render_value(
                statistic.value_number,
                statistic.value_text,
            )
            if statistic.unit is not None:
                value = f"{value} {statistic.unit}"
            if statistic.period is not None:
                value = f"{value} ({statistic.period})"
            rows.append((label, value))
        return self._render_table("Statistics", rows)

    @classmethod
    def _render_table(
        cls,
        heading: str,
        rows: list[tuple[str, str]],
    ) -> str:
        rendered_rows = "".join(
            "<tr>"
            f'<td style="{_LABEL_CELL_STYLE}">{cls._text(label)}:</td>'
            f'<td style="{_VALUE_CELL_STYLE}">{cls._text(value)}</td>'
            "</tr>"
            for label, value in rows
        )
        return (
            f'<h3 style="{_SECTION_HEADING_STYLE}">{cls._text(heading)}</h3>'
            f'<table role="presentation" style="{_TABLE_STYLE}"><tbody>'
            f"{rendered_rows}</tbody></table>"
        )

    def _format_start_time(self, value: str, event_time_zone: str) -> str:
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as error:
            raise ValueError(f"Invalid event date-time: {value}") from error

        if parsed.tzinfo is None:
            try:
                parsed = parsed.replace(tzinfo=ZoneInfo(event_time_zone))
            except ZoneInfoNotFoundError as error:
                raise ValueError(
                    f"Unknown event time zone: {event_time_zone}"
                ) from error

        displayed = parsed.astimezone(self._display_zone)
        return f"{displayed.isoformat(timespec='minutes')} ({self._display_time_zone})"

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

    @staticmethod
    def _render_value(value_number: float | None, value_text: str | None) -> str:
        if value_text is not None:
            return value_text
        if value_number is None:
            return "n/a"
        return f"{value_number:g}"

    @staticmethod
    def _text(value: object) -> str:
        return escape(str(value), quote=True)
