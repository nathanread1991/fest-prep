#!/usr/bin/env python3
"""Script to fix all E501 errors by reading files and applying fixes."""

import subprocess
import re
from pathlib import Path

# Get all E501 errors
result = subprocess.run(
    ["docker", "exec", "festival_app", "flake8",
     "festival_playlist_generator/", "tests/", "--select=E501"],
    capture_output=True,
    text=True,
    cwd="services/api"
)

errors = []
for line in result.stdout.strip().split('\n'):
    if line and 'E501' in line:
        match = re.match(r'(.+?):(\d+):', line)
        if match:
            filepath, lineno = match.groups()
            errors.append((filepath, int(lineno)))

# Group by file
files_dict = {}
for filepath, lineno in errors:
    if filepath not in files_dict:
        files_dict[filepath] = []
    files_dict[filepath].append(lineno)

print(f"Total E501 errors: {len(errors)}")
print(f"Files with errors: {len(files_dict)}")
print("\nFiles with most errors:")
for filepath, lines in sorted(files_dict.items(), key=lambda x: len(x[1]), reverse=True)[:10]:
    print(f"  {filepath}: {len(lines)} errors")
