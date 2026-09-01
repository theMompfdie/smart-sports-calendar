"""Secret-safe local administration CLI for persisted reminder rules."""

import argparse
import json
import sqlite3
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from app.database.database import Database
from app.database.reminder_rules_repository import (
    ReminderRuleRepositoryError,
    ReminderRulesRepository,
    ReminderRuleTarget,
)
from app.domain.reminder_rules import (
    ReminderAction,
    ReminderRule,
    ReminderRuleError,
    ReminderRuleWrite,
    ReminderScope,
)


def _add_target_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--scope", required=True, choices=tuple(ReminderScope))
    parser.add_argument("--competition")
    parser.add_argument("--participant")
    parser.add_argument("--event")


def _target_from_args(args: argparse.Namespace) -> ReminderRuleTarget:
    return ReminderRuleTarget(
        scope=ReminderScope(args.scope),
        competition_key=args.competition,
        participant_key=args.participant,
        event_key=args.event,
    )


def _rule_payload(
    repository: ReminderRulesRepository,
    rule: ReminderRule,
) -> dict[str, Any]:
    target = repository.target_for(rule)
    return {
        "scope": target.scope.value,
        "competition": target.competition_key,
        "participant": target.participant_key,
        "event": target.event_key,
        "action": None if rule.action is None else rule.action.value,
        "preferred_lead_minutes": rule.preferred_lead_minutes,
        "minimum_lead_minutes": rule.minimum_lead_minutes,
        "maximum_lead_minutes": rule.maximum_lead_minutes,
        "quiet_start": rule.quiet_start,
        "quiet_end": rule.quiet_end,
        "timezone": rule.timezone,
        "active": rule.is_active,
        "operator_note": rule.operator_note,
        "created_at": rule.created_at,
        "updated_at": rule.updated_at,
        "deleted_at": rule.deleted_at,
    }


def _print_json(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def _list_rules(
    repository: ReminderRulesRepository,
    args: argparse.Namespace,
) -> None:
    rules = repository.list(include_deleted=args.include_deleted)
    _print_json([_rule_payload(repository, rule) for rule in rules])


def _show_rule(
    repository: ReminderRulesRepository,
    args: argparse.Namespace,
) -> None:
    selector = repository.resolve_target(_target_from_args(args))
    rule = repository.get_current(selector)
    if rule is None:
        raise ReminderRuleRepositoryError("Current reminder rule was not found.")
    _print_json(_rule_payload(repository, rule))


def _set_rule(
    repository: ReminderRulesRepository,
    args: argparse.Namespace,
) -> None:
    selector = repository.resolve_target(_target_from_args(args))
    action = None if args.action in (None, "inherit") else ReminderAction(args.action)
    rule = repository.set(
        ReminderRuleWrite(
            selector=selector,
            action=action,
            preferred_lead_minutes=args.preferred_lead_minutes,
            minimum_lead_minutes=args.minimum_lead_minutes,
            maximum_lead_minutes=args.maximum_lead_minutes,
            quiet_start=args.quiet_start,
            quiet_end=args.quiet_end,
            timezone=args.timezone,
            operator_note=args.note,
        )
    )
    _print_json(_rule_payload(repository, rule))


def _disable_rule(
    repository: ReminderRulesRepository,
    args: argparse.Namespace,
) -> None:
    selector = repository.resolve_target(_target_from_args(args))
    _print_json(_rule_payload(repository, repository.disable(selector)))


def _delete_rule(
    repository: ReminderRulesRepository,
    args: argparse.Namespace,
) -> None:
    selector = repository.resolve_target(_target_from_args(args))
    _print_json(_rule_payload(repository, repository.delete(selector)))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Manage canonical reminder rules in one local SMART Sports Calendar "
            "SQLite database."
        )
    )
    parser.add_argument(
        "--database",
        required=True,
        type=Path,
        help="Explicit path to the target SMART Sports Calendar SQLite database.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List persisted rules.")
    list_parser.add_argument("--include-deleted", action="store_true")
    list_parser.set_defaults(handler=_list_rules)

    show_parser = subparsers.add_parser("show", help="Show one current rule.")
    _add_target_arguments(show_parser)
    show_parser.set_defaults(handler=_show_rule)

    set_parser = subparsers.add_parser(
        "set",
        help="Create or completely replace one current natural-scope rule.",
    )
    _add_target_arguments(set_parser)
    set_parser.add_argument(
        "--action",
        choices=(ReminderAction.ENABLE.value, ReminderAction.SUPPRESS.value, "inherit"),
    )
    set_parser.add_argument("--preferred-lead-minutes", type=int)
    set_parser.add_argument("--minimum-lead-minutes", type=int)
    set_parser.add_argument("--maximum-lead-minutes", type=int)
    set_parser.add_argument("--quiet-start")
    set_parser.add_argument("--quiet-end")
    set_parser.add_argument("--timezone")
    set_parser.add_argument("--note")
    set_parser.set_defaults(handler=_set_rule)

    disable_parser = subparsers.add_parser(
        "disable",
        help="Deactivate one current rule without deleting its audit state.",
    )
    _add_target_arguments(disable_parser)
    disable_parser.set_defaults(handler=_disable_rule)

    delete_parser = subparsers.add_parser(
        "delete",
        help="Tombstone one current rule.",
    )
    _add_target_arguments(delete_parser)
    delete_parser.set_defaults(handler=_delete_rule)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        Database(args.database).initialize()
        repository = ReminderRulesRepository(args.database)
        args.handler(repository, args)
    except ReminderRuleError as error:
        parser.exit(status=1, message=f"Reminder rule command failed: {error}\n")
    except (OSError, sqlite3.Error):
        parser.exit(
            status=1,
            message="Reminder rule command failed: database operation failed.\n",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
