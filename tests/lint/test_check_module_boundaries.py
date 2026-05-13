"""Tests for scripts/lint/check_module_boundaries.py (R12 lint rule)."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.lint.check_module_boundaries import main


def make_repo(tmp_path: Path, modules: dict[str, list[str]], shared: dict[str, str]) -> Path:
    """Build a fake repo at tmp_path.

    Args:
        modules: {module_name: [marker, ...]} where each marker is either
            'src' (creates modules/<name>/src/) or a filename (creates
            modules/<name>/<filename> as an empty file). Empty list means
            modules/<name>/ exists with no children.
        shared: {relative_filename: file_contents}. Files are created
            under tmp_path/shared/ with parent dirs auto-created.

    Returns:
        tmp_path (for convenience).
    """
    modules_dir = tmp_path / "modules"
    modules_dir.mkdir(parents=True, exist_ok=True)
    for mod_name, markers in modules.items():
        mod_dir = modules_dir / mod_name
        mod_dir.mkdir(parents=True, exist_ok=True)
        for marker in markers:
            if marker == "src":
                (mod_dir / "src").mkdir(exist_ok=True)
            else:
                (mod_dir / marker).touch()
    shared_dir = tmp_path / "shared"
    shared_dir.mkdir(parents=True, exist_ok=True)
    for rel, contents in shared.items():
        file_path = shared_dir / rel
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(contents)
    return tmp_path


def test_clean_shared_passes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Spec test #1: shared/ that doesn't import any module → exit 0, no output."""
    make_repo(
        tmp_path,
        modules={"foo": ["src"]},
        shared={"db.py": "import json\n\ndata = json.loads('{}')\n"},
    )

    exit_code = main(["--root", str(tmp_path)])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_marker_discovery_includes_src_dirs(tmp_path: Path) -> None:
    """Spec test #11: directories under modules/ with src/ are forbidden."""
    from scripts.lint.check_module_boundaries import discover_forbidden_modules

    make_repo(tmp_path, modules={"foo": ["src"], "bar": ["src"]}, shared={})

    forbidden = discover_forbidden_modules(tmp_path)

    assert forbidden == {"foo", "bar"}


def test_marker_discovery_excludes_non_src_dirs(tmp_path: Path) -> None:
    """Spec test #12: directories under modules/ without src/ are NOT forbidden.

    Catches stray archives, scratch dirs, etc. — only real module dirs (with
    src/ subdirectory) are added to the forbidden set.
    """
    from scripts.lint.check_module_boundaries import discover_forbidden_modules

    make_repo(
        tmp_path,
        modules={
            "foo": ["src"],         # real module — forbidden
            "_archive": [],         # no src/ — NOT forbidden
            "scratch": ["README"],  # only a README — NOT forbidden
        },
        shared={},
    )

    forbidden = discover_forbidden_modules(tmp_path)

    assert forbidden == {"foo"}


def test_hyphenated_module_name_normalized(tmp_path: Path) -> None:
    """Spec test #13: module dirs with hyphens map to underscored package names.

    modules/network-management/ → forbidden name 'network_management'
    (matches Python package conventions; `from network-management ...`
    is a syntax error in Python and never reaches detection).
    """
    from scripts.lint.check_module_boundaries import discover_forbidden_modules

    make_repo(tmp_path, modules={"network-management": ["src"]}, shared={})

    forbidden = discover_forbidden_modules(tmp_path)

    assert forbidden == {"network_management"}
    assert "network-management" not in forbidden


def test_simple_import_from_violation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Spec test #2: `from foo import bar` inside shared/ is flagged."""
    make_repo(
        tmp_path,
        modules={"foo": ["src"]},
        shared={"x.py": "from foo import bar\n"},
    )

    exit_code = main(["--root", str(tmp_path)])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "M001" in captured.out
    assert "shared/ cannot import from module 'foo'" in captured.out
    assert str(tmp_path / "shared" / "x.py") in captured.out
    assert ":1:0:" in captured.out  # line 1, column 0


def test_dotted_import_from_violation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Spec test #3: `from foo.models.claim import Claim` is flagged on top segment."""
    make_repo(
        tmp_path,
        modules={"foo": ["src"]},
        shared={"x.py": "from foo.models.claim import Claim\n"},
    )

    exit_code = main(["--root", str(tmp_path)])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "shared/ cannot import from module 'foo'" in captured.out


def test_bare_import_violation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Spec test #4: `import foo` inside shared/ is flagged."""
    make_repo(
        tmp_path,
        modules={"foo": ["src"]},
        shared={"x.py": "import foo\n"},
    )

    exit_code = main(["--root", str(tmp_path)])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "shared/ cannot import from module 'foo'" in captured.out


def test_aliased_bare_import_violation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Spec test #5: `import foo as f` is flagged."""
    make_repo(
        tmp_path,
        modules={"foo": ["src"]},
        shared={"x.py": "import foo as f\n"},
    )

    exit_code = main(["--root", str(tmp_path)])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "shared/ cannot import from module 'foo'" in captured.out


def test_dotted_bare_import_violation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Spec test #6: `import foo.models` is flagged on top segment."""
    make_repo(
        tmp_path,
        modules={"foo": ["src"]},
        shared={"x.py": "import foo.models\n"},
    )

    exit_code = main(["--root", str(tmp_path)])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "shared/ cannot import from module 'foo'" in captured.out


