import time
from typing import Any, Dict
from curl_cffi.requests import AsyncSession

from phonsint.core.impersonate import get_global_proxy, get_global_timeout
from phonsint.core.parser import PhoneInfo
from phonsint.core.result import Result

SIGNIN_URL = "https://accounts.zoho.com/signin"
LOOKUP_URL_TEMPLATE = "https://accounts.zoho.com/signin/v2/lookup/{target}"
SHOW_URL = "https://accounts.zoho.com"


async def validate_zoho(info: PhoneInfo) -> Result:
    """Validate if a phone number is registered on Zoho Accounts."""
    if not info.is_valid or not info.country_code or not info.national_number:
        return Result.available(url=SHOW_URL)

    phone_target = f"{info.country_code}-{info.national_number}"
    proxy = get_global_proxy()
    proxies = {"http": proxy, "https": proxy} if proxy else None
    timeout = get_global_timeout()

    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
        "Accept": "*/*",
        "Origin": "https://accounts.zoho.com",
        "Referer": "https://accounts.zoho.com/",
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        async with AsyncSession(impersonate="chrome120", proxies=proxies, timeout=timeout) as session:  # type: ignore[arg-type]
            # Step 1: Access signin page to obtain iamcsr CSRF cookie
            init_resp = await session.get(SIGNIN_URL, headers=headers)
            if init_resp.status_code == 429:
                return Result.error("Zoho rate limit reached (HTTP 429)", url=SHOW_URL)

            csrf = session.cookies.get("iamcsr")
            if not csrf:
                return Result.error("Failed to retrieve Zoho CSRF token", url=SHOW_URL)

            # Step 2: Query lookup endpoint with phone target
            headers["X-ZCSRF-TOKEN"] = f"iamcsrcoo={csrf}"
            payload = {
                "mode": "primary",
                "cli_time": str(int(time.time() * 1000)),
                "servicename": "AaaServer",
                "serviceurl": "https://accounts.zoho.com/u/h",
            }

            lookup_url = LOOKUP_URL_TEMPLATE.format(target=phone_target)
            resp = await session.post(lookup_url, data=payload, headers=headers)

            if resp.status_code == 429:
                return Result.error("Zoho rate limit reached (HTTP 429)", url=SHOW_URL)

            if resp.status_code != 200:
                return Result.error(f"Zoho returned HTTP {resp.status_code}", url=SHOW_URL)

            data: Dict[str, Any] = resp.json()
            status_code = data.get("status_code")
            message = str(data.get("message", ""))
            err_codes = [err.get("code") for err in data.get("errors", []) if isinstance(err, dict)]

            # Case A: Account exists in primary DC
            if status_code == 201 or message == "User exists" or "U200" in err_codes:
                extra: Dict[str, Any] = {}
                lookup_info = data.get("lookup", {})
                if isinstance(lookup_info, dict):
                    if uid := lookup_info.get("identifier"):
                        extra["user_id"] = str(uid)
                    modes = lookup_info.get("modes", {})
                    if isinstance(modes, dict) and "allowed_modes" in modes:
                        allowed = modes["allowed_modes"]
                        if isinstance(allowed, list):
                            extra["allowed_modes"] = ", ".join(str(m) for m in allowed)
                return Result.taken(extra=extra, url=SHOW_URL)

            # Case B: Account exists in another regional DC (EU, IN, AU, etc.)
            if "User exists in another DC" in message or "U400" in err_codes:
                extra = {}
                data_obj = data.get("data", {})
                redirect_uri = str(data_obj.get("redirect_uri", "")) if isinstance(data_obj, dict) else ""
                if redirect_uri:
                    try:
                        # Extract target host from redirect URI (e.g. accounts.zoho.in)
                        dc_host = redirect_uri.split("//")[1].split("/")[0]
                        extra["datacenter"] = dc_host
                        # Query the target DC to extract the full user ID
                        dc_headers = dict(headers)
                        dc_headers["Origin"] = f"https://{dc_host}"
                        dc_headers["Referer"] = f"https://{dc_host}/"
                        await session.get(f"https://{dc_host}/signin", headers=dc_headers)
                        if dc_csrf := session.cookies.get("iamcsr"):
                            dc_headers["X-ZCSRF-TOKEN"] = f"iamcsrcoo={dc_csrf}"
                            dc_payload = dict(payload)
                            dc_payload["serviceurl"] = f"https://{dc_host}/u/h"
                            dc_resp = await session.post(
                                f"https://{dc_host}/signin/v2/lookup/{phone_target}",
                                data=dc_payload,
                                headers=dc_headers,
                            )
                            if dc_resp.status_code == 200:
                                dc_json = dc_resp.json()
                                if dc_lookup := dc_json.get("lookup"):
                                    if isinstance(dc_lookup, dict) and (uid := dc_lookup.get("identifier")):
                                        extra["user_id"] = str(uid)
                    except Exception:
                        pass
                return Result.taken(extra=extra, url=SHOW_URL)

            # Case C: Account exists but is marked as spam/inactive
            if "User is marked as spam" in message or "U409" in err_codes:
                return Result.taken(extra={"status": "inactive_or_spam"}, url=SHOW_URL)

            # Case D: Account does not exist
            if (status_code == 400 and ("does not exists" in message.lower())) or "U401" in err_codes:
                return Result.available(url=SHOW_URL)

            # Case E: Unallocated / invalid number format
            if status_code == 404 or "Invalid input" in message or "IN106" in err_codes:
                return Result.available(url=SHOW_URL)

            return Result.error(f"Unexpected response from Zoho: {message or status_code}", url=SHOW_URL)

    except Exception as e:
        return Result.error(str(e), url=SHOW_URL)
