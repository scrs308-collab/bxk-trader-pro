from __future__ import annotations

import ast
import re
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON_PACKAGE = PROJECT_ROOT / "bxk_app"
STATIC_DIR = PROJECT_ROOT / "static"

REPORT_FILE = PROJECT_ROOT / "project_audit_report.txt"
PROJECT_MAP_FILE = (
    PROJECT_ROOT
    / "docs"
    / "PROJECT"
    / "09_Project_Map.md"
)

IGNORED_DIRECTORIES = {
    ".git",
    ".idea",
    ".pytest_cache",
    ".venv",
    "venv",
    "__pycache__",
    "archive",
    "node_modules",
}

# Files that may legitimately be run directly rather than imported.
KNOWN_ENTRY_POINTS = {
    "server.py",
    "main.py",
    "backup.py",
    "bxk.py",
    "release.py",
    "version.py",
    "project_audit.py",
    "sdk_test.py",
    "sdk_dxlink_test.py",
}

# Modules that are often loaded indirectly or used as package markers.
SPECIAL_MODULES = {
    "__init__.py",
}


# ============================================================
# DATA MODELS
# ============================================================

@dataclass
class PythonFileInfo:
    path: Path
    module_name: str
    imports: set[str]
    local_imports: set[str]
    syntax_error: str | None = None


@dataclass
class FrontendFileInfo:
    path: Path
    references: set[str]


# ============================================================
# GENERAL HELPERS
# ============================================================

def is_ignored(path: Path) -> bool:
    """Return True when any path component is ignored."""
    return any(part in IGNORED_DIRECTORIES for part in path.parts)


def relative(path: Path) -> str:
    """Return a project-relative path using forward slashes."""
    try:
        return path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def read_text_safely(path: Path) -> str:
    """Read text while tolerating occasional encoding oddities."""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(
            encoding="utf-8",
            errors="replace",
        )


def discover_files(pattern: str) -> list[Path]:
    """Find project files while excluding ignored folders."""
    return sorted(
        path
        for path in PROJECT_ROOT.rglob(pattern)
        if path.is_file() and not is_ignored(path)
    )


# ============================================================
# PYTHON ANALYSIS
# ============================================================

def path_to_module(path: Path) -> str:
    """
    Convert a Python path to a dotted module name.

    Examples:
        bxk_app/scanner_engine.py
        -> bxk_app.scanner_engine

        bxk_app/services/__init__.py
        -> bxk_app.services
    """
    rel = path.relative_to(PROJECT_ROOT)

    parts = list(rel.with_suffix("").parts)

    if parts and parts[-1] == "__init__":
        parts.pop()

    return ".".join(parts)


def normalize_import_name(
    imported_name: str,
    known_modules: set[str],
) -> str | None:
    """
    Match an imported module to the most specific local module.

    Example:
        bxk_app.services.scanner_service.SomeClass
        becomes
        bxk_app.services.scanner_service
    """
    candidate = imported_name

    while candidate:
        if candidate in known_modules:
            return candidate

        if "." not in candidate:
            break

        candidate = candidate.rsplit(".", 1)[0]

    return None


def resolve_relative_import(
    current_module: str,
    level: int,
    imported_module: str | None,
) -> str:
    """
    Resolve Python relative imports.

    Example:
        current_module = bxk_app.services.scanner_service
        from ..scanner_engine import scan
    """
    current_parts = current_module.split(".")

    # A file module contributes its filename as the last component.
    package_parts = current_parts[:-1]

    if level > 0:
        remove_count = max(level - 1, 0)

        if remove_count:
            package_parts = package_parts[:-remove_count]

    if imported_module:
        package_parts.extend(imported_module.split("."))

    return ".".join(package_parts)


def extract_python_imports(
    path: Path,
    module_name: str,
) -> tuple[set[str], str | None]:
    """Parse all import statements from one Python file."""
    source = read_text_safely(path)

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        error = (
            f"Line {exc.lineno}: "
            f"{exc.msg}"
        )
        return set(), error

    imports: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)

        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = resolve_relative_import(
                    current_module=module_name,
                    level=node.level,
                    imported_module=node.module,
                )
            else:
                base = node.module or ""

            if base:
                imports.add(base)

            # Include possible submodule imports too.
            for alias in node.names:
                if alias.name == "*":
                    continue

                if base:
                    imports.add(
                        f"{base}.{alias.name}"
                    )
                else:
                    imports.add(alias.name)

    return imports, None


