"""Safe, deterministic HTML rendering for Outlook sports events."""

import re
from dataclasses import dataclass
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
_MIDDLE_LABEL_CELL_STYLE = (
    "border-bottom:1px solid #e5e7eb;font-weight:600;padding:4px 12px 4px 0;"
    "vertical-align:middle;width:120px;"
)
_MIDDLE_VALUE_CELL_STYLE = (
    "border-bottom:1px solid #e5e7eb;padding:4px 0;vertical-align:middle;"
)
_PARTICIPANT_VALUE_TABLE_STYLE = "border-collapse:collapse;margin:0;"
_PARTICIPANT_IMAGE_CELL_STYLE = "line-height:0;padding:0 8px 0 0;vertical-align:middle;"
_PARTICIPANT_NAME_CELL_STYLE = "padding:0;vertical-align:middle;"
_CONTENT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._@-]{0,254}$")
_INLINE_IMAGE_SIZE = 30
_COMPETITION_HEADER_IMAGE_SIZE = 44


@dataclass(frozen=True)
class OutlookInlineImage:
    slot: str
    content_id: str
    alt_text: str

    def __post_init__(self) -> None:
        if self.slot not in {"competition", "home", "away", "final"}:
            raise ValueError("Inline image slot is invalid.")
        if not _CONTENT_ID_PATTERN.fullmatch(self.content_id):
            raise ValueError("Inline image content ID is invalid.")
        if not self.alt_text or self.alt_text != self.alt_text.strip():
            raise ValueError("Inline image alternative text is invalid.")


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
        inline_images: tuple[OutlookInlineImage, ...] = (),
    ) -> str:
        """Return one complete fragment with all dynamic text HTML-escaped."""

        images = {image.slot: image for image in inline_images}
        if len(images) != len(inline_images):
            raise ValueError("Inline image slots must be unique.")
        participants = sorted(
            synchronization_event.participants,
            key=self._participant_sort_key,
        )
        header = self._render_header(
            synchronization_event,
            participants,
            images,
        )
        sections = [
            f'<div style="{_CONTAINER_STYLE}">',
            header,
            self._render_event_details(
                synchronization_event,
                is_cancelled=is_cancelled,
                location=location,
            ),
        ]

        if participants:
            sections.append(self._render_participants(participants, images))

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

    def _render_header(
        self,
        synchronization_event: SynchronizationEvent,
        participants: list[SynchronizationParticipant],
        images: dict[str, OutlookInlineImage],
    ) -> str:
        event = synchronization_event.event
        context = (
            synchronization_event.competition.name
            if synchronization_event.competition is not None
            else synchronization_event.sport.name
        )
        header_slots = tuple(
            slot for slot in ("competition", "final") if slot in images
        )
        image_cells = "".join(
            self._render_image_cell(images[slot]) for slot in header_slots
        )
        title = self._render_title(
            event.title,
            participants,
            images,
        )
        return (
            f'<table role="presentation" style="{_HEADER_TABLE_STYLE}"><tbody><tr>'
            f"{image_cells}"
            f'<td style="{_HEADER_CELL_STYLE}">'
            '<div style="font-size:20px;font-weight:600;margin:0 0 2px;">'
            f"{title}</div>"
            '<div style="color:#5f6368;font-size:13px;">'
            f"{self._text(context)}</div>"
            "</td></tr></tbody></table>"
        )

    @classmethod
    def _render_title(
        cls,
        event_title: str,
        participants: list[SynchronizationParticipant],
        images: dict[str, OutlookInlineImage],
    ) -> str:
        participant_names = {
            participant.role: participant.participant.name
            for participant in participants
            if participant.role in {"home", "away"}
        }
        home = participant_names.get("home")
        away = participant_names.get("away")
        if home is None or away is None or event_title != f"{home} vs {away}":
            return cls._text(event_title)

        home_title = cls._text(home)
        home_image = images.get("home")
        if home_image is not None:
            home_title = (
                f"{cls._render_image(home_image, size=_COMPETITION_HEADER_IMAGE_SIZE)}"
                f"&nbsp;{home_title}"
            )

        away_title = cls._text(away)
        away_image = images.get("away")
        if away_image is not None:
            away_title = (
                f"{away_title}&nbsp;"
                f"{cls._render_image(away_image, size=_COMPETITION_HEADER_IMAGE_SIZE)}"
            )
        return f"{home_title} vs {away_title}"

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
        images: dict[str, OutlookInlineImage],
    ) -> str:
        rows = [
            (
                participant.role,
                self._participant_value(
                    participant.participant.name,
                    images.get(participant.role),
                ),
            )
            for participant in participants
        ]
        middle_aligned_rows = frozenset(
            index
            for index, participant in enumerate(participants)
            if participant.role in images
        )
        return self._render_table(
            "Participants",
            rows,
            values_are_html=True,
            middle_aligned_rows=middle_aligned_rows,
        )

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
        *,
        values_are_html: bool = False,
        middle_aligned_rows: frozenset[int] = frozenset(),
    ) -> str:
        rendered_row_values: list[str] = []
        for index, (label, value) in enumerate(rows):
            align_middle = index in middle_aligned_rows
            label_cell_style = (
                _MIDDLE_LABEL_CELL_STYLE if align_middle else _LABEL_CELL_STYLE
            )
            value_cell_style = (
                _MIDDLE_VALUE_CELL_STYLE if align_middle else _VALUE_CELL_STYLE
            )
            rendered_row_values.append(
                "<tr>"
                f'<td style="{label_cell_style}">{cls._text(label)}:</td>'
                f'<td style="{value_cell_style}">'
                f"{value if values_are_html else cls._text(value)}</td>"
                "</tr>"
            )
        rendered_rows = "".join(rendered_row_values)
        return (
            f'<h3 style="{_SECTION_HEADING_STYLE}">{cls._text(heading)}</h3>'
            f'<table role="presentation" style="{_TABLE_STYLE}"><tbody>'
            f"{rendered_rows}</tbody></table>"
        )

    @classmethod
    def _participant_value(
        cls,
        name: str,
        image: OutlookInlineImage | None,
    ) -> str:
        if image is None:
            return cls._text(name)
        return (
            f'<table role="presentation" style="{_PARTICIPANT_VALUE_TABLE_STYLE}">'
            "<tbody><tr>"
            f'<td style="{_PARTICIPANT_IMAGE_CELL_STYLE}">'
            f"{cls._render_image(image)}</td>"
            f'<td style="{_PARTICIPANT_NAME_CELL_STYLE}">{cls._text(name)}</td>'
            "</tr></tbody></table>"
        )

    @classmethod
    def _render_image_cell(cls, image: OutlookInlineImage) -> str:
        size = (
            _COMPETITION_HEADER_IMAGE_SIZE
            if image.slot in {"competition", "home", "away"}
            else _INLINE_IMAGE_SIZE
        )
        return (
            '<td style="padding:10px 0 10px 12px;vertical-align:middle;">'
            f"{cls._render_image(image, size=size)}</td>"
        )

    @classmethod
    def _render_image(
        cls,
        image: OutlookInlineImage,
        *,
        size: int = _INLINE_IMAGE_SIZE,
    ) -> str:
        return (
            f'<img src="cid:{cls._text(image.content_id)}" '
            f'alt="{cls._text(image.alt_text)}" width="{size}" height="{size}" '
            f'style="border:0;display:inline-block;height:{size}px;max-height:{size}px;'
            f'max-width:{size}px;vertical-align:middle;width:{size}px;" />'
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
