#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from keystone.export import build_reader
parser = argparse.ArgumentParser(description='Build an unencrypted static reader from verified documentation only.')
parser.add_argument('--data', default='./data')
parser.add_argument('--out', required=True)
args = parser.parse_args()
try:
    print(json.dumps(build_reader(args.data, args.out), indent=2))
except (ValueError, OSError) as error:
    parser.exit(1, f'Export failed: {error}\n')
