#!/usr/bin/env python3
"""Script to automatically fix E501 line too long errors."""

import subprocess
import re
from pathlib import Path

def get_e501_errors():
    """Get all E501 errors from flake8."""
    result = subprocess.run(
        [
            "docker", "exec", "festival_app",
            "flake8", "festival_playlist_generator/", "tests/",
            "--select=E501"
        ],
        capture_output=True,
        text=True,
        cwd="/Users/nathan/gigprep/services/api"
    )

    errors = []
    for line in result.stdout.strip().split('\n'):
        if line and 'E501' in line:
            match = re.match(r'(.+?):(\d+):\d+: E501', line)
            if match:
                filepath, lineno = match.groups()
                errors.append((filepath, int(lineno)))

    return errors

def main():
    errors = get_e501_errors()
    print(f"Found {len(errors)} E501 errors")

    # Group by file
    files = {}
    for filepath, lineno in errors:
        if filepath not in files:
            files[filepath] = []
        files[filepath].append(lineno)

    for filepath, lines in sorted(files.items()):
        print(f"\n{filepath}: {len(lines)} errors on lines {lines[:10]}...")

if __name__ == "__main__":
    main()
