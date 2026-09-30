import json
import re
from typing import Optional
from phonsint.core.impersonate import impersonate_request_async
from phonsint.core.parser import PhoneInfo
from phonsint.core.result import Result

LOGIN_URL = (
    "https://login.live.com/oauth20_authorize.srf"
    "?client_id=3fa91358-6f74-4525-b5df-da149652be36"
    "&scope=openid+profile+User.Read+email+offline_access"
    "&redirect_uri=https%3a%2f%2fwww.linkedin.com%2fmicrosoft-login%2fhandler"
    "&response_type=code&response_mode=form_post&msproxy=1&issuer=mso&tenant=consumers&ui_locales=en-GB"
)
SHOW_URL = "https://account.microsoft.com"
PPFT_REGEX = re.compile(r'value="([^"]+)"')


def _extract_server_data(html: str) -> Optional[dict]:
    marker = "var ServerData ="
    idx = html.find(marker)
    if idx == -1:
        return None
    start = html.find("{", idx)
    if start == -1:
        return None

    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(html)):
        ch = html[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    data = json.loads(html[start : i + 1])
                    return data if isinstance(data, dict) else None
                except Exception:
                    return None
    return None


async def validate_microsoft(info: PhoneInfo) -> Result:
    phone_target = info.e164
    try:
        # Request Microsoft OAuth page to capture session & flowToken
        login_resp = await impersonate_request_async(LOGIN_URL)
        if login_resp.status_code != 200:
            return Result.error(
                f"Failed to fetch login page (HTTP {login_resp.status_code})",
                url=SHOW_URL,
            )

        server_data = _extract_server_data(login_resp.text)
        if not server_data:
            return Result.error("Could not parse ServerData session payload", url=SHOW_URL)

        cred_url = server_data.get("urlGetCredentialType") or "https://login.live.com/GetCredentialType.srf"
        uaid = server_data.get("sUnauthSessionID", "")
        sft_tag = server_data.get("sFTTag", "")

        ppft_match = PPFT_REGEX.search(sft_tag)
        if not ppft_match:
            ppft_match = PPFT_REGEX.search(login_resp.text)
        if not ppft_match:
            return Result.error("Could not extract Microsoft flowToken", url=SHOW_URL)

        flow_token = ppft_match.group(1)

        # Query credential validation endpoint with the exact react login payload
        payload = {
            "checkPhones": True,
            "country": "",
            "federationFlags": 3,
            "flowToken": flow_token,
            "isReactLoginRequest": True,
            "isRemoteNGCSupported": True,
            "uaid": uaid,
            "username": phone_target,
        }

        cred_resp = await impersonate_request_async(
            cred_url,
            method="POST",
            json=payload,
            headers={
                "Content-Type": "application/json; charset=UTF-8",
                "Referer": LOGIN_URL,
                "Origin": "https://login.live.com",
            },
        )

        if cred_resp.status_code == 429:
            return Result.error("Microsoft rate limit reached (HTTP 429)", url=SHOW_URL)

        if cred_resp.status_code != 200:
            return Result.error(
                f"Credential API error (HTTP {cred_resp.status_code})",
                url=SHOW_URL,
            )

        data = cred_resp.json()
        if_exists = data.get("IfExistsResult")

        # 0 = Account exists
        if if_exists == 0:
            extra = {}
            if display := data.get("Display"):
                extra["display_name"] = display
            return Result.taken(extra=extra, url=SHOW_URL)

        # 1 = Account does not exist
        elif if_exists == 1:
            return Result.available(url=SHOW_URL)

        return Result.error(f"Unexpected IfExistsResult: {if_exists}", url=SHOW_URL)

    except Exception as e:
        return Result.error(str(e), url=SHOW_URL)
