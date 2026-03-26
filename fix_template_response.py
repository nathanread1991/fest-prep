"""Fix TemplateResponse calls to use new Starlette API.

Old: templates.TemplateResponse("name.html", {"request": request, ...})
New: templates.TemplateResponse(request, "name.html", {"request": request, ...})
"""

import re
import sys


def fix_file(filepath: str) -> int:
    with open(filepath, "r") as f:
        content = f.read()

    # Pattern: templates.TemplateResponse("template_name", {context})
    # We need to insert `request, ` before the template name
    # But request is already in the context dict

    # Match single-line: templates.TemplateResponse("...", {...})
    pattern = r'templates\.TemplateResponse\(\s*\n?\s*"([^"]+)"'

    count = 0

    def replacer(match: re.Match) -> str:  # type: ignore
        nonlocal count
        count += 1
        template_name = match.group(1)
        # Check indentation
        full = match.group(0)
        if "\n" in full:
            # Multi-line version
            indent = full.split("\n")[-1].replace('"' + template_name + '"', "")
            return f'templates.TemplateResponse(\n{indent}request,\n{indent}"{template_name}"'
        else:
            return f'templates.TemplateResponse(\n            request,\n            "{template_name}"'

    new_content = re.sub(pattern, replacer, content)

    if count > 0:
        with open(filepath, "w") as f:
            f.write(new_content)
        print(f"Fixed {count} TemplateResponse calls in {filepath}")

    return count


files = [
    "services/api/festival_playlist_generator/web/routes.py",
    "services/api/festival_playlist_generator/web/auth_routes.py",
    "services/api/festival_playlist_generator/web/admin.py",
]

total = 0
for f in files:
    total += fix_file(f)

print(f"\nTotal: {total} fixes applied")
