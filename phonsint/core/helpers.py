import importlib.util
import inspect
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Dict, List, Optional, cast

# List of modules that could potentially alert the target via SMS or phone call
LOUD_MODULES: List[str] = []


@dataclass(frozen=True)
class ScanConfig:
    allow_loud: bool = False
    show_all: bool = False
    verbose: bool = False
    timeout: Optional[float] = None
    concurrency: int = 15


def is_loud(site_name: str) -> bool:
    return site_name.lower() in LOUD_MODULES


def get_site_name(module: ModuleType) -> str:
    name = module.__name__.split(".")[-1].replace("_", " ").title()
    return name


def find_category(module: ModuleType) -> str:
    parts = module.__name__.split(".")
    if len(parts) >= 3 and parts[-3] == "modules":
        return parts[-2].capitalize()
    return "General"


def load_categories() -> Dict[str, Path]:
    root = Path(__file__).resolve().parent.parent / "modules"
    categories: Dict[str, Path] = {}
    if not root.exists():
        return categories

    for subfolder in root.iterdir():
        if subfolder.is_dir() and not subfolder.name.startswith("__"):
            categories[subfolder.name] = subfolder.resolve()

    return categories


def load_modules(category_path: Path) -> List[ModuleType]:
    modules = []
    for file in category_path.glob("*.py"):
        if file.name.startswith("__"):
            continue
        spec = importlib.util.spec_from_file_location(file.stem, str(file))
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
            modules.append(module)
        except Exception:
            continue
    return modules


def get_scan_func(module: ModuleType) -> Optional[Callable[..., Any]]:
    for attr_name in dir(module):
        if not attr_name.startswith("validate_"):
            continue
        f = getattr(module, attr_name)
        if inspect.isfunction(f) or inspect.iscoroutinefunction(f):
            return cast(Callable[..., Any], f)
    return None
