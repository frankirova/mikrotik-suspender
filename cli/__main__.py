"""Entry point for the CLI — `python -m cli ...`.

Parses args, runs the bootstrap, dispatches to use cases, formats output.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import date as _date

import bootstrap
from api.dependencies import get_suspension_use_cases
from use_cases.suspension import SuspensionUseCases

logger = logging.getLogger(__name__)


def _format_table(rows: list[tuple[str, str, str]]) -> str:
    """Render 3-column rows as an aligned ASCII table."""
    if not rows:
        return "(no entries to suspend)"
    headers = ("ID", "CURRENT", "FINAL")
    widths = [max(len(headers[i]), *(len(r[i]) for r in rows)) for i in range(3)]
    sep = "  "
    fmt = sep.join(f"{{:<{w}}}" for w in widths)

    lines = [fmt.format(*headers), fmt.format(*("-" * w for w in widths))]
    lines.extend(fmt.format(*r) for r in rows)
    return "\n".join(lines)


async def _run_preview(uc: SuspensionUseCases, mikrotik_ip: str, day: str) -> int:
    """Show what WOULD be suspended, without executing."""
    result = await uc.preview(mikrotik_ip=mikrotik_ip, date=day)
    rows = [
        (e.id, e.comment, f.comment)
        for e, f in zip(result.current_comments, result.final_comments)
    ]
    print(_format_table(rows))
    return 0


async def _run_execute(uc: SuspensionUseCases, mikrotik_ip: str, day: str) -> int:
    """Execute the suspension on the MikroTik device."""
    await uc.execute(mikrotik_ip=mikrotik_ip, date=day)
    print(f"OK: suspension executed against {mikrotik_ip} for date {day}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m cli",
        description="Suspend MikroTik client IPs from CSV — CLI for technicians.",
    )

    def _add_common(sub: argparse.ArgumentParser) -> None:
        sub.add_argument(
            "--mikrotik", "-m",
            required=True,
            help="IP of the MikroTik device to connect to.",
        )
        sub.add_argument(
            "--date", "-d",
            default=_date.today().isoformat(),
            help="Suspension date (default: today, ISO format YYYY-MM-DD).",
        )
        sub.add_argument(
            "--json", "-j",
            action="store_true",
            help="Output as JSON instead of a table.",
        )

    sub = parser.add_subparsers(dest="command", required=True)

    p_preview = sub.add_parser("preview", help="Show what would be suspended, without executing.")
    _add_common(p_preview)

    p_run = sub.add_parser("run", help="Execute the suspension on the MikroTik device.")
    _add_common(p_run)

    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = _build_parser()
    args = parser.parse_args(argv)

    bootstrap.run()
    uc = get_suspension_use_cases()

    coro = _run_preview if args.command == "preview" else _run_execute

    try:
        code = asyncio.run(coro(uc, args.mikrotik, args.date))
    except Exception as exc:
        logger.exception("CLI failed")
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return code


if __name__ == "__main__":
    sys.exit(main())
