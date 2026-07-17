"""Safe command-line plan/apply workflow."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import io
import json
import sys
from dataclasses import asdict
from datetime import date

import bootstrap
from api.dependencies import get_suspension_use_cases


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mikrotik-suspender")
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("plan", "apply"):
        child = sub.add_parser(command)
        child.add_argument("--router", required=True)
        child.add_argument("--date", default=date.today().isoformat())
        child.add_argument("--json", action="store_true")
        if command == "apply":
            child.add_argument("--yes", action="store_true", help="skip interactive confirmation")
    return parser


async def _run(args: argparse.Namespace) -> int:
    uc = get_suspension_use_cases()
    plan = await uc.plan(args.router, args.date)
    if args.command == "plan":
        print(json.dumps(asdict(plan), sort_keys=True) if args.json else _plan_text(plan))
        return 3 if any(action.kind == "conflict" for action in plan.actions) else 0
    if not args.yes:
        answer = input(f"Apply plan {plan.plan_id} to router {args.router}? [y/N] ")
        if answer.strip().lower() not in {"y", "yes"}:
            print(json.dumps({"status": "cancelled"}) if args.json else "Cancelled")
            return 4
    result = await uc.apply(plan, args.router)
    payload = asdict(result) | {"summary": result.summary}
    print(
        json.dumps(payload, sort_keys=True)
        if args.json
        else f"Applied {result.succeeded}; failed {result.failed}"
    )
    return 5 if result.failed else 0


def _plan_text(plan) -> str:
    lines = [
        f"Plan: {plan.plan_id}",
        f"Router: {plan.router}",
        f"Address-list: {plan.address_list}",
    ]
    lines.extend(f"{action.kind}: {action.address} ({action.reason})" for action in plan.actions)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    effective_argv = list(sys.argv[1:] if argv is None else argv)
    json_output = "--json" in effective_argv
    parser_stderr = io.StringIO()
    try:
        with contextlib.redirect_stderr(parser_stderr) if json_output else contextlib.nullcontext():
            args = _parser().parse_args(effective_argv)
        bootstrap.run()
        return asyncio.run(_run(args))
    except SystemExit as exc:
        if json_output and exc.code:
            detail = parser_stderr.getvalue().strip().splitlines()[-1]
            print(json.dumps({"error": detail}), file=sys.stderr)
        return int(exc.code or 0)
    except (ValueError, RuntimeError) as exc:
        print(
            json.dumps({"error": str(exc)}) if json_output else f"ERROR: {exc}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
