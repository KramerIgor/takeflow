from __future__ import annotations

from pathlib import Path
import re


IMPORT_RE = re.compile(r'import\s+["\'](?P<path>[^"\']+)["\'];')


def static_js_files(project_root: Path) -> list[Path]:
    """Return the frontend JS entrypoint and imported modules in runtime order."""
    entry = project_root / "app" / "static" / "app.js"
    files = [entry]
    entry_text = entry.read_text(encoding="utf-8")

    for match in IMPORT_RE.finditer(entry_text):
        imported_path = match.group("path").split("?", 1)[0]
        imported = (entry.parent / imported_path).resolve()
        if imported not in files:
            files.append(imported)

    static_root = project_root / "app" / "static"
    for extra in sorted(static_root.rglob("*.js")):
        resolved = extra.resolve()
        if resolved not in files:
            files.append(resolved)

    return files


def read_static_js(project_root: Path) -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in static_js_files(project_root))
