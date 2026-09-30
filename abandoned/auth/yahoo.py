import re
from typing import Any, Dict
from curl_cffi.requests import AsyncSession

from phonsint.core.impersonate import get_global_proxy, get_global_timeout
from phonsint.core.parser import PhoneInfo
from phonsint.core.result import Result

LOGIN_URL = "https://login.yahoo.com/"
VALIDATE_URL = "https://login.yahoo.com/validate"
SHOW_URL = "https://login.yahoo.com"

ACRUMB_REGEX = re.compile(r'\\"acrumb\\":\\"([^\\"]+)\\"')
CRUMB_REGEX = re.compile(r'\\"crumb\\":\\"([^\\"]+)\\"')
SESSION_REGEX = re.compile(r'\\"sessionIndex\\":\\"([^\\"]+)\\"')


async def validate_yahoo(info: PhoneInfo) -> Result:
    """Validate if a phone number is registered on Yahoo / AOL."""
    phone_target = info.e164
    proxy = get_global_proxy()
    proxies = {"http": proxy, "https": proxy} if proxy else None
    timeout = get_global_timeout()

    headers = {
        "Origin": "https://login.yahoo.com",
        "Referer": "https://login.yahoo.com/",
        "X-Requested-With": "XMLHttpRequest",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }

    try:
        async with AsyncSession(impersonate="chrome120", proxies=proxies, timeout=timeout) as session:  # type: ignore[arg-type]
            # Step 1: Request login landing page to capture session crumb tokens
            init_resp = await session.get(LOGIN_URL)
            if init_resp.status_code == 429:
                return Result.error("Yahoo rate limit reached (HTTP 429)", url=SHOW_URL)
            if init_resp.status_code != 200:
                return Result.error(
                    f"Failed to fetch Yahoo login page (HTTP {init_resp.status_code})",
                    url=SHOW_URL,
                )

            m_ac = ACRUMB_REGEX.search(init_resp.text)
            m_cr = CRUMB_REGEX.search(init_resp.text)
            m_se = SESSION_REGEX.search(init_resp.text)

            if not (m_ac and m_cr and m_se):
                return Result.error("Could not parse Yahoo login session tokens", url=SHOW_URL)

            acrumb = m_ac.group(1)
            crumb = m_cr.group(1)
            session_index = m_se.group(1)

            # Step 2: Validate phone number against pre-auth challenge check
            data = {
                "acrumb": acrumb,
                "crumb": crumb,
                "sessionIndex": session_index,
                "username": phone_target,
                "persistent": "y",
            }

            val_resp = await session.post(VALIDATE_URL, data=data, headers=headers)
            if val_resp.status_code == 429:
                return Result.error("Yahoo rate limit reached (HTTP 429)", url=SHOW_URL)
            if val_resp.status_code != 200:
                return Result.error(
                    f"Yahoo validate error (HTTP {val_resp.status_code})",
                    url=SHOW_URL,
                )

            res: Dict[str, Any] = val_resp.json()

            # Case A: Success redirect to challenge (account exists)
            if "redirect" in res:
                redir = str(res["redirect"])
                if "challenge/fail" in redir:
                    return Result.available(url=SHOW_URL)

                extra: Dict[str, Any] = {}
                base_challenge = redir.split("?")[0].replace("/account/challenge/", "")
                if base_challenge:
                    extra["challenge_type"] = base_challenge
                return Result.taken(extra=extra, url=SHOW_URL)

            # Case B: Error returned
            if "error" in res:
                err_dict = res["error"]
                err_msg = str(err_dict.get("message", "")) if isinstance(err_dict, dict) else str(err_dict)

                # ERROR_202, ERROR_218, ERROR_224, ERROR_260, etc. or INVALID_IDENTIFIER mean unregistered/unallocated
                if err_msg.startswith("ERROR_") or err_msg in ("INVALID_IDENTIFIER", "INVALID_USERNAME"):
                    return Result.available(url=SHOW_URL)

                return Result.error(f"Yahoo error: {err_msg}", url=SHOW_URL)

            return Result.error(f"Unexpected Yahoo response shape: {res}", url=SHOW_URL)

    except Exception as e:
        return Result.error(str(e), url=SHOW_URL)
