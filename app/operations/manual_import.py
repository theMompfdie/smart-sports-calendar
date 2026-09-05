"""Submit reviewed files to the owning process through its persistent inbox."""

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from app.imports.manual_files import read_bounded
from app.imports.manual_inbox import ManualInbox
from app.imports.manual_manifest import parse_manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inbox", type=Path, required=True)
    parser.add_argument("--instance", required=True)
    parser.add_argument("--namespace", required=True)
    commands = parser.add_subparsers(dest="action", required=True)
    submit = commands.add_parser("submit")
    submit.add_argument("--manifest", type=Path, required=True)
    for action in ("approve", "preview", "status"):
        command = commands.add_parser(action)
        command.add_argument("--submission", required=True)
        if action == "approve":
            command.add_argument("--approval", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        inbox = ManualInbox(args.inbox, args.instance)
        if args.action == "status":
            result = inbox.status(args.namespace, args.submission)
            print(json.dumps(result, indent=2, sort_keys=True))
            if result.get("error") and result["state"] != "RETRYABLE_FAILURE":
                return 2
            return {"REJECTED": 2, "NEEDS_REVIEW": 2, "RETRYABLE_FAILURE": 3}.get(
                result["state"], 0
            )
        payload = b""
        if args.action == "submit":
            payload = read_bounded(args.manifest)
            manifest = parse_manifest(payload)
            if manifest.namespace != args.namespace:
                raise ValueError("Manifest namespace differs from target.")
            submission = manifest.submission_id
        else:
            submission = args.submission
            if args.action == "approve":
                payload = read_bounded(args.approval)
        request = inbox.submit(args.action, args.namespace, submission, payload)
        print(json.dumps({"state": "QUEUED", "request_id": request}))
        return 0
    except ValueError:
        print(
            json.dumps(
                {
                    "state": "REJECTED",
                    "error": "Invalid input or target instance/scope.",
                }
            )
        )
        return 2
    except OSError:
        print(
            json.dumps(
                {
                    "state": "UNAVAILABLE",
                    "error": "Inbox/status unavailable; check mount and worker.",
                }
            )
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
