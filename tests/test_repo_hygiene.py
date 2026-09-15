"""Repository hygiene: the budget and boundary rules `AGENTS.md` makes non-negotiable.

Every assertion is a plain `ast` or text scan over the repository's own files; nothing
here imports `invoice_extractor`, so these checks still report a real result when the
package itself is broken.
"""

from __future__ import annotations

import ast
import re
import tomllib
from collections.abc import Iterator
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"
# Two distributions are built from this one tree: the engine at the root, and the
# generator it is proved against under `tools/forge/`. A rule about "the packaging"
# means both, or the half it does not read is the half that ships broken.
PYPROJECTS = (PYPROJECT, REPO_ROOT / "tools" / "forge" / "pyproject.toml")
SRC = REPO_ROOT / "src"
EXTRACTOR = SRC / "invoice_extractor"
FORGE = SRC / "invoice_forge"

MAX_MODULE_LINES = 250
MAX_FUNCTION_LINES = 40

# The only two modules allowed to import the PDF library: the extractor reads with it,
# the generator writes with it, and nothing else knows it exists. `pymupdf` is the modern
# import name; `fitz` is the deprecated alias, which prints a warning on every import.
PDF_MODULES = (EXTRACTOR / "document" / "pymupdf_reader.py", FORGE / "render" / "pdf.py")
# Where money lives in each package. `float` is not called there (ADR-0003).
MONEY_LAYERS = (EXTRACTOR / "domain", FORGE / "model")

# Assembled from halves so this file, which `test_no_todo_markers` scans, is not itself
# the violation it looks for.
UNFINISHED_MARKERS = tuple(
    head + tail for head, tail in (("TO", "DO"), ("FIX", "ME"), ("XX", "X"), ("HA", "CK"))
)
SUPPRESSION_MARKERS = ("# noqa", "# type: ignore")

# Requiring a word character after the prefix is what separates a real leaked path from
# a document quoting the rule itself, as Appendix A of the implementation plan does.
ABSOLUTE_PATH_PATTERNS = (
    re.compile(r"/home/\w"),
    re.compile(r"/Users/\w"),
    re.compile(r"C:\\\w"),
)
EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
URL_PATTERN = re.compile(r"https?://")

# Markdown does not render a link inside a code span, so neither does the link check —
# docs/IMPLEMENTATION_PLAN.md states this very rule with the syntax quoted in backticks.
FENCED_CODE = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE = re.compile(r"`[^`]*`")
MARKDOWN_LINK = re.compile(r"\]\(([^)\s]+)")

TEXT_SUFFIXES = frozenset({".py", ".md", ".json", ".toml", ".yml", ".yaml", ".cfg", ".txt"})
TEXT_FILENAMES = frozenset({"Makefile", "make.ps1", "LICENSE", ".gitignore"})
IGNORED_DIRS = frozenset(
    {".git", ".venv", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache", "build", "dist"}
)
PROSE_ROOTS = ("src", "tests", "scripts", "docs")
URL_ALLOWED_ROOTS = frozenset({"docs", ".github"})
URL_ALLOWED_FILES = frozenset(
    {
        "README.md",
        "CONTRIBUTING.md",
        "tools/forge/README.md",
        ".pre-commit-config.yaml",
        "pyproject.toml",
        "tools/forge/pyproject.toml",
        # The bundled fonts' licence is third-party text, reproduced as it must be.
        "src/invoice_forge/fonts/LICENSE",
    }
)


def walk(root: Path) -> Iterator[Path]:
    """Every file under `root`, skipping caches, virtualenvs and build output."""
    if not root.is_dir():
        return
    for entry in sorted(root.iterdir()):
        if entry.name in IGNORED_DIRS or entry.name.endswith(".egg-info"):
            continue
        if entry.is_dir():
            yield from walk(entry)
        elif entry.is_file():
            yield entry


def python_modules(root: Path) -> list[Path]:
    return [path for path in walk(root) if path.suffix == ".py"]


def source_modules() -> list[Path]:
    return python_modules(SRC)


def is_text(path: Path) -> bool:
    return path.suffix in TEXT_SUFFIXES or path.name in TEXT_FILENAMES


def prose_files() -> list[Path]:
    """The set `test_no_absolute_paths` and `test_no_email_addresses` scan."""
    files = [REPO_ROOT / "README.md"]
    for root in PROSE_ROOTS:
        files.extend(path for path in walk(REPO_ROOT / root) if is_text(path))
    return files


def repo_text_files() -> list[Path]:
    return [path for path in walk(REPO_ROOT) if is_text(path)]


def counted_lines(path: Path) -> int:
    """Non-blank, non-comment lines — the unit `AGENTS.md` states the size budget in."""
    stripped = (line.strip() for line in path.read_text(encoding="utf-8").splitlines())
    return sum(1 for line in stripped if line and not line.startswith("#"))


def parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def numbered_lines(path: Path) -> Iterator[tuple[int, str]]:
    return enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)


