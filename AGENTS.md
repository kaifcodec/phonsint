# AI Contributor Guide

This file orients an AI assistant (or any new contributor) working in this repository.

## What this project is

A silent, high-throughput OSINT suite for **phone numbers**. It checks whether a phone
number is registered across popular platforms (social networks, identity providers,
cloud services, e-commerce) and extracts rich profile metadata (display names, masked
emails, profile photos, account status) **without ever dispatching SMS codes or alerts**
to the target phone number.

## Repository layout

- `phonsint/modules/<category>/<site>.py` — platform scan modules.
  Export `async def validate_<site>(info: PhoneInfo) -> Result`.
- `phonsint/core/` — core engine, async orchestrator, phone parser, `Result` container,
  TLS impersonation transport. Changes here affect every module; review carefully.
- `abandoned/<category>/<site>.py` — retired modules (dead sites, permanently broken
  detection). See "Retiring a module" below.
- `tests/` — pytest suite covering core result formatting, phone parsing, module integrity,
  and CLI export logic. **Do not add mocked unit tests for individual scan modules** —
  modules are verified by live-testing against known registered and unallocated numbers.

## Adding a new module

1. **File name** = platform name, lowercase, no spaces/special characters (`amazon.py`, `microsoft.py`).
2. **One validator** per module: `async def validate_<site>(info: PhoneInfo) -> Result`.
3. **No false positives.** Verify unique markers for **both** found and not-found states.
   Confirm *not found* with explicit markers, never a bare 404 or bare `else`.
4. **Silent operation guarantee.** Never trigger SMS dispatch or two-factor alert requests.
   If a step could be loud, register the platform in `LOUD_MODULES` in `phonsint/core/helpers.py`.
5. **Never use `raise`.** Return `Result.error(...)` so the scan continues across remaining modules.
6. **Pick the transport by anti-bot defense.** Use `impersonate_request_async` (`curl_cffi`)
   for Cloudflare/Akamai/Shape-protected endpoints; use `httpx` for standard APIs.

## Retiring a module

Never delete a scan module. When a site shuts down or changes its flow to be permanently
untestable or noisy, **move** the module from `phonsint/modules/<category>/` to
`abandoned/<category>/`.

## CI & Quality Gates

Local gates must pass cleanly:

```bash
ruff check .
mypy phonsint tests
pytest tests
```

## Privacy & Safety

- Never commit real phone numbers, credentials, or target scan outputs.
- Test documentation and examples must use dummy documentation numbers (e.g. `+14155552671`).
