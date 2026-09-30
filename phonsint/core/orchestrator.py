import asyncio
import inspect
from types import ModuleType
from typing import Callable, List, Optional, Set
from colorama import Fore, Style
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn

from phonsint.core.helpers import (
    ScanConfig,
    find_category,
    get_scan_func,
    get_site_name,
    is_loud,
    load_categories,
    load_modules,
)
from phonsint.core.parser import PhoneInfo
from phonsint.core.result import Result


async def _async_worker(
    module: ModuleType,
    phone_info: PhoneInfo,
    sem: asyncio.Semaphore,
    configs: ScanConfig,
    cat_override: Optional[str] = None,
    on_start: Optional[Callable[[str], None]] = None,
) -> Result:
    async with sem:
        site_name = get_site_name(module)
        if on_start:
            on_start(site_name)

        func = get_scan_func(module)
        category = cat_override or find_category(module)

        params = {
            "site_name": site_name,
            "phone": phone_info.e164,
            "category": category,
        }

        if not func:
            return Result.error(f"{site_name} has no validate_ function", **params)

        if not configs.allow_loud and is_loud(site_name):
            return Result.skipped(reason="Loud module skipped (use --allow-loud)", **params)

        try:
            timeout_val = (configs.timeout or 15.0) + 5.0
            # Check if function accepts phone_info object or string
            sig = inspect.signature(func)
            arg = phone_info if len(sig.parameters) == 1 and next(iter(sig.parameters.values())).name in ("phone_info", "info") else phone_info.e164

            if inspect.iscoroutinefunction(func):
                raw_res = await asyncio.wait_for(func(arg), timeout=timeout_val)
            else:
                raw_res = await asyncio.wait_for(asyncio.to_thread(func, arg), timeout=timeout_val)

            if isinstance(raw_res, Result):
                result = raw_res
            else:
                result = Result.error("Module returned invalid result type")
        except asyncio.TimeoutError:
            result = Result.error(f"Timed out after {timeout_val}s")
        except Exception as e:
            result = Result.error(str(e))

        return result.update(**params)


async def run_scan_async(
    phone_info: PhoneInfo,
    configs: ScanConfig,
    category_filter: Optional[str] = None,
    module_filter: Optional[str] = None,
) -> List[Result]:
    all_categories = load_categories()
    if not all_categories:
        return []

    # Apply category filter if requested
    if category_filter:
        cat_targets = [c.strip().lower() for c in category_filter.split(",") if c.strip()]
        categories = {k: v for k, v in all_categories.items() if k.lower() in cat_targets}
    else:
        categories = all_categories

    # Collect modules to run
    category_modules: List[tuple[str, List[ModuleType]]] = []
    total_modules = 0

    mod_targets = (
        [m.strip().lower() for m in module_filter.split(",") if m.strip()]
        if module_filter
        else None
    )

    for cat_name, cat_path in categories.items():
        mods = load_modules(cat_path)
        if mod_targets:
            mods = [m for m in mods if m.__name__.split(".")[-1].lower() in mod_targets]
        if mods:
            display_name = cat_name.capitalize()
            category_modules.append((display_name, mods))
            total_modules += len(mods)

    if total_modules == 0:
        print(f"{Fore.YELLOW}[!] No matching scan modules found.{Style.RESET_ALL}")
        return []

    sem = asyncio.Semaphore(configs.concurrency)
    all_results: List[Result] = []
    printed_cats: Set[str] = set()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        transient=True,
    ) as progress:
        task_id = progress.add_task(f"[cyan]Scanning {phone_info.e164}...", total=total_modules)

        def on_start_cb(site: str):
            progress.update(task_id, description=f"[cyan]Scanning {phone_info.e164}... ({site})")

        spawned_category_tasks = []
        for display_name, modules in category_modules:
            tasks = []
            for module in modules:
                t = asyncio.create_task(
                    _async_worker(
                        module,
                        phone_info,
                        sem,
                        configs,
                        cat_override=display_name,
                        on_start=on_start_cb,
                    )
                )
                t.add_done_callback(lambda _: progress.advance(task_id))
                tasks.append(t)
            spawned_category_tasks.append((display_name, tasks))

        for display_name, tasks in spawned_category_tasks:
            if not tasks:
                continue

            if configs.show_all:
                if display_name not in printed_cats:
                    print(f"\n{Fore.MAGENTA}== {display_name.upper()} SITES =={Style.RESET_ALL}")
                    printed_cats.add(display_name)

            for coro in asyncio.as_completed(tasks):
                result = await coro
                if configs.show_all or result.is_visible(configs):
                    cat = result.category or display_name
                    if cat not in printed_cats:
                        print(f"\n{Fore.MAGENTA}== {cat.upper()} SITES =={Style.RESET_ALL}")
                        printed_cats.add(cat)

                result.show(configs)
                all_results.append(result)

    return all_results


def run_scan(
    phone_info: PhoneInfo,
    configs: ScanConfig,
    category_filter: Optional[str] = None,
    module_filter: Optional[str] = None,
) -> List[Result]:
    return asyncio.run(run_scan_async(phone_info, configs, category_filter, module_filter))