def analyze_python_files() -> dict[str, PythonFileInfo]:
    """Build Python module and local-import information."""
    python_paths = discover_files("*.py")

    module_by_path = {
        path: path_to_module(path)
        for path in python_paths
    }

    known_modules = set(module_by_path.values())
    results: dict[str, PythonFileInfo] = {}

    for path, module_name in module_by_path.items():
        imports, syntax_error = extract_python_imports(
            path,
            module_name,
        )

        local_imports: set[str] = set()

        for imported_name in imports:
            local_match = normalize_import_name(
                imported_name,
                known_modules,
            )

            if local_match:
                local_imports.add(local_match)

        results[module_name] = PythonFileInfo(
            path=path,
            module_name=module_name,
            imports=imports,
            local_imports=local_imports,
            syntax_error=syntax_error,
        )

    return results


def build_reverse_imports(
    python_files: dict[str, PythonFileInfo],
) -> dict[str, set[str]]:
    """Map each module to the local modules importing it."""
    reverse_imports: dict[str, set[str]] = defaultdict(set)

    for source_module, info in python_files.items():
        for target_module in info.local_imports:
            reverse_imports[target_module].add(
                source_module
            )

    return reverse_imports


def identify_entry_points(
    python_files: dict[str, PythonFileInfo],
) -> set[str]:
    """Identify likely application, tool, and script entry points."""
    entry_points: set[str] = set()

    for module_name, info in python_files.items():
        filename = info.path.name
        rel_path = relative(info.path)

        if filename in KNOWN_ENTRY_POINTS:
            entry_points.add(module_name)
            continue

        if rel_path.startswith("tools/"):
            entry_points.add(module_name)
            continue

        if rel_path.startswith("tests/"):
            entry_points.add(module_name)
            continue

        source = read_text_safely(info.path)

        if '__name__ == "__main__"' in source:
            entry_points.add(module_name)

    return entry_points


def reachable_modules(
    python_files: dict[str, PythonFileInfo],
    entry_points: set[str],
) -> set[str]:
    """
    Find all local modules reachable from known entry points.

    This is stronger than merely checking whether a filename appears
    somewhere, though dynamic imports can still evade static analysis.
    """
    visited: set[str] = set()
    queue: deque[str] = deque(entry_points)

    while queue:
        module_name = queue.popleft()

        if module_name in visited:
            continue

        if module_name not in python_files:
            continue

        visited.add(module_name)

        for imported_module in (
            python_files[module_name].local_imports
        ):
            if imported_module not in visited:
                queue.append(imported_module)

    return visited


def find_archive_candidates(
    python_files: dict[str, PythonFileInfo],
    reverse_imports: dict[str, set[str]],
    entry_points: set[str],
    reachable: set[str],
) -> list[str]:
    """
    Return modules that appear unreferenced.

    These are candidates for review, not automatic deletion.
    """
    candidates: list[str] = []

    for module_name, info in python_files.items():
        if info.path.name in SPECIAL_MODULES:
            continue

        if module_name in entry_points:
            continue

        imported_by = reverse_imports.get(
            module_name,
            set(),
        )

        if not imported_by and module_name not in reachable:
            candidates.append(module_name)

    return sorted(candidates)


def find_missing_local_imports(
    python_files: dict[str, PythonFileInfo],
) -> dict[str, set[str]]:
    """
    Identify imports beginning with bxk_app that do not map to a
    discovered local module.
    """
    known_modules = set(python_files)
    missing: dict[str, set[str]] = defaultdict(set)

    for source_module, info in python_files.items():
        for imported_name in info.imports:
            if not imported_name.startswith("bxk_app"):
                continue

            match = normalize_import_name(
                imported_name,
                known_modules,
            )

            if match is None:
                missing[source_module].add(
                    imported_name
                )

    return missing


