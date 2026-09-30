import ast
import re
from collections import defaultdict
from pathlib import Path


def _get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def test_no_duplicate_normalized_module_names():
    """Ensure no two scan modules share the same normalized name across categories."""
    root = _get_project_root()
    modules_dir = root / "phonsint" / "modules"
    assert modules_dir.exists(), f"Directory not found: {modules_dir}"

    normalized_map = defaultdict(list)
    for path in modules_dir.rglob("*.py"):
        if path.name.startswith("__"):
            continue

        norm_name = re.sub(r"[^a-z0-9]", "", path.stem.lower())
        rel_path = path.relative_to(modules_dir).as_posix()
        normalized_map[norm_name].append(rel_path)

    duplicates = {k: v for k, v in normalized_map.items() if len(v) > 1}
    assert not duplicates, f"Duplicate or similarly-named modules found: {duplicates}"


def test_all_modules_have_validator_and_valid_ast():
    """Ensure every module in modules/ parses valid AST and defines validate_<module_name>."""
    root = _get_project_root()
    modules_dir = root / "phonsint" / "modules"

    for path in modules_dir.rglob("*.py"):
        if path.name.startswith("__"):
            continue

        rel_path = path.relative_to(modules_dir).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
        except SyntaxError as e:
            raise AssertionError(f"Syntax error in {rel_path}: {e}")

        expected_fn = f"validate_{path.stem.lower()}"
        validators = [
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("validate_")
        ]
        assert validators, f"{rel_path} has no validator function starting with 'validate_'"
        assert expected_fn in validators, (
            f"{rel_path} does not define expected '{expected_fn}'. Found: {validators}"
        )


def test_abandoned_modules_have_valid_ast():
    """Ensure abandoned modules still have valid Python syntax."""
    root = _get_project_root()
    abandoned_dir = root / "abandoned"
    if not abandoned_dir.exists():
        return

    for path in abandoned_dir.rglob("*.py"):
        if path.name.startswith("__"):
            continue
        try:
            ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
        except SyntaxError as e:
            raise AssertionError(f"Syntax error in abandoned module {path}: {e}")
