"""The architecture rules from `src/resume_parsing/AGENTS.md`, as tests.

These run under plain pytest with no extra tooling, so a rule violation fails
the ordinary test command rather than waiting for a separate lint step.
`.importlinter` checks the same rules against the full import graph; this file
is the fast, dependency-free copy.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

MODULE = Path(__file__).resolve().parents[2] / "src" / "resume_parsing"
INTERNAL = MODULE / "internal"


def imported_modules(path: Path) -> set[str]:
    """Every module name a file imports, absolute and relative alike."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
    return names


def python_files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)


# --------------------------------------------------------------------------- #
# Rule 3 — routers never touch the database
# --------------------------------------------------------------------------- #

FORBIDDEN_IN_ROUTER = (
    "sqlalchemy",
    "asyncpg",
    "src.core.db",
    "src.resume_parsing.internal",
    "psycopg",
)


def test_router_never_touches_persistence_or_internals() -> None:
    imports = imported_modules(MODULE / "router.py")
    offenders = sorted(
        name
        for name in imports
        for banned in FORBIDDEN_IN_ROUTER
        if name == banned or name.startswith(f"{banned}.")
    )
    assert not offenders, (
        "router.py must reach the module through service.py only. "
        f"Forbidden imports found: {offenders}. See AGENTS.md rule 3."
    )


def test_router_stays_thin() -> None:
    lines = (MODULE / "router.py").read_text(encoding="utf-8").splitlines()
    assert len(lines) < 130, (
        "router.py has grown past 130 lines, which means logic has leaked into "
        "the transport layer. Move it into internal/service_impl.py."
    )


# --------------------------------------------------------------------------- #
# Rule 1 — internals are private
# --------------------------------------------------------------------------- #


def test_internals_are_not_imported_from_outside_the_module() -> None:
    src = MODULE.parent
    outsiders = [
        path
        for path in python_files(src)
        if MODULE not in path.parents and path != MODULE
        for name in imported_modules(path)
        if name.startswith("src.resume_parsing.internal")
    ]
    assert not outsiders, (
        "internal/ is private to the module. Imported from: "
        f"{[str(p) for p in outsiders]}. See AGENTS.md rule 1."
    )


def test_only_dependencies_reaches_into_internal() -> None:
    """Inside the module, `dependencies.py` is the sole composition root."""
    allowed = {"dependencies.py"}
    offenders = [
        path.name
        for path in python_files(MODULE)
        if INTERNAL not in path.parents
        and path.name not in allowed
        and any(
            name.startswith("src.resume_parsing.internal")
            for name in imported_modules(path)
        )
    ]
    assert not offenders, (
        f"Only dependencies.py may build internals; {offenders} also does. "
        "See AGENTS.md § Layering."
    )


# --------------------------------------------------------------------------- #
# Rule 2 — the contract is the seam
# --------------------------------------------------------------------------- #


def test_contract_declares_every_operation_the_router_uses() -> None:
    """Every `service.<method>` call in the router must exist on the Protocol."""
    contract = ast.parse((MODULE / "service.py").read_text(encoding="utf-8"))
    protocol = next(
        node
        for node in ast.walk(contract)
        if isinstance(node, ast.ClassDef) and node.name == "ResumeParsingService"
    )
    declared = {
        node.name
        for node in protocol.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }

    router = ast.parse((MODULE / "router.py").read_text(encoding="utf-8"))
    used = {
        node.func.attr
        for node in ast.walk(router)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "service"
    }
    assert used <= declared, (
        f"router.py calls {sorted(used - declared)} which service.py does not "
        "declare. Extend the contract first. See AGENTS.md rule 2."
    )


# --------------------------------------------------------------------------- #
# SQL is confined to the repository
# --------------------------------------------------------------------------- #


def test_only_repository_and_models_import_sqlalchemy() -> None:
    allowed = {INTERNAL / "repository.py", INTERNAL / "models.py"}
    offenders = [
        str(path.relative_to(MODULE))
        for path in python_files(INTERNAL)
        if path not in allowed
        and any(name.split(".")[0] in {"sqlalchemy", "asyncpg"} for name in imported_modules(path))
    ]
    assert not offenders, (
        f"SQL belongs in internal/repository.py; {offenders} import it too."
    )


# --------------------------------------------------------------------------- #
# Pipeline stages stay pure
# --------------------------------------------------------------------------- #

IO_MODULES = {"sqlalchemy", "asyncpg", "google", "httpx", "requests", "aiohttp"}


@pytest.mark.parametrize(
    "stage",
    ["routing.py", "preprocess.py", "postprocess.py", "validation.py"],
)
def test_pipeline_stages_do_no_io(stage: str) -> None:
    imports = imported_modules(INTERNAL / "pipeline" / stage)
    offenders = sorted(name for name in imports if name.split(".")[0] in IO_MODULES)
    assert not offenders, (
        f"pipeline/{stage} must stay a pure function over domain values; it "
        f"imports {offenders}. Orchestration and I/O belong in service_impl.py."
    )


# --------------------------------------------------------------------------- #
# PII contract
# --------------------------------------------------------------------------- #

BANNED_FIELDS = (
    "email",
    "phone",
    "date_of_birth",
    "dob",
    "gender",
    "marital_status",
    "nationality",
    "father_name",
    "spouse_name",
    "photo",
    "aadhaar",
    "passport",
)


def test_schema_excludes_pii_fields() -> None:
    schema = json.loads(
        (INTERNAL / "prompts" / "parsed_resume_schema.json").read_text(encoding="utf-8")
    )
    found: list[str] = []

    def walk(node: object, path: str = "") -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if path.endswith("properties") and key.lower() in BANNED_FIELDS:
                    found.append(f"{path}.{key}")
                walk(value, f"{path}.{key}" if path else key)
        elif isinstance(node, list):
            for item in node:
                walk(item, path)

    walk(schema)
    assert not found, f"PII fields must never enter the schema: {found}"


def test_schema_rejects_unknown_fields_everywhere() -> None:
    """`additionalProperties: false` *is* the PII enforcement, not a style choice."""
    schema = json.loads(
        (INTERNAL / "prompts" / "parsed_resume_schema.json").read_text(encoding="utf-8")
    )
    permissive: list[str] = []

    def walk(node: object, path: str = "root") -> None:
        if isinstance(node, dict):
            if node.get("type") == "object" and node.get("additionalProperties") is not False:
                permissive.append(path)
            for key, value in node.items():
                walk(value, f"{path}.{key}")
        elif isinstance(node, list):
            for i, item in enumerate(node):
                walk(item, f"{path}[{i}]")

    walk(schema)
    assert not permissive, (
        f"These objects accept unknown keys, so a transcribed email would pass "
        f"validation: {permissive}"
    )


def test_wire_schemas_declare_no_pii() -> None:
    source = (MODULE / "schemas.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    fields = {
        node.target.id
        for node in ast.walk(tree)
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }
    offenders = sorted(fields & set(BANNED_FIELDS))
    assert not offenders, f"schemas.py declares PII fields: {offenders}"