def find_cycles(
    python_files: dict[str, PythonFileInfo],
) -> list[list[str]]:
    """Detect circular local-import paths using depth-first search."""
    graph = {
        module: set(info.local_imports)
        for module, info in python_files.items()
    }

    cycles: set[tuple[str, ...]] = set()
    visited: set[str] = set()
    active_stack: list[str] = []
    active_set: set[str] = set()

    def canonical_cycle(
        cycle: list[str],
    ) -> tuple[str, ...]:
        """
        Normalize cycle rotation so the same cycle is not repeated.
        """
        cycle_without_repeat = cycle[:-1]

        rotations = [
            tuple(
                cycle_without_repeat[index:]
                + cycle_without_repeat[:index]
            )
            for index in range(
                len(cycle_without_repeat)
            )
        ]

        smallest = min(rotations)
        return smallest + (smallest[0],)

    def visit(module: str) -> None:
        visited.add(module)
        active_stack.append(module)
        active_set.add(module)

        for neighbor in graph.get(module, set()):
            if neighbor not in graph:
                continue

            if neighbor not in visited:
                visit(neighbor)

            elif neighbor in active_set:
                start_index = active_stack.index(
                    neighbor
                )

                cycle = (
                    active_stack[start_index:]
                    + [neighbor]
                )

                cycles.add(
                    canonical_cycle(cycle)
                )

        active_stack.pop()
        active_set.remove(module)

    for module in graph:
        if module not in visited:
            visit(module)

    return [
        list(cycle)
        for cycle in sorted(cycles)
    ]


# ============================================================
# FRONTEND ANALYSIS
# ============================================================

