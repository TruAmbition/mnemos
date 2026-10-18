#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mnemos.backup import restore_backup
parser = argparse.ArgumentParser(description='Verify and restore a snapshot into a new or empty directory.')
parser.add_argument('snapshot')
parser.add_argument('--to', required=True)
args = parser.parse_args()
try:
    print(json.dumps(restore_backup(args.snapshot, args.to), indent=2))
except (ValueError, OSError, KeyError) as error:
    parser.exit(1, f'Restore failed: {error}\n')
