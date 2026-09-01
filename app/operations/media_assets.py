"""Secret-safe local administration CLI for rights-controlled media assets."""

import argparse
import json
import sqlite3
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from app.database.database import Database
from app.database.media_assets_repository import (
    MediaAsset,
    MediaAssetsRepository,
)
from app.domain.media_assets import MediaAssetError, MediaOwnerType
from app.media.asset_service import MediaAssetService


def _asset_payload(
    repository: MediaAssetsRepository,
    asset: MediaAsset,
) -> dict[str, Any]:
    return {
        "asset_key": asset.asset_key,
        "version": asset.version,
        "owner_type": asset.owner.owner_type.value,
        "owner_key": repository.owner_key_for(asset.owner),
        "variant": asset.variant,
        "mime_type": asset.mime_type,
        "width": asset.width,
        "height": asset.height,
        "byte_size": asset.byte_size,
        "sha256": asset.sha256,
        "license_name": asset.license_name,
        "has_permission_reference": asset.permission_reference is not None,
        "attribution": asset.attribution,
        "approved": asset.is_approved,
        "approved_by": asset.approved_by,
        "approved_at": asset.approved_at,
        "active": asset.is_active,
        "deactivated_at": asset.deactivated_at,
        "created_at": asset.created_at,
        "updated_at": asset.updated_at,
    }


def _print_json(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def _import_asset(
    repository: MediaAssetsRepository,
    service: MediaAssetService,
    args: argparse.Namespace,
) -> None:
    owner = repository.resolve_owner(
        MediaOwnerType(args.owner_type),
        args.owner_key,
    )
    asset = service.import_asset(
        asset_key=args.asset_key,
        owner=owner,
        variant=args.variant,
        source_file=args.file,
        source_reference=args.source_reference,
        license_name=args.license_name,
        permission_reference=args.permission_reference,
        attribution=args.attribution,
    )
    _print_json(_asset_payload(repository, asset))


def _approve_asset(
    repository: MediaAssetsRepository,
    service: MediaAssetService,
    args: argparse.Namespace,
) -> None:
    asset = service.approve(args.asset_key, args.version, args.reviewer)
    _print_json(_asset_payload(repository, asset))


def _disable_asset(
    repository: MediaAssetsRepository,
    service: MediaAssetService,
    args: argparse.Namespace,
) -> None:
    asset = service.disable(args.asset_key)
    _print_json(_asset_payload(repository, asset))


def _list_assets(
    repository: MediaAssetsRepository,
    _service: MediaAssetService,
    args: argparse.Namespace,
) -> None:
    _print_json(
        [
            _asset_payload(repository, asset)
            for asset in repository.list(include_inactive=args.include_inactive)
        ]
    )


def _add_import_parser(
    subparsers: argparse._SubParsersAction,
    command: str,
) -> None:
    parser = subparsers.add_parser(
        command,
        help=f"{command.title()} one local image as a pending normalized asset.",
    )
    parser.add_argument("--asset-key", required=True)
    parser.add_argument("--owner-type", required=True, choices=tuple(MediaOwnerType))
    parser.add_argument("--owner-key", required=True)
    parser.add_argument("--variant", required=True)
    parser.add_argument("--file", required=True, type=Path)
    parser.add_argument("--source-reference", required=True)
    parser.add_argument("--license-name")
    parser.add_argument("--permission-reference")
    parser.add_argument("--attribution")
    parser.set_defaults(handler=_import_asset)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage rights-controlled SMART Sports Calendar media assets."
    )
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--media-root", required=True, type=Path)
    subparsers = parser.add_subparsers(dest="command", required=True)
    _add_import_parser(subparsers, "import")
    _add_import_parser(subparsers, "replace")

    approve = subparsers.add_parser(
        "approve",
        help="Approve and activate one validated asset version.",
    )
    approve.add_argument("--asset-key", required=True)
    approve.add_argument("--version", required=True, type=int)
    approve.add_argument("--reviewer", required=True)
    approve.set_defaults(handler=_approve_asset)

    disable = subparsers.add_parser("disable", help="Deactivate one active asset.")
    disable.add_argument("--asset-key", required=True)
    disable.set_defaults(handler=_disable_asset)

    list_parser = subparsers.add_parser("list", help="List media assets.")
    list_parser.add_argument("--include-inactive", action="store_true")
    list_parser.set_defaults(handler=_list_assets)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        Database(args.database).initialize()
        repository = MediaAssetsRepository(args.database)
        service = MediaAssetService(repository, args.media_root)
        args.handler(repository, service, args)
    except MediaAssetError as error:
        parser.exit(status=1, message=f"Media asset command failed: {error}\n")
    except (OSError, sqlite3.Error):
        parser.exit(
            status=1,
            message="Media asset command failed: storage operation failed.\n",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
