#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mnemos.export import build_reader
from mnemos.installation import resolve_data


def main(argv=None):
    parser = argparse.ArgumentParser(description='Build an unencrypted static reader from verified documentation only.')
    parser.add_argument('--data', help='Pin a data folder; omitted uses the selected default.')
    parser.add_argument('--out', required=True)
    args = parser.parse_args(argv)
    try:
        data = resolve_data(args.data)
        print(json.dumps(build_reader(data, args.out), indent=2))
        return 0
    except (ValueError, OSError) as error:
        parser.exit(1, f'Export failed: {error}\n')


if __name__ == '__main__':
    raise SystemExit(main())
