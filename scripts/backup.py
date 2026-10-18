#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mnemos.backup import create_backup
parser = argparse.ArgumentParser(description='Create a verified local or cloud vault snapshot.')
parser.add_argument('--data', default='./data')
args = parser.parse_args()
try:
    print(json.dumps(create_backup(args.data), indent=2))
except (ValueError, OSError) as error:
    parser.exit(1, f'Backup failed: {error}\n')