def where(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def call_sites(modules: list[Path], function_name: str) -> list[str]:
    return [
        f"{where(module)}:{node.lineno}"
        for module in modules
        for node in ast.walk(parse(module))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == function_name
    ]


def imports_module(module: Path, name: str) -> bool:
    for node in ast.walk(parse(module)):
        if isinstance(node, ast.Import) and any(alias.name == name for alias in node.names):
            return True
        if isinstance(node, ast.ImportFrom) and node.module == name:
            return True
    return False


def imports_name(module: Path, name: str) -> bool:
    return any(
        isinstance(node, ast.Import | ast.ImportFrom)
        and any(alias.name == name for alias in node.names)
        for node in ast.walk(parse(module))
    )


def decorator_name(node: ast.expr) -> str | None:
    target = node.func if isinstance(node, ast.Call) else node
    if isinstance(target, ast.Attribute):
        return target.attr
    return target.id if isinstance(target, ast.Name) else None


def declares_frozen(decorator: ast.expr) -> bool:
    if not isinstance(decorator, ast.Call):
        return False
    return any(
        keyword.arg == "frozen"
        and isinstance(keyword.value, ast.Constant)
        and keyword.value.value is True
        for keyword in decorator.keywords
    )


def test_no_module_over_250_lines() -> None:
    sizes = {where(module): counted_lines(module) for module in source_modules()}
    oversized = {name: size for name, size in sizes.items() if size > MAX_MODULE_LINES}
    assert not oversized, f"modules over {MAX_MODULE_LINES} counted lines: {oversized}"


def test_no_function_over_40_lines() -> None:
    oversized = [
        f"{where(module)}:{node.name} spans {node.end_lineno - node.lineno + 1} lines"
        for module in source_modules()
        for node in ast.walk(parse(module))
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        and node.end_lineno is not None
        and node.end_lineno - node.lineno + 1 > MAX_FUNCTION_LINES
    ]
    assert not oversized, f"functions over {MAX_FUNCTION_LINES} lines: {oversized}"


def test_pymupdf_imported_only_in_the_two_pdf_modules() -> None:
    allowed = set(PDF_MODULES)
    importers = {module for module in source_modules() if imports_module(module, "pymupdf")}
    strays = sorted(where(module) for module in importers - allowed)
    assert not strays, f"pymupdf imported outside the two PDF modules: {strays}"
    # Each module arrives with its own pull request; until then the rule holds vacuously.
    for module in PDF_MODULES:
        if module.exists():
            assert module in importers, f"{where(module)} is a module that must import pymupdf"


def test_no_float_calls_in_the_money_layers() -> None:
    modules = [module for layer in MONEY_LAYERS for module in python_modules(layer)]
    offenders = call_sites(modules, "float")
    assert not offenders, f"float() called where money lives: {offenders}"


def test_no_print_in_source() -> None:
    offenders = call_sites(source_modules(), "print")
    assert not offenders, f"print() called in src/: {offenders}"


def test_no_todo_markers() -> None:
    scanned = source_modules() + python_modules(REPO_ROOT / "tests")
    offenders = [
        f"{where(path)}:{number}"
        for path in scanned
        for number, line in numbered_lines(path)
        if any(marker in line for marker in UNFINISHED_MARKERS)
    ]
    assert not offenders, f"unfinished-work markers left behind: {offenders}"


def test_suppressions_carry_justification() -> None:
    offenders = [
        f"{where(path)}:{number}"
        for path in source_modules()
        for number, line in numbered_lines(path)
        for marker in SUPPRESSION_MARKERS
        if marker in line and "#" not in line.split(marker, 1)[1]
    ]
    assert not offenders, f"suppressions with no stated reason: {offenders}"


def test_no_absolute_paths() -> None:
    offenders = [
        f"{where(path)}:{number}"
        for path in prose_files()
        for number, line in numbered_lines(path)
        if any(pattern.search(line) for pattern in ABSOLUTE_PATH_PATTERNS)
    ]
    assert not offenders, f"machine-specific absolute paths: {offenders}"


def test_no_email_addresses() -> None:
    offenders = [
        where(path)
        for path in prose_files()
        if EMAIL_PATTERN.search(path.read_text(encoding="utf-8"))
    ]
    assert not offenders, f"email addresses committed: {offenders}"


def test_no_urls_outside_docs() -> None:
    offenders = [
        where(path)
        for path in repo_text_files()
        if path.relative_to(REPO_ROOT).parts[0] not in URL_ALLOWED_ROOTS
        and where(path) not in URL_ALLOWED_FILES
        and URL_PATTERN.search(path.read_text(encoding="utf-8"))
    ]
    assert not offenders, f"URLs outside README, docs, CI config and packaging: {offenders}"


def test_public_api_has_no_any() -> None:
    offenders = [where(module) for module in source_modules() if imports_name(module, "Any")]
    assert not offenders, f"`Any` imported under src/: {offenders}"


def test_markdown_links_resolve() -> None:
    offenders = [
        f"{where(document)} -> {target}"
        for document in repo_text_files()
        if document.suffix == ".md"
        for target in _link_targets(document)
        if not (document.parent / target).exists()
    ]
    assert not offenders, f"markdown links pointing at nothing: {offenders}"


def _link_targets(document: Path) -> list[str]:
    """Every relative link target in a document, code spans and anchors excluded."""
    text = document.read_text(encoding="utf-8")
    prose = INLINE_CODE.sub("", FENCED_CODE.sub("", text))
    found = (target.split("#")[0] for target in MARKDOWN_LINK.findall(prose))
    return [target for target in found if target and "://" not in target]


def declared_data() -> list[tuple[str, str]]:
    """Every (package, glob) either distribution says it ships."""
    return [
        (package, pattern)
        for pyproject in PYPROJECTS
        for package, patterns in tomllib.loads(pyproject.read_text(encoding="utf-8"))["tool"][
            "setuptools"
        ]["package-data"].items()
        for pattern in patterns
    ]


def test_every_declared_data_file_exists() -> None:
    """A data glob that matches nothing is a file that will be missing from the wheel."""
    offenders = [
        f"{package}: {pattern}"
        for package, pattern in declared_data()
        if not list((SRC / package).glob(pattern))
    ]
    assert not offenders, f"package data declared but not present: {offenders}"


def test_every_data_file_under_source_is_declared() -> None:
    """The other direction: a JSON file inside a package that no glob ships.

    Read across both distributions, because a file is shipped by whichever one owns it:
    the profiles and lexicons travel with the engine, the catalogues with the generator.
    """
    packaged = {
        path for package, pattern in declared_data() for path in (SRC / package).glob(pattern)
    }
    offenders = [where(path) for path in sorted(SRC.rglob("*.json")) if path not in packaged]
    assert not offenders, f"data files that would not ship: {offenders}"


def test_dataclasses_are_frozen() -> None:
    offenders = [
        f"{where(module)}:{node.name}"
        for module in source_modules()
        for node in ast.walk(parse(module))
        if isinstance(node, ast.ClassDef)
        for decorator in node.decorator_list
        if decorator_name(decorator) == "dataclass" and not declares_frozen(decorator)
    ]
    assert not offenders, f"dataclasses declared without frozen=True: {offenders}"


def test_no_module_without_an_importer() -> None:
    """Every module under `src/` is reached from somewhere (`docs/ENGINE_PLAN.md` §4).

    The other two halves of that rule are held elsewhere — `tests/test_unit_registry.py`
    for units nothing names, `tests/test_profile_contract.py` for profile keys nothing
    reads. This is the third: a module nothing imports is code that cannot run, and the
    only way to find out is to look for the import.

    `from pkg import module` counts, which is how the loaders reach their helpers; and
    `__init__.py` and `__main__.py` are not modules with importers but the package and
    its entry point.
    """
    named = {_dotted(path): path for path in source_modules() if _is_a_module(path)}
    reached = _imported_anywhere()
    orphans = sorted(where(path) for name, path in named.items() if name not in reached)
    assert not orphans, f"modules nothing imports: {orphans}"


def _is_a_module(path: Path) -> bool:
    return path.stem not in ("__init__", "__main__")


def _dotted(path: Path) -> str:
    return ".".join(path.relative_to(SRC).with_suffix("").parts)


def _imported_anywhere() -> set[str]:
    """Every module name any Python file in the repository imports, by either spelling."""
    reached: set[str] = set()
    for root in (SRC, REPO_ROOT / "tests", REPO_ROOT / "benchmarks", REPO_ROOT / "scripts"):
        for path in python_modules(root):
            for node in ast.walk(parse(path)):
                reached.update(_named(node))
    return reached


def _named(node: ast.AST) -> set[str]:
    if isinstance(node, ast.ImportFrom) and node.module:
        return {node.module, *(f"{node.module}.{alias.name}" for alias in node.names)}
    if isinstance(node, ast.Import):
        return {alias.name for alias in node.names}
    return set()
