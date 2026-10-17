"""Command line entry point: python -m keystone --help."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import core


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Keystone engineering knowledge toolkit")
    commands = parser.add_subparsers(dest="command", required=True)
    default_data = str(Path.cwd() / "data")
    for command in ("init", "serve", "capture", "search", "get", "recall", "token", "workflow-plan", "backup", "export", "build-reader"):
        sub = commands.add_parser(command)
        sub.add_argument("--data", default=default_data, help="Dedicated Keystone data folder (default: ./data)")
        if command == "init":
            sub.add_argument("--author", default="Local engineer")
        elif command == "serve":
            sub.add_argument("--host", default="127.0.0.1")
            sub.add_argument("--port", default=4318, type=int)
            sub.add_argument("--public-host", action="append", default=[], help="Allowed network hostname, including port when applicable")
            sub.add_argument("--require-auth", action="store_true", help="Require a token even on localhost; required behind a reverse proxy")
        elif command == "capture":
            sub.add_argument("--file", required=True, help="JSON capture file, or - for stdin")
        elif command in {"search", "recall"}:
            sub.add_argument("query", nargs="*", help="Words to find across document titles and contents")
            sub.add_argument("--role", choices=["owner", "author", "reader"], default="owner")
            if command == "recall":
                sub.add_argument("--budget", type=int, default=6000, help="Maximum context characters")
        elif command == "token":
            sub.add_argument("--role", choices=["reader", "author", "owner"], required=True)
            sub.add_argument("--author", required=True, help="Name identifying the person or agent")
        elif command in {"workflow-plan", "get"}:
            sub.add_argument("--id", required=True)
        elif command in {"export", "build-reader"}:
            sub.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            config = core.initialize(args.data, args.author)
            result = {"vault_path": str(core.vault_path(args.data)), "owner": config["owner"], "initialized": True}
        elif args.command == "serve":
            from .server import serve
            serve(args.data, args.host, args.port, args.public_host, args.require_auth)
            return 0
        elif args.command == "capture":
            payload = json.loads(sys.stdin.read() if args.file == "-" else Path(args.file).read_text("utf-8"))
            result = {"document": core.save_document(args.data, payload)}
        elif args.command == "search":
            result = {"documents": core.list_documents(args.data, args.role, " ".join(args.query))}
        elif args.command == "get":
            result = {"document": core.get_document(args.data, args.id)}
        elif args.command == "recall":
            from .recall import recall
            print(recall(args.data, " ".join(args.query), args.budget, args.role)["context"])
            return 0
        elif args.command == "token":
            print(core.issue_token(args.data, args.role, args.author))
            return 0
        elif args.command == "workflow-plan":
            result = core.workflow_plan(args.data, args.id)
        elif args.command == "backup":
            from .backup import create_backup
            result = create_backup(args.data)
        elif args.command == "export":
            from .export import vault_archive
            core.atomic_write(Path(args.output).expanduser().resolve(), vault_archive(args.data))
            result = {"output": str(Path(args.output).resolve())}
        else:
            from .export import build_reader
            result = build_reader(args.data, args.output)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except (ValueError, OSError) as exc:
        print(f"Keystone: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
