"""Command line entry point: python -m mnemos --help."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import core
from .installation import resolve_data
from .runtime import default_root


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Mnemos engineering knowledge toolkit")
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("projects", "connections", "init", "serve", "capture", "search", "get", "recall", "handoff", "skills-export", "token", "workflow-plan", "backup", "export", "build-reader"):
        sub = commands.add_parser(command)
        sub.add_argument("--data", help="Pin a data folder; omitted uses this installation's selected default")
        if command == "projects":
            sub.add_argument('action', choices=['list', 'save', 'refresh', 'remove', 'automatic'], default='list', nargs='?')
            sub.add_argument('--file', help='JSON settings, or id/revision; automatic also needs auto_refresh boolean')
        elif command == "connections":
            sub.add_argument("--project", help="Project folder whose assistant settings to inspect")
        elif command == "init":
            sub.add_argument("--author", default="Local engineer")
        elif command == "serve":
            sub.add_argument("--host", default="127.0.0.1")
            sub.add_argument("--port", default=4318, type=int)
            sub.add_argument("--public-host", action="append", default=[], help="Allowed network hostname, including port when applicable")
            sub.add_argument("--require-auth", action="store_true", help="Require a token even on localhost; required behind a reverse proxy")
        elif command == "capture":
            sub.add_argument("--file", required=True, help="JSON capture file, or - for stdin")
        elif command in {"search", "recall", "handoff"}:
            sub.add_argument("query", nargs="*", help="Words to find across document titles and contents")
            sub.add_argument("--role", choices=["owner", "author", "reader"], default="owner")
            if command in {"recall", "handoff"}:
                sub.add_argument("--budget", type=int, default=6000, help="Maximum context characters")
            if command == "handoff":
                sub.add_argument("--output", help="Save a context pack JSON file; otherwise print it")
                sub.add_argument("--id", action="append", default=[], help="Explicitly include a full source document (repeatable)")
        elif command == "token":
            sub.add_argument("--role", choices=["reader", "author", "owner"], required=True)
            sub.add_argument("--author", required=True, help="Name identifying the person or agent")
        elif command in {"workflow-plan", "get"}:
            sub.add_argument("--id", required=True)
        elif command in {"export", "build-reader", "skills-export"}:
            sub.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        uses_default = args.data is None
        if args.command != "skills-export":
            args.data = resolve_data(args.data)
        if args.command == "projects":
            from . import projects
            if args.action == 'list':
                result = projects.list_projects(args.data)
            else:
                if not args.file:
                    raise ValueError('Use --file with a project JSON object; list returns current revisions.')
                payload = json.loads(Path(args.file).read_text('utf-8'))
                operation = {'save': projects.save_project, 'refresh': projects.refresh_project, 'remove': projects.remove_project, 'automatic': projects.set_automatic}[args.action]
                result = operation(args.data, payload)
        elif args.command == "connections":
            from .connections import inventory, public_inventory
            result = public_inventory(inventory(args.data, {}, args.project))
        elif args.command == "init":
            config = core.initialize(args.data, args.author)
            result = {"vault_path": str(core.vault_path(args.data)), "owner": config["owner"], "initialized": True}
        elif args.command == "serve":
            from .server import serve
            serve(args.data, args.host, args.port, args.public_host, args.require_auth,
                  installation_file=default_root() / "installation.json" if uses_default else None)
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
        elif args.command == "handoff":
            from .handoff import build_pack
            result = build_pack(args.data, " ".join(args.query), args.budget, args.role, args.id)
            if args.output:
                core.atomic_write(Path(args.output).expanduser(), json.dumps(result, indent=2, ensure_ascii=False) + "\n")
                result = {"output": str(Path(args.output).expanduser().absolute()), "mode": result["mode"]}
        elif args.command == "skills-export":
            from .handoff import skills_archive
            core.atomic_write(Path(args.output).expanduser(), skills_archive())
            result = {"output": str(Path(args.output).expanduser().absolute())}
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
        print(f"Mnemos: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
