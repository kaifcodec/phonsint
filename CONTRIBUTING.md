# Contributing to phonsint

Thank you for contributing to `phonsint`! This repository is designed to make adding new phone OSINT modules fast, modular, and consistent.

---

## Architecture Overview

Modules are organized by category under `phonsint/modules/<category>/<platform>.py`:
* `auth/`: Identity providers and single sign-on systems (Microsoft, Google, Apple ID).
* `social/`: Social media platforms (Facebook, Instagram, X/Twitter, Snapchat).
* `shopping/`: E-commerce platforms (Amazon, eBay, Flipkart).
* `messaging/`: Instant messaging apps (WhatsApp, Telegram, Signal, Viber).

---

## Module Guidelines

1. **File Name**:
   * Must be lowercase alphanumeric, matching the platform name (e.g., `microsoft.py`, `facebook.py`).
2. **Validator Function**:
   * Exactly one exported validator function per module:
     ```python
     async def validate_<platform>(info: PhoneInfo) -> Result:
         ...
     ```
   * `info` is a `PhoneInfo` object providing:
     * `info.e164`: Standardized E.164 string (e.g. `+14155552671`).
     * `info.national_number`: Raw digits without country code.
     * `info.country_code`: Country calling code integer (e.g. `1`, `44`).
     * `info.region_code`: ISO 2-letter country code (e.g. `US`, `GB`).
3. **Return Values**:
   * Always return a `Result` instance:
     * `Result.taken(url=..., extra={...}, media={...})`
     * `Result.available(url=...)`
     * `Result.error("Description of error", url=...)`
   * **Images** (avatars, profile photos) MUST go into `media={"avatar": "https://..."}`.
   * **Attributes** (display name, masked email, carrier, status) go into `extra={"name": "...", "masked_email": "..."}`.
4. **Never Use `raise`**:
   * All network anomalies, unexpected HTTP status codes, or parsing errors must return `Result.error(...)` so the scanner can gracefully continue to other modules.
5. **No False Positives**:
   * Never infer account availability from a bare HTTP 200 or bare `else`. Verify explicit positive and negative markers.
6. **Silent Operation Guarantee**:
   * Probes must NEVER trigger an SMS verification code, call, or email alert to the target phone number.
   * If a module relies on a step that could trigger an alert, it must be added to `LOUD_MODULES` in `phonsint/core/helpers.py`.

---

## Example Module Blueprint

```python
# phonsint/modules/auth/example.py
from phonsint.core.impersonate import impersonate_request_async
from phonsint.core.parser import PhoneInfo
from phonsint.core.result import Result

CHECK_URL = "https://api.example.com/check-phone"
SHOW_URL = "https://example.com"


async def validate_example(info: PhoneInfo) -> Result:
    try:
        response = await impersonate_request_async(
            CHECK_URL,
            method="POST",
            json={"phone": info.e164},
            headers={"Accept": "application/json"},
        )

        if response.status_code == 200:
            data = response.json()
            # Explicit negative match
            if data.get("exists") is False:
                return Result.available(url=SHOW_URL)
            
            # Explicit positive match
            if data.get("exists") is True:
                extra = {}
                if name := data.get("name"):
                    extra["name"] = name
                return Result.taken(extra=extra, url=SHOW_URL)

        return Result.error(f"Unexpected status code: {response.status_code}", url=SHOW_URL)

    except Exception as exc:
        return Result.error(str(exc), url=SHOW_URL)
```

---

## Local Testing & Verification

Run tests with `pytest`:

```bash
pytest tests/
```

Verify your module live with a known registered number and an unallocated/nonexistent number:

```bash
python3 -m phonsint -p +14155552671 -m example -v --all
```