def test_relative_import_not_flagged(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Spec test #7: `from . import sibling` inside shared/ is NOT flagged.

    Relative imports never reach modules/* package space (they resolve
    inside the importing file's package). Confirmed via ast.ImportFrom.level > 0.
    """
    # The relative import is a syntax-only check; the file just needs to
    # parse. We don't need a real sibling module for AST analysis.
    make_repo(
        tmp_path,
        modules={"foo": ["src"]},
        shared={"pkg/__init__.py": "", "pkg/file.py": "from . import sibling\n"},
    )

    exit_code = main(["--root", str(tmp_path)])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert captured.out == ""


def test_type_checking_block_violation_flagged(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Spec test #8: imports inside `if TYPE_CHECKING:` blocks are flagged.

    Per spec: structural rule, not runtime rule. shared/ source code does
    not reference module names regardless of runtime semantics.
    """
    source = (
        "from __future__ import annotations\n"
        "from typing import TYPE_CHECKING\n"
        "\n"
        "if TYPE_CHECKING:\n"
        "    from foo.models import Claim  # type-only annotation usage\n"
        "\n"
        "def handle(c: 'Claim') -> None: ...\n"
    )
    make_repo(
        tmp_path,
        modules={"foo": ["src"]},
        shared={"x.py": source},
    )

    exit_code = main(["--root", str(tmp_path)])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "shared/ cannot import from module 'foo'" in captured.out


def test_type_checking_elsewhere_does_not_interfere(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Spec test #9: presence of TYPE_CHECKING in a file does not cause the
    visitor to skip later non-TYPE_CHECKING imports.

    Belt-and-suspenders pair with test #8 — confirms the walker doesn't
    bail out early when it sees TYPE_CHECKING.
    """
    source = (
        "from __future__ import annotations\n"
        "from typing import TYPE_CHECKING\n"
        "\n"
        "if TYPE_CHECKING:\n"
        "    from collections.abc import Iterable  # stdlib, not flagged\n"
        "\n"
        "from foo import bar  # runtime import, MUST be flagged\n"
    )
    make_repo(
        tmp_path,
        modules={"foo": ["src"]},
        shared={"x.py": source},
    )

    exit_code = main(["--root", str(tmp_path)])

    assert exit_code == 1
    captured = capsys.readouterr()
    # Exactly one violation, on the runtime `from foo import bar` line.
    assert captured.out.count("M001") == 1
    assert "shared/ cannot import from module 'foo'" in captured.out


def test_shared_tests_subdir_uniformly_enforced(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Spec test #10: violations in shared/tests/ are flagged just like
    violations in shared/db/ or any other subdir.

    Confirms the uniform-scope decision: foundation has no consumers,
    including in tests.
    """
    make_repo(
        tmp_path,
        modules={"foo": ["src"]},
        shared={"tests/test_foo.py": "from foo import bar\n"},
    )

    exit_code = main(["--root", str(tmp_path)])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "shared/ cannot import from module 'foo'" in captured.out
    # Cross-platform path check: Windows reports tests\\test_foo.py,
    # POSIX reports tests/test_foo.py. Match basename + parent separately.
    assert "test_foo.py" in captured.out
    assert "tests" in captured.out


def test_unparseable_file_exits_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Spec test #14: a syntax error in shared/ → exit 2, stderr message,
    NOT exit 1 (don't conflate parse errors with violations)."""
    make_repo(
        tmp_path,
        modules={"foo": ["src"]},
        shared={"broken.py": "def foo(:\n"},  # syntax error
    )

    exit_code = main(["--root", str(tmp_path)])

    assert exit_code == 2
    captured = capsys.readouterr()
    assert "parse error" in captured.err
    assert "broken.py" in captured.err


def test_missing_modules_dir_exits_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Spec test #15: --root pointing at a tree with no modules/ → exit 2."""
    (tmp_path / "shared").mkdir()
    # No modules/ dir created.

    exit_code = main(["--root", str(tmp_path)])

    assert exit_code == 2
    captured = capsys.readouterr()
    assert "modules/ directory not found" in captured.err


def test_missing_shared_dir_exits_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Spec test #16: --root pointing at a tree with modules/ but no shared/ → exit 2."""
    make_repo(tmp_path, modules={"foo": ["src"]}, shared={})
    # make_repo creates shared/. Remove it.
    (tmp_path / "shared").rmdir()

    exit_code = main(["--root", str(tmp_path)])

    assert exit_code == 2
    captured = capsys.readouterr()
    assert "shared/ directory not found" in captured.err


def test_empty_forbidden_set_exits_2_with_distinct_message(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Spec test #17: modules/ exists but contains nothing with src/ → exit 2.

    Distinct stderr message from missing-dir cases — handles legitimate
    early-scaffold case AND misconfigured root.
    """
    # modules/ exists but has only non-module dirs (no src/).
    make_repo(tmp_path, modules={"_archive": [], "scratch": ["README"]}, shared={})

    exit_code = main(["--root", str(tmp_path)])

    assert exit_code == 2
    captured = capsys.readouterr()
    assert "no module markers found" in captured.err
    assert "modules/<name>/src/ structure" in captured.err
    # Confirm the message is DISTINCT from the missing-dir cases.
    assert "directory not found" not in captured.err
