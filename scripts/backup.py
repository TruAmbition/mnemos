#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mnemos.backup import create_backup
from mnemos.installation import resolve_data


def main(argv=None):
    parser = argparse.ArgumentParser(description='Create a verified local or cloud vault snapshot.')
    parser.add_argument('--data', help='Pin a data folder; omitted uses the selected default.')
    args = parser.parse_args(argv)
    try:
        data = resolve_data(args.data)
        print(json.dumps(create_backup(data), indent=2))
        return 0
    except (ValueError, OSError) as error:
        parser.exit(1, f'Backup failed: {error}\n')


if __name__ == '__main__':
    raise SystemExit(main())