REFERENCE_PATTERN = re.compile(
    r"""
    (?:
        src
        |
        href
        |
        import
        |
        from
    )
    \s*
    (?:
        =
        \s*
    )?
    ["']
    (?P<path>
        [^"'?#]+
        \.(?:js|css|html)
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)


def extract_frontend_references(
    path: Path,
) -> set[str]:
    """Extract JavaScript, CSS, and HTML references."""
    text = read_text_safely(path)

    references = {
        match.group("path")
        for match in REFERENCE_PATTERN.finditer(text)
    }

    return references


def analyze_frontend_files() -> dict[str, FrontendFileInfo]:
    """Analyze frontend files and their static references."""
    frontend_paths: list[Path] = []

    for extension in ("*.html", "*.js", "*.css"):
        frontend_paths.extend(
            discover_files(extension)
        )

    results: dict[str, FrontendFileInfo] = {}

    for path in sorted(set(frontend_paths)):
        rel_path = relative(path)

        results[rel_path] = FrontendFileInfo(
            path=path,
            references=extract_frontend_references(
                path
            ),
        )

    return results


def normalize_frontend_reference(
    source_path: Path,
    reference: str,
) -> Path:
    """Resolve a frontend reference to a project path."""
    cleaned = reference.lstrip("/")

    if reference.startswith("/static/"):
        return (
            PROJECT_ROOT
            / reference.lstrip("/")
        ).resolve()

    if cleaned.startswith("static/"):
        return (
            PROJECT_ROOT
            / cleaned
        ).resolve()

    return (
        source_path.parent
        / reference
    ).resolve()


def find_frontend_references(
    frontend_files: dict[str, FrontendFileInfo],
) -> dict[str, set[str]]:
    """Map each frontend file to files that reference it."""
    referenced_by: dict[str, set[str]] = defaultdict(
        set
    )

    path_to_relative = {
        info.path.resolve(): rel_path
        for rel_path, info in frontend_files.items()
    }

    for source_relative, info in (
        frontend_files.items()
    ):
        for reference in info.references:
            resolved = normalize_frontend_reference(
                info.path,
                reference,
            )

            target_relative = path_to_relative.get(
                resolved
            )

            if target_relative:
                referenced_by[target_relative].add(
                    source_relative
                )

    return referenced_by


def find_frontend_archive_candidates(
    frontend_files: dict[str, FrontendFileInfo],
    referenced_by: dict[str, set[str]],
) -> list[str]:
    """Find JS/CSS files not referenced by another frontend file."""
    candidates: list[str] = []

    for rel_path, info in frontend_files.items():
        if info.path.suffix == ".html":
            continue

        if info.path.name == "favicon.ico":
            continue

        if rel_path.startswith("archive/"):
            continue

        if not referenced_by.get(rel_path):
            candidates.append(rel_path)

    return sorted(candidates)


# ============================================================
# REPORTING
# ============================================================

def module_display(
    module_name: str,
    python_files: dict[str, PythonFileInfo],
) -> str:
    info = python_files[module_name]
    return relative(info.path)


def format_python_section(
    python_files: dict[str, PythonFileInfo],
    reverse_imports: dict[str, set[str]],
    entry_points: set[str],
    reachable: set[str],
    archive_candidates: list[str],
    missing_imports: dict[str, set[str]],
    cycles: list[list[str]],
) -> list[str]:
    lines: list[str] = []

    lines.extend(
        [
            "PYTHON SUMMARY",
            "--------------",
            f"Python files: {len(python_files)}",
            f"Entry points: {len(entry_points)}",
            f"Reachable modules: {len(reachable)}",
            (
                "Archive candidates: "
                f"{len(archive_candidates)}"
            ),
            "",
            "ENTRY POINTS",
            "------------",
        ]
    )

    for module_name in sorted(entry_points):
        lines.append(
            f"[ENTRY] "
            f"{module_display(module_name, python_files)}"
        )

    lines.extend(
        [
            "",
            "ARCHIVE CANDIDATES",
            "------------------",
        ]
    )

    if archive_candidates:
        for module_name in archive_candidates:
            lines.append(
                f"[REVIEW] "
                f"{module_display(module_name, python_files)}"
            )
    else:
        lines.append("None found.")

    lines.extend(
        [
            "",
            "PYTHON DEPENDENCY MAP",
            "---------------------",
        ]
    )

    for module_name in sorted(python_files):
        info = python_files[module_name]
        path_text = relative(info.path)

        lines.append(path_text)

        imported_by = sorted(
            reverse_imports.get(
                module_name,
                set(),
            )
        )

        if imported_by:
            lines.append("  Imported by:")

            for importer in imported_by:
                lines.append(
                    "    - "
                    + module_display(
                        importer,
                        python_files,
                    )
                )
        else:
            lines.append("  Imported by: none")

        if info.local_imports:
            lines.append("  Imports:")

            for imported_module in sorted(
                info.local_imports
            ):
                lines.append(
                    "    - "
                    + module_display(
                        imported_module,
                        python_files,
                    )
                )
        else:
            lines.append(
                "  Local imports: none"
            )

        if info.syntax_error:
            lines.append(
                "  SYNTAX ERROR: "
                + info.syntax_error
            )

        lines.append("")

    lines.extend(
        [
            "MISSING LOCAL IMPORTS",
            "---------------------",
        ]
    )

    if missing_imports:
        for source_module in sorted(
            missing_imports
        ):
            lines.append(
                module_display(
                    source_module,
                    python_files,
                )
            )

            for missing_name in sorted(
                missing_imports[source_module]
            ):
                lines.append(
                    f"  - {missing_name}"
                )
    else:
        lines.append("None found.")

    lines.extend(
        [
            "",
            "CIRCULAR IMPORTS",
            "----------------",
        ]
    )

    if cycles:
        for cycle in cycles:
            display_cycle = " -> ".join(
                module_display(
                    module_name,
                    python_files,
                )
                for module_name in cycle
            )
            lines.append(display_cycle)
    else:
        lines.append("None found.")

    return lines


def format_frontend_section(
    frontend_files: dict[str, FrontendFileInfo],
    referenced_by: dict[str, set[str]],
    archive_candidates: list[str],
) -> list[str]:
    lines: list[str] = [
        "",
        "FRONTEND SUMMARY",
        "----------------",
        f"Frontend files: {len(frontend_files)}",
        (
            "Archive candidates: "
            f"{len(archive_candidates)}"
        ),
        "",
        "FRONTEND ARCHIVE CANDIDATES",
        "---------------------------",
    ]

    if archive_candidates:
        for rel_path in archive_candidates:
            lines.append(
                f"[REVIEW] {rel_path}"
            )
    else:
        lines.append("None found.")

    lines.extend(
        [
            "",
            "FRONTEND REFERENCE MAP",
            "----------------------",
        ]
    )

    for rel_path in sorted(frontend_files):
        info = frontend_files[rel_path]

        lines.append(rel_path)

        sources = sorted(
            referenced_by.get(
                rel_path,
                set(),
            )
        )

        if sources:
            lines.append("  Referenced by:")

            for source in sources:
                lines.append(f"    - {source}")
        else:
            lines.append(
                "  Referenced by: none"
            )

        if info.references:
            lines.append(
                "  Declared references:"
            )

            for reference in sorted(
                info.references
            ):
                lines.append(
                    f"    - {reference}"
                )
        else:
            lines.append(
                "  Declared references: none"
            )

        lines.append("")

    return lines


def calculate_health_score(
    python_candidates: list[str],
    frontend_candidates: list[str],
    missing_imports: dict[str, set[str]],
    cycles: list[list[str]],
    syntax_errors: int,
) -> int:
    """Calculate a simple, deliberately conservative score."""
    score = 100

    score -= min(
        len(python_candidates) * 2,
        20,
    )

    score -= min(
        len(frontend_candidates) * 2,
        15,
    )

    missing_count = sum(
        len(values)
        for values in missing_imports.values()
    )

    score -= min(missing_count * 5, 30)
    score -= min(len(cycles) * 5, 20)
    score -= min(syntax_errors * 10, 30)

    return max(score, 0)


def write_text_report(
    python_files: dict[str, PythonFileInfo],
    reverse_imports: dict[str, set[str]],
    entry_points: set[str],
    reachable: set[str],
    python_candidates: list[str],
    missing_imports: dict[str, set[str]],
    cycles: list[list[str]],
    frontend_files: dict[str, FrontendFileInfo],
    frontend_referenced_by: dict[str, set[str]],
    frontend_candidates: list[str],
) -> int:
    syntax_errors = sum(
        1
        for info in python_files.values()
        if info.syntax_error
    )

    score = calculate_health_score(
        python_candidates=python_candidates,
        frontend_candidates=frontend_candidates,
        missing_imports=missing_imports,
        cycles=cycles,
        syntax_errors=syntax_errors,
    )

    timestamp = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    lines = [
        "=" * 60,
        "BXK TRADER PRO PROJECT AUDIT",
        "=" * 60,
        f"Generated: {timestamp}",
        f"Project root: {PROJECT_ROOT}",
        f"Project health score: {score}/100",
        "",
        (
            "NOTE: Archive candidates require human review. "
            "Dynamic imports and manually executed scripts may "
            "not appear in static dependency analysis."
        ),
        "",
    ]

    lines.extend(
        format_python_section(
            python_files=python_files,
            reverse_imports=reverse_imports,
            entry_points=entry_points,
            reachable=reachable,
            archive_candidates=python_candidates,
            missing_imports=missing_imports,
            cycles=cycles,
        )
    )

    lines.extend(
        format_frontend_section(
            frontend_files=frontend_files,
            referenced_by=frontend_referenced_by,
            archive_candidates=frontend_candidates,
        )
    )

    REPORT_FILE.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    return score


def write_markdown_map(
    python_files: dict[str, PythonFileInfo],
    reverse_imports: dict[str, set[str]],
    entry_points: set[str],
    python_candidates: list[str],
    frontend_files: dict[str, FrontendFileInfo],
    frontend_referenced_by: dict[str, set[str]],
    frontend_candidates: list[str],
    health_score: int,
) -> None:
    """Generate the reusable project map in Markdown."""
    PROJECT_MAP_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    lines = [
        "# BXK Trader Pro Project Map",
        "",
        f"Generated: `{timestamp}`",
        "",
        f"Project health score: **{health_score}/100**",
        "",
        (
            "> Archive candidates are files requiring review. "
            "They are not automatically safe to delete."
        ),
        "",
        "## Python entry points",
        "",
    ]

    for module_name in sorted(entry_points):
        lines.append(
            f"- `{module_display(module_name, python_files)}`"
        )

    lines.extend(
        [
            "",
            "## Python modules",
            "",
        ]
    )

    for module_name in sorted(python_files):
        info = python_files[module_name]
        path_text = relative(info.path)

        lines.append(f"### `{path_text}`")
        lines.append("")

        imported_by = sorted(
            reverse_imports.get(
                module_name,
                set(),
            )
        )

        if imported_by:
            lines.append("Imported by:")

            for importer in imported_by:
                lines.append(
                    "- `"
                    + module_display(
                        importer,
                        python_files,
                    )
                    + "`"
                )
        else:
            lines.append("Imported by: none detected.")

        lines.append("")

        if info.local_imports:
            lines.append("Local dependencies:")

            for dependency in sorted(
                info.local_imports
            ):
                lines.append(
                    "- `"
                    + module_display(
                        dependency,
                        python_files,
                    )
                    + "`"
                )
        else:
            lines.append(
                "Local dependencies: none detected."
            )

        lines.append("")

    lines.extend(
        [
            "## Python archive candidates",
            "",
        ]
    )

    if python_candidates:
        for module_name in python_candidates:
            lines.append(
                f"- `{module_display(module_name, python_files)}`"
            )
    else:
        lines.append("None detected.")

    lines.extend(
        [
            "",
            "## Frontend files",
            "",
        ]
    )

    for rel_path in sorted(frontend_files):
        lines.append(f"### `{rel_path}`")
        lines.append("")

        references = sorted(
            frontend_referenced_by.get(
                rel_path,
                set(),
            )
        )

        if references:
            lines.append("Referenced by:")

            for source in references:
                lines.append(f"- `{source}`")
        else:
            lines.append(
                "Referenced by: none detected."
            )

        lines.append("")

    lines.extend(
        [
            "## Frontend archive candidates",
            "",
        ]
    )

    if frontend_candidates:
        for rel_path in frontend_candidates:
            lines.append(f"- `{rel_path}`")
    else:
        lines.append("None detected.")

    lines.append("")

    PROJECT_MAP_FILE.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    print("=" * 60)
    print("BXK TRADER PRO PROJECT AUDIT")
    print("=" * 60)
    print(f"Scanning: {PROJECT_ROOT}")
    print()

    python_files = analyze_python_files()

    reverse_imports = build_reverse_imports(
        python_files
    )

    entry_points = identify_entry_points(
        python_files
    )

    reachable = reachable_modules(
        python_files,
        entry_points,
    )

    python_candidates = find_archive_candidates(
        python_files=python_files,
        reverse_imports=reverse_imports,
        entry_points=entry_points,
        reachable=reachable,
    )

    missing_imports = find_missing_local_imports(
        python_files
    )

    cycles = find_cycles(
        python_files
    )

    frontend_files = analyze_frontend_files()

    frontend_referenced_by = (
        find_frontend_references(
            frontend_files
        )
    )

    frontend_candidates = (
        find_frontend_archive_candidates(
            frontend_files,
            frontend_referenced_by,
        )
    )

    health_score = write_text_report(
        python_files=python_files,
        reverse_imports=reverse_imports,
        entry_points=entry_points,
        reachable=reachable,
        python_candidates=python_candidates,
        missing_imports=missing_imports,
        cycles=cycles,
        frontend_files=frontend_files,
        frontend_referenced_by=(
            frontend_referenced_by
        ),
        frontend_candidates=frontend_candidates,
    )

    write_markdown_map(
        python_files=python_files,
        reverse_imports=reverse_imports,
        entry_points=entry_points,
        python_candidates=python_candidates,
        frontend_files=frontend_files,
        frontend_referenced_by=(
            frontend_referenced_by
        ),
        frontend_candidates=frontend_candidates,
        health_score=health_score,
    )

    print(f"Python files: {len(python_files)}")
    print(
        "Python archive candidates: "
        f"{len(python_candidates)}"
    )
    print(
        "Frontend files: "
        f"{len(frontend_files)}"
    )
    print(
        "Frontend archive candidates: "
        f"{len(frontend_candidates)}"
    )
    print(
        "Circular imports: "
        f"{len(cycles)}"
    )
    print(
        "Project health score: "
        f"{health_score}/100"
    )
    print()
    print("Reports created:")
    print(f"  {relative(REPORT_FILE)}")
    print(f"  {relative(PROJECT_MAP_FILE)}")
    print()
    print(
        "Review candidates before moving anything. "
        "Software enjoys punishing confidence."
    )


if __name__ == "__main__":
    main()