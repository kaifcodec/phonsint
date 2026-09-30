import json
import re
import uuid
from phonsint.core.impersonate import impersonate_request_async
from phonsint.core.parser import PhoneInfo
from phonsint.core.result import Result

HOME_PAGE_URL = "https://www.instagram.com/"
RESET_PAGE_URL = "https://www.instagram.com/accounts/password/reset/"
GRAPHQL_URL = "https://www.instagram.com/api/graphql"
SHOW_URL = "https://www.instagram.com"

TIMELOCK_DOC_ID = "27729863049988601"
TIMELOCK_FRIENDLY_NAME = "ScriptedTimelockChallengeQuery"
SEARCH_DOC_ID = "36716895674620546"
SEARCH_FRIENDLY_NAME = "CAAIGAccountSearchViewQuery"
ASBD_ID = "359341"
IG_APP_ID = "936619743392459"


def _solve_timelock(base_hex: str, modulus_hex: str, iterations: int) -> str:
    """Solves Meta's LOX client-side time-lock puzzle via repeated modular squaring."""
    base = int(base_hex, 16)
    modulus = int(modulus_hex, 16)
    val = base
    for _ in range(iterations):
        val = (val * val) % modulus
    return hex(val)[2:]


async def validate_instagram(info: PhoneInfo) -> Result:
    phone_target = info.e164
    try:
        # Obtain session cookies and CSRF/LSD tokens from Instagram homepage
        base_headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        }

        resp = await impersonate_request_async(
            HOME_PAGE_URL, headers=base_headers, allow_redirects=True
        )
        if resp.status_code != 200:
            return Result.error(
                f"Failed to load Instagram homepage (HTTP {resp.status_code})",
                url=SHOW_URL,
            )

        csrf = resp.cookies.get("csrftoken", "")
        if not csrf:
            if m := re.search(r'["\']csrf_token["\']\s*:\s*["\']([^"\']+)["\']', resp.text):
                csrf = m.group(1)

        lsd = "AdQMw16ebPpH9oGan3btV8R8hHc"
        if m := re.search(r'["\']lsd["\']\s*:\s*["\']([^"\']+)["\']', resp.text):
            lsd = m.group(1)
        elif m := re.search(r'name="lsd"\s+value="([^"]+)"', resp.text):
            lsd = m.group(1)

        api_headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "X-FB-Friendly-Name": TIMELOCK_FRIENDLY_NAME,
            "X-FB-LSD": lsd,
            "X-ASBD-ID": ASBD_ID,
            "X-CSRFToken": csrf,
            "X-IG-App-ID": IG_APP_ID,
            "Origin": SHOW_URL,
            "Referer": RESET_PAGE_URL,
            "Accept": "*/*",
            "User-Agent": base_headers["User-Agent"],
        }

        # Request the ScriptedTimelockChallenge from Meta CAA
        timelock_data = {
            "av": "0",
            "__d": "www",
            "__user": "0",
            "__a": "1",
            "lsd": lsd,
            "jazoest": "22274",
            "fb_api_caller_class": "RelayModern",
            "fb_api_req_friendly_name": TIMELOCK_FRIENDLY_NAME,
            "variables": "{}",
            "doc_id": TIMELOCK_DOC_ID,
            "server_timestamps": "true",
        }

        timelock_resp = await impersonate_request_async(
            GRAPHQL_URL,
            method="POST",
            data=timelock_data,
            headers=api_headers,
        )

        if timelock_resp.status_code == 429:
            return Result.error("Instagram rate limit reached (HTTP 429)", url=SHOW_URL)
        if timelock_resp.status_code != 200:
            return Result.error(
                f"Failed to fetch Timelock challenge (HTTP {timelock_resp.status_code})",
                url=SHOW_URL,
            )

        try:
            t_json = timelock_resp.json()
        except Exception:
            return Result.error("Invalid JSON from Timelock query", url=SHOW_URL)

        challenge = (
            t_json.get("data", {})
            .get("caa_account_recovery_content", {})
            .get("lox_pow_challenge")
        )
        if not challenge:
            return Result.error("Could not obtain LOX POW challenge", url=SHOW_URL)

        # Solve the LOX Proof of Work timelock puzzle
        base_hex = challenge.get("base", "")
        modulus_hex = challenge.get("modulus", "")
        iterations = challenge.get("iterations", 2000)
        mac = challenge.get("mac", "")
        token = challenge.get("token", "")

        solution = _solve_timelock(base_hex, modulus_hex, iterations)

        # Execute CAAIGAccountSearchViewQuery with the verified solution
        variables = {
            "params": {
                "account_recovery_entry_point": None,
                "event_request_id": str(uuid.uuid4()),
                "is_threads": False,
                "lox_pow_mac": mac,
                "lox_pow_solution": solution,
                "lox_pow_token": token,
                "next_uri": "",
                "search_query": phone_target,
                "waterfall_id": str(uuid.uuid4()),
            }
        }

        search_headers = dict(api_headers)
        search_headers["X-FB-Friendly-Name"] = SEARCH_FRIENDLY_NAME

        search_form = {
            "av": "0",
            "__d": "www",
            "__user": "0",
            "__a": "1",
            "__req": "6",
            "__hs": "20725.HYP:instagram_web_pkg.2.1...0",
            "dpr": "1",
            "__ccg": "GOOD",
            "__rev": "1048738070",
            "__s": "kfl1eh:41y5g4:aff208",
            "__hsi": "7690910195064949123",
            "lsd": lsd,
            "jazoest": "22274",
            "__spin_r": "1048738070",
            "__spin_b": "trunk",
            "__spin_t": "1790679571",
            "__crn": "comet.igweb.PolarisCAAIGAccountRecoverySearchRoute",
            "fb_api_caller_class": "RelayModern",
            "fb_api_req_friendly_name": SEARCH_FRIENDLY_NAME,
            "variables": json.dumps(variables),
            "doc_id": SEARCH_DOC_ID,
            "server_timestamps": "true",
        }

        search_resp = await impersonate_request_async(
            GRAPHQL_URL,
            method="POST",
            data=search_form,
            headers=search_headers,
        )

        if search_resp.status_code == 429:
            return Result.error("Instagram rate limit reached (HTTP 429)", url=SHOW_URL)
        if search_resp.status_code != 200:
            return Result.error(
                f"Instagram search error (HTTP {search_resp.status_code})",
                url=SHOW_URL,
            )

        try:
            s_data = search_resp.json()
        except Exception:
            return Result.error("Invalid JSON from Instagram search", url=SHOW_URL)

        search_result = s_data.get("data", {}).get("caa_ar_ig_account_search")
        if search_result is None:
            if "errors" in s_data and s_data["errors"]:
                err = s_data["errors"][0].get("message", "Unknown error")
                return Result.error(f"Instagram error: {err}", url=SHOW_URL)
            return Result.error("Unexpected response shape from Instagram", url=SHOW_URL)

        contact_points = search_result.get("contact_points", [])
        profiles = search_result.get("profiles", [])

        # Account is registered when contact recovery points exist
        if len(contact_points) > 0:
            extra = {}
            media = {}

            cp = contact_points[0]
            if cp_title := cp.get("title"):
                extra["recovery_method"] = cp_title

            if profiles and len(profiles) > 0:
                p = profiles[0]
                name = p.get("name", "")
                if name and name.strip() != phone_target.strip():
                    extra["name"] = name
                if pic := p.get("profile_pic_url"):
                    if "115870214_694925034696967" not in pic:
                        media["avatar"] = pic

            return Result.taken(extra=extra, media=media, url=SHOW_URL)

        # Explicit not found: contact_points is empty
        return Result.available(url=SHOW_URL)

    except Exception as e:
        return Result.error(str(e), url=SHOW_URL)
