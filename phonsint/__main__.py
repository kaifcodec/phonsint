import argparse
import csv
import json
import sys
from pathlib import Path
from colorama import Fore, Style, init

from phonsint import __version__
from phonsint.core.helpers import ScanConfig, load_categories, load_modules
from phonsint.core.orchestrator import run_scan
from phonsint.core.parser import parse_phone_number
from rich.console import Console
from rich.table import Table

init(autoreset=True)
console = Console()

BANNER = rf"""{Fore.CYAN}
    ____  __                      _       __ 
   / __ \/ /_  ____  ____  _____ (_)___  / /_
  / /_/ / __ \/ __ \/ __ \/ ___// / __ \/ __/
 / ____/ / / / /_/ / / / (__  )/ / / / / /_  
/_/   /_/ /_/\____/_/ /_/____//_/_/ /_/\__/  
{Fore.LIGHTBLACK_EX}   phonsint v{__version__} | Silent Phone Reconnaissance & Intelligence Suite
{Style.RESET_ALL}"""


def print_banner() -> None:
    print(BANNER)




def list_modules() -> None:
    print_banner()
    categories = load_categories()
    if not categories:
        print(f"{Fore.YELLOW}[!] No modules found.{Style.RESET_ALL}")
        return

    table = Table(title="[bold cyan]Available Scan Modules[/bold cyan]", border_style="cyan")
    table.add_column("Category", style="magenta", width=18)
    table.add_column("Module", style="green", width=22)
    table.add_column("Path", style="dim white")

    for cat_name, cat_path in sorted(categories.items()):
        mods = load_modules(cat_path)
        for m in mods:
            table.add_row(cat_name.capitalize(), m.__name__.split(".")[-1], str(m.__file__))

    console.print(table)


def export_results(results, file_path: str, fmt: str = "json") -> None:
    out = Path(file_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    if fmt == "csv" or out.suffix.lower() == ".csv":
        with open(out, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["site_name", "category", "phone", "status", "url", "extra", "media", "reason"])
            for r in results:
                writer.writerow([
                    r.site_name,
                    r.category,
                    r.phone,
                    r.status.to_label(),
                    r.url,
                    json.dumps(r.extra) if r.extra else "",
                    json.dumps(r.media) if r.media else "",
                    r.reason or "",
                ])
    else:
        with open(out, "w", encoding="utf-8") as f:
            json.dump([r.to_dict() for r in results], f, indent=2)

    print(f"\n{Fore.GREEN}[+] Results successfully exported to: {out}{Style.RESET_ALL}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="phonsint",
        description="phonsint: High-Throughput Silent Phone Number Reconnaissance & Identity Footprinting",
    )
    parser.add_argument("-p", "--phone", help="Target phone number (e.g. +14155552671)")
    parser.add_argument("-r", "--region", help="Default ISO country code if number lacks '+' prefix (e.g. US, GB, IN, FR)")
    parser.add_argument("-c", "--category", help="Limit scan to specific comma-separated categories (e.g. auth,social)")
    parser.add_argument("-m", "--module", help="Limit scan to specific comma-separated modules (e.g. microsoft,facebook)")
    parser.add_argument("-l", "--list", action="store_true", help="List all available categories and modules")
    parser.add_argument("--all", action="store_true", help="Show all results including not registered and errors")
    parser.add_argument("-v", "--verbose", action="store_true", help="Display URLs and diagnostic reasons")
    parser.add_argument("-t", "--timeout", type=float, default=15.0, help="Per-module request timeout in seconds")
    parser.add_argument("-C", "--concurrency", type=int, default=15, help="Maximum concurrent requests")
    parser.add_argument("--allow-loud", action="store_true", help="Allow modules that may trigger SMS/notifications")
    parser.add_argument("-f", "--format", choices=["json", "csv"], default="json", help="Export format (json/csv)")
    parser.add_argument("-o", "--output", help="Save scan results to file")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    args = parser.parse_args()

    if args.list:
        list_modules()
        return

    if not args.phone:
        print_banner()
        parser.print_help()
        print(f"\n{Fore.RED}[!] Error: Please provide a target phone number using -p / --phone.{Style.RESET_ALL}")
        sys.exit(1)

    print_banner()

    # Step 1: Parse and validate phone number
    phone_info = parse_phone_number(args.phone, args.region)
    print(f"\n{Fore.CYAN} Checking phone: {phone_info.e164}{Style.RESET_ALL}")

    if not phone_info.is_valid:
        print(f"{Fore.YELLOW}[!] Warning: '{args.phone}' is not a standard allocated number according to E.164.{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[*] Proceeding with best-effort scan anyway...{Style.RESET_ALL}\n")

    # Step 2: Build scan configuration
    configs = ScanConfig(
        allow_loud=args.allow_loud,
        show_all=args.all,
        verbose=args.verbose,
        timeout=args.timeout,
        concurrency=args.concurrency,
    )

    # Step 3: Run platform scan
    results = run_scan(
        phone_info,
        configs,
        category_filter=args.category,
        module_filter=args.module,
    )

    # Summary count
    taken_count = sum(1 for r in results if r.is_found())
    print(f"\n{Fore.CYAN}== SUMMARY =={Style.RESET_ALL}")
    print(f"Total Sites Scanned: {len(results)}")
    print(f"Registered / Found:  {Fore.GREEN}{taken_count}{Style.RESET_ALL}")

    # Step 4: Export if requested
    if args.output:
        export_results(results, args.output, args.format)


if __name__ == "__main__":
    main()
