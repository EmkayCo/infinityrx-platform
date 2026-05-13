"""Float-vs-Decimal regression test (repo-level).

Prevents float type annotations and sa.Float SQLAlchemy columns from
appearing in money-relevant source paths.  Runs fast (<5 s) via in-process
AST walking.

Rule references
---------------
- CLAUDE.md non-negotiable #1: "Decimal with ROUND_HALF_UP for all money.
  No floats. Ever."
- .claude/rules/financial-precision.md — full rule list including
  sa.Numeric requirement and sa.Float prohibition.

Condition 3 (func.sum wrapping) is reviewer-enforced per the brief's
recommendation (option a) — static detection is too fragile and would
produce excessive false-positives.  The rule is documented in
.claude/rules/financial-precision.md.

Wave 41.6 M7.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import NamedTuple

import pytest

# ---------------------------------------------------------------------------
# Repo root — two levels up from tests/repo/
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Money-relevant directory globs.
# These are the paths the financial-precision rules apply to.
# ---------------------------------------------------------------------------
_MONEY_GLOBS: tuple[str, ...] = (
    "modules/*/src/*/services/**/*.py",
    "modules/*/src/*/models/**/*.py",
    "modules/*/src/*/schemas/**/*.py",
    "modules/*/src/*/events/**/*.py",
    "modules/*/src/*/remittance/**/*.py",
    "modules/*/src/*/billing/**/*.py",
    # paysync uses a nested src/paysync/… layout
    "modules/paysync/src/paysync/models/**/*.py",
    "modules/paysync/src/paysync/remittance/**/*.py",
    # reclaimrx uses src/reclaimrx/… nested layout
    "modules/reclaimrx/src/reclaimrx/**/*.py",
    "modules/reclaimrx/src/services/**/*.py",
    "modules/reclaimrx/src/events/**/*.py",
    # switch-connectivity services
    "modules/switch-connectivity/src/services/**/*.py",
    # adjudication-engine api (schemas live there)
    "modules/adjudication-engine/src/api/**/*.py",
    "modules/adjudication-engine/src/services/**/*.py",
    "modules/adjudication-engine/src/models/**/*.py",
    "modules/adjudication-engine/src/events/**/*.py",
    # shared money utilities and models
    "shared/utils/money.py",
    "shared/db/models/**/*.py",
    "shared/models/**/*.py",
)

# Exclude worktrees — they are parallel in-flight branches, not production
# source, and would generate spurious findings for work-in-progress code.
_EXCLUDE_DIRS: tuple[str, ...] = (
    ".claude/worktrees",
    ".venv",
    "__pycache__",
    "node_modules",
)


class _FloatHit(NamedTuple):
    rel_path: str
    lineno: int
    reason: str  # what kind of hit it is


# ---------------------------------------------------------------------------
# ALLOWLIST
#
# Format: (relative_path_from_repo_root, lineno) → human_reason
#
# Only allowlist floats that are PROVABLY NOT money values.
# Allowed categories: ML scores (0-1 probability), clinical measurements
# (BMI), timing (seconds/ms), rate-limiting tokens, compliance percentages,
# statistical aggregates used as ML features.
#
# DO NOT allowlist anything that is, or could become, a dollar amount.
# ---------------------------------------------------------------------------
KNOWN_LEGITIMATE_FLOAT_USES: dict[tuple[str, int], str] = {
    # --- prior-authorization: BMI is a clinical measurement, not money ---
    ("modules/prior-authorization/src/models/tables.py", 229): "glp1_bmi_threshold: clinical BMI measurement, not money",
    ("modules/prior-authorization/src/api/schemas.py", 66): "member_bmi: clinical BMI measurement, not money",
    ("modules/prior-authorization/src/services/pa_lifecycle.py", 128): "member_bmi: clinical BMI measurement, not money",
    ("modules/prior-authorization/src/services/criteria_engine.py", 43): "member_bmi: clinical BMI measurement, not money",
    ("modules/prior-authorization/src/services/criteria_engine.py", 270): "member_bmi: clinical BMI measurement, not money",

    # --- edi-compliance: denial scoring uses 0-1 risk scores and weights ---
    ("modules/edi-compliance/src/services/denial_scoring.py", 31): "weight: ML rule weight (0-1 score component), not money",
    ("modules/edi-compliance/src/services/denial_scoring.py", 36): "score: denial risk score 0.0-1.0, not money",
    ("modules/edi-compliance/src/services/denial_scoring.py", 43): "_HIGH_THRESHOLD: risk score threshold 0-1, not money",
    ("modules/edi-compliance/src/services/denial_scoring.py", 44): "_MEDIUM_THRESHOLD: risk score threshold 0-1, not money",
    ("modules/edi-compliance/src/services/denial_scoring.py", 47): "_risk_level param: risk score 0-1, not money",
    # --- edi-compliance: SLA monitoring uses elapsed time and compliance % ---
    ("modules/edi-compliance/src/services/sla_monitoring.py", 35): "at_risk_threshold_pct: fraction of SLA window (time ratio), not money",
    ("modules/edi-compliance/src/services/sla_monitoring.py", 59): "elapsed_minutes: time measurement, not money",
    ("modules/edi-compliance/src/services/sla_monitoring.py", 72): "acknowledgment_compliance_pct: SLA compliance percentage, not money",
    ("modules/edi-compliance/src/services/sla_monitoring.py", 73): "response_compliance_pct: SLA compliance percentage, not money",
    ("modules/edi-compliance/src/services/sla_monitoring.py", 76): "compute_elapsed_minutes return: time duration, not money",
    # --- edi-compliance: API acceptance rate percentage ---
    ("modules/edi-compliance/src/api/compliance.py", 41): "acceptance_rate_pct: transaction acceptance rate (%), not money",

    # --- adjudication-engine reclaimrx routes: ML fraud scores ---
    ("modules/adjudication-engine/src/api/reclaimrx_routes.py", 1751): "score_threshold_override: ML fraud score threshold (0-1), not money",
    ("modules/adjudication-engine/src/api/reclaimrx_routes.py", 1765): "score_threshold_override: ML fraud score threshold (0-1), not money",
    ("modules/adjudication-engine/src/api/reclaimrx_routes.py", 1963): "score: ML fraud detection score (0-1), not money",
    # --- adjudication-engine rate limiter: token bucket timing ---
    ("modules/adjudication-engine/src/services/rate_limiter.py", 48): "tokens: rate-limiter token bucket count, not money",
    ("modules/adjudication-engine/src/services/rate_limiter.py", 49): "last_refill: monotonic clock timestamp, not money",

    # --- reclaimrx scrutiny service: ML score thresholds ---
    ("modules/reclaimrx/src/reclaimrx/scrutiny/service.py", 43): "score_threshold_override: ML fraud score threshold (0-1), not money",
    ("modules/reclaimrx/src/reclaimrx/scrutiny/service.py", 93): "score_threshold_override param: ML fraud score threshold (0-1), not money",
    ("modules/reclaimrx/src/reclaimrx/scrutiny/service.py", 242): "get_score_threshold_override return: ML score threshold (0-1), not money",
    ("modules/reclaimrx/src/reclaimrx/scrutiny/service.py", 259): "rule_default_threshold param: ML score threshold (0-1), not money",
    ("modules/reclaimrx/src/reclaimrx/scrutiny/service.py", 260): "_resolve_threshold return: ML score threshold (0-1), not money",
    # --- reclaimrx events: graph analysis rates (ML feature) ---
    ("modules/reclaimrx/src/events/publishers.py", 179): "self_referral_rate: network graph ML feature (ratio), not money",
    # --- reclaimrx graph analysis service: network analysis scores ---
    ("modules/reclaimrx/src/services/graph_analysis.py", 55): "self_referral_rate: network graph ML feature (ratio), not money",
    ("modules/reclaimrx/src/services/graph_analysis.py", 56): "geographic_spread_score: ML geographic clustering score, not money",
    ("modules/reclaimrx/src/services/graph_analysis.py", 178): "self_referral_rate param: network graph ML feature (ratio), not money",

    # --- ai-nlp: confidence scores from document-intelligence / RAG ---
    ("modules/ai-nlp/src/api/schemas/responses.py", 14): "confidence_score: AI extraction confidence (0-1), not money",
    ("modules/ai-nlp/src/api/schemas/responses.py", 21): "confidence: per-field extraction confidence (0-1), not money",
    ("modules/ai-nlp/src/api/schemas/responses.py", 28): "overall_confidence: document-level extraction confidence (0-1), not money",
    ("modules/ai-nlp/src/api/schemas/responses.py", 43): "confidence: chatbot RAG response confidence (0-1), not money",

    # --- program-config: workflow progress percentage ---
    ("modules/program-config/src/api/schemas/programs.py", 293): "percent_complete: workflow progress percentage (0-100), not money",

    # --- reclaimrx ml detection: sklearn feature extraction helpers ---
    ("modules/reclaimrx/src/reclaimrx/detection/ml/sklearn_detector.py", 256): "_to_float helper: coerces feature values for sklearn input, not money",
    ("modules/reclaimrx/src/reclaimrx/detection/ml/sklearn_detector.py", 303): "_fv helper: extracts numeric feature value for sklearn, not money",

    # --- reclaimrx ml_scoring: synthetic training generator + feature extractor ---
    ("modules/reclaimrx/src/services/ml_scoring.py", 151): "fraud_rate param: synthetic training data positive-class rate (0-1), not money",
    ("modules/reclaimrx/src/services/ml_scoring.py", 278): "fval feature extractor: numeric feature default + return for ML input, not money",
}


# ---------------------------------------------------------------------------
# SQLAlchemy Float column allowlist
# (path, lineno) → reason
# Currently empty — no sa.Float found in money model files.
# Add entries here if a legitimate non-money Float column is ever needed.
# ---------------------------------------------------------------------------
KNOWN_LEGITIMATE_SA_FLOAT_COLUMNS: dict[tuple[str, int], str] = {}


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

def _is_excluded(path: Path) -> bool:
    parts = path.parts
    return any(excl in parts for excl in _EXCLUDE_DIRS)


def _discover_money_files() -> list[Path]:
    """Return all .py files in money-relevant directories."""
    found: list[Path] = []
    seen: set[Path] = set()
    for glob in _MONEY_GLOBS:
        for path in _REPO_ROOT.glob(glob):
            if path in seen:
                continue
            if _is_excluded(path):
                continue
            seen.add(path)
            found.append(path)
    return sorted(found)


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------

def _rel(path: Path) -> str:
    # POSIX form so allowlist keys (forward slashes) match cross-platform.
    # On Windows, str(Path.relative_to(...)) uses backslashes and silently
    # misses every allowlist entry; using as_posix() makes the lookup OS-agnostic.
    return path.relative_to(_REPO_ROOT).as_posix()


def _parse(path: Path) -> ast.Module | None:
    try:
        source = path.read_text(encoding="utf-8")
        return ast.parse(source, filename=str(path))
    except SyntaxError:
        return None


def _annotation_is_float(node: ast.expr | None) -> bool:
    """Return True if the annotation resolves to (bare) float.

    Matches: ``float``, ``float | None``, ``Optional[float]``,
    ``Union[float, None]``.  Does NOT match ``list[float]``,
    ``dict[str, float]``, or compound types beyond the simple nullable
    pattern — those are rare in signatures and would need explicit
    review if they appear.
    """
    if node is None:
        return False
    # Bare `float`
    if isinstance(node, ast.Name) and node.id == "float":
        return True
    # `float | None` or `None | float` (Python 3.10+ union syntax)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        left_float = isinstance(node.left, ast.Name) and node.left.id == "float"
        right_none = isinstance(node.right, ast.Constant) and node.right.value is None
        right_float = isinstance(node.right, ast.Name) and node.right.id == "float"
        left_none = isinstance(node.left, ast.Constant) and node.left.value is None
        if (left_float and right_none) or (left_none and right_float):
            return True
    # `Optional[float]` or `Union[float, None]`
    if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
        name = node.value.id
        if name == "Optional":
            inner = node.slice
            if isinstance(inner, ast.Name) and inner.id == "float":
                return True
        if name == "Union" and isinstance(node.slice, ast.Tuple):
            elts = node.slice.elts
            has_float = any(isinstance(e, ast.Name) and e.id == "float" for e in elts)
            has_none = any(isinstance(e, ast.Constant) and e.value is None for e in elts)
            if has_float and has_none and len(elts) == 2:
                return True
    return False


def _collect_float_annotations(tree: ast.Module, rel_path: str) -> list[_FloatHit]:
    """Walk AST, collect all float-annotated sites not in the allowlist."""
    hits: list[_FloatHit] = []

    for node in ast.walk(tree):
        # Variable annotations: x: float = ...
        if isinstance(node, ast.AnnAssign):
            if _annotation_is_float(node.annotation):
                key = (rel_path, node.lineno)
                if key not in KNOWN_LEGITIMATE_FLOAT_USES:
                    hits.append(_FloatHit(rel_path, node.lineno, "variable annotation: float"))

        # Function arguments and return type
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Return annotation — use the annotation node's line (the `-> float`
            # line), not the def line, so the allowlist key matches the line
            # where "float" actually appears (required by the staleness check).
            if _annotation_is_float(node.returns):
                ret_lineno = node.returns.lineno if node.returns is not None else node.lineno
                key = (rel_path, ret_lineno)
                if key not in KNOWN_LEGITIMATE_FLOAT_USES:
                    hits.append(_FloatHit(rel_path, ret_lineno, f"function return annotation: -> float (def {node.name})"))

            # Positional + keyword args
            for arg in (*node.args.args, *node.args.kwonlyargs, *node.args.posonlyargs):
                if _annotation_is_float(arg.annotation):
                    key = (rel_path, arg.lineno)
                    if key not in KNOWN_LEGITIMATE_FLOAT_USES:
                        hits.append(_FloatHit(rel_path, arg.lineno, f"argument annotation: {arg.arg}: float"))

            # vararg / kwarg
            for special_arg in (node.args.vararg, node.args.kwarg):
                if special_arg and _annotation_is_float(special_arg.annotation):
                    key = (rel_path, special_arg.lineno)
                    if key not in KNOWN_LEGITIMATE_FLOAT_USES:
                        hits.append(_FloatHit(rel_path, special_arg.lineno, "*args/**kwargs annotation: float"))

    return hits


# ---------------------------------------------------------------------------
# SA Float column detection
# ---------------------------------------------------------------------------
_SA_FLOAT_NAMES = frozenset({"Float", "REAL", "FLOAT"})


def _node_is_sa_float(node: ast.expr) -> bool:
    """Return True if node looks like Float(...), sa.Float(...), etc."""
    if isinstance(node, ast.Call):
        func = node.func
        # Float(...)
        if isinstance(func, ast.Name) and func.id in _SA_FLOAT_NAMES:
            return True
        # sa.Float(...) or sqlalchemy.Float(...)
        if isinstance(func, ast.Attribute) and func.attr in _SA_FLOAT_NAMES:
            return True
    # Bare name (not a call): Column(Float) — the class itself passed as arg
    if isinstance(node, ast.Name) and node.id in _SA_FLOAT_NAMES:
        return True
    return isinstance(node, ast.Attribute) and node.attr in _SA_FLOAT_NAMES


def _collect_sa_float_columns(tree: ast.Module, rel_path: str) -> list[_FloatHit]:
    """Find Column(Float(...)) / mapped_column(Float(...)) calls."""
    hits: list[_FloatHit] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        # Is this a Column(...) or mapped_column(...) call?
        is_column_call = False
        if (isinstance(func, ast.Name) and func.id in {"Column", "mapped_column"}) or (isinstance(func, ast.Attribute) and func.attr in {"Column", "mapped_column"}):
            is_column_call = True

        if not is_column_call:
            continue

        # Check positional args — first arg is usually the column type
        for arg in node.args:
            if _node_is_sa_float(arg):
                key = (rel_path, node.lineno)
                if key not in KNOWN_LEGITIMATE_SA_FLOAT_COLUMNS:
                    hits.append(_FloatHit(rel_path, node.lineno, "sa.Float/REAL column in money model"))

        # Also check keyword args (type=Float(...))
        for kw in node.keywords:
            if kw.arg == "type_" and _node_is_sa_float(kw.value):
                key = (rel_path, node.lineno)
                if key not in KNOWN_LEGITIMATE_SA_FLOAT_COLUMNS:
                    hits.append(_FloatHit(rel_path, node.lineno, "sa.Float/REAL column (type_ kwarg) in money model"))

    return hits


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_no_float_annotations_in_money_paths() -> None:
    """No `float` type annotations in money-relevant source files.

    Scans services/, models/, schemas/, events/, remittance/, billing/ and
    shared money utilities using AST walking.  Annotations for legitimate
    non-money floats (ML scores, BMI, timing, rate-limiting) are captured
    in KNOWN_LEGITIMATE_FLOAT_USES above — add entries there, not here.

    Fails with an actionable list of every offending file:line if any
    unapproved float annotation is found.
    """
    files = _discover_money_files()
    assert files, "No money-path files discovered — check _MONEY_GLOBS"

    all_hits: list[_FloatHit] = []
    for path in files:
        tree = _parse(path)
        if tree is None:
            continue
        rel = _rel(path)
        all_hits.extend(_collect_float_annotations(tree, rel))

    if all_hits:
        lines = [
            f"  {h.rel_path}:{h.lineno}  [{h.reason}]"
            for h in sorted(all_hits, key=lambda h: (h.rel_path, h.lineno))
        ]
        message = (
            "float type annotations found in money-relevant paths.\n\n"
            "Fix: change the type to Decimal (and use shared/utils/money.py helpers).\n"
            "If the float is genuinely NOT a money value (e.g., ML score, BMI,\n"
            "timing), add an entry to KNOWN_LEGITIMATE_FLOAT_USES in this test\n"
            "file with a clear reason.\n\n"
            "Offending locations:\n" + "\n".join(lines)
        )
        pytest.fail(message)


def test_no_float_columns_in_money_models() -> None:
    """No sa.Float / REAL SQLAlchemy column types in money-relevant model files.

    Money columns MUST use sa.Numeric(x, 2) or sa.Numeric(x, 4).
    sa.Float and sa.REAL are IEEE 754 types and will introduce silent
    rounding errors at the cent level.

    Fails with an actionable list of every offending Column(...) call.
    """
    files = _discover_money_files()
    assert files, "No money-path files discovered — check _MONEY_GLOBS"

    all_hits: list[_FloatHit] = []
    for path in files:
        tree = _parse(path)
        if tree is None:
            continue
        rel = _rel(path)
        all_hits.extend(_collect_sa_float_columns(tree, rel))

    if all_hits:
        lines = [
            f"  {h.rel_path}:{h.lineno}  [{h.reason}]"
            for h in sorted(all_hits, key=lambda h: (h.rel_path, h.lineno))
        ]
        message = (
            "sa.Float / REAL column types found in money-relevant model files.\n\n"
            "Fix: replace with sa.Numeric(precision, 2) for dollar amounts or\n"
            "sa.Numeric(precision, 4) for unit prices.  See\n"
            ".claude/rules/financial-precision.md for the full rule.\n"
            "If the column is genuinely NOT money (extremely rare), add an entry\n"
            "to KNOWN_LEGITIMATE_SA_FLOAT_COLUMNS in this test file.\n\n"
            "Offending locations:\n" + "\n".join(lines)
        )
        pytest.fail(message)


def test_allowlist_entries_still_exist() -> None:
    """Every allowlist entry must reference a line that still exists in the file.

    Prevents allowlist rot — when allowlisted code is refactored or moved,
    this test catches stale entries that would silently whittle down
    enforcement coverage.
    """
    stale: list[str] = []
    for (rel_path, lineno), reason in {
        **KNOWN_LEGITIMATE_FLOAT_USES,
        **KNOWN_LEGITIMATE_SA_FLOAT_COLUMNS,
    }.items():
        full_path = _REPO_ROOT / rel_path
        if not full_path.exists():
            stale.append(f"  {rel_path}:{lineno} — file does not exist ({reason})")
            continue
        lines = full_path.read_text(encoding="utf-8").splitlines()
        if lineno > len(lines):
            stale.append(
                f"  {rel_path}:{lineno} — file has only {len(lines)} lines ({reason})"
            )
            continue
        line_text = lines[lineno - 1]
        # Confirm the line still contains "float" (case-insensitive)
        if "float" not in line_text.lower():
            stale.append(
                f"  {rel_path}:{lineno} — line no longer contains 'float': "
                f"{line_text.strip()!r} ({reason})"
            )

    if stale:
        message = (
            "Stale allowlist entries found in "
            "tests/repo/test_no_floats_in_money_paths.py.\n\n"
            "When refactoring moves or removes allowlisted code, update the\n"
            "KNOWN_LEGITIMATE_FLOAT_USES / KNOWN_LEGITIMATE_SA_FLOAT_COLUMNS\n"
            "dicts in that file to match the new line numbers (or remove entries\n"
            "for code that no longer exists).\n\n"
            "Stale entries:\n" + "\n".join(stale)
        )
        pytest.fail(message)
