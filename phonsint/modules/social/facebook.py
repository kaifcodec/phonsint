import json
import re
import uuid
from urllib.parse import parse_qs, urlparse
from phonsint.core.impersonate import impersonate_request_async
from phonsint.core.parser import PhoneInfo
from phonsint.core.result import Result

LOGIN_PAGE_URL = "https://www.facebook.com/login/identify/"
GRAPHQL_URL = "https://www.facebook.com/api/graphql/"
SHOW_URL = "https://www.facebook.com"

SEARCH_DOC_ID = "28496659306608697"
SEARCH_FRIENDLY_NAME = "CAAFBAccountSearchViewQuery"
SELECT_DOC_ID = "9730637087034984"
SELECT_FRIENDLY_NAME = "useCAAAccountSearchSelectMutation"
ASBD_ID = "359341"

EQMC_REGEX = re.compile(r'<script\s+id="__eqmc"[^>]*>(.*?)</script>', re.DOTALL)
LSD_REGEX = re.compile(r'name="lsd"\s+value="([^"]+)"')
JAZOEST_REGEX = re.compile(r'name="jazoest"\s+value="([^"]+)"')
MASKED_EMAIL_REGEX = re.compile(r'[a-zA-Z0-9_\.\+-]*\*[a-zA-Z0-9_\*\.\+-]*@[a-zA-Z0-9_\*\.\+-]+')


async def validate_facebook(info: PhoneInfo) -> Result:
    phone_target = info.e164
    try:
        # Step 1: Access identify page to extract session tokens
        resp = await impersonate_request_async(
            LOGIN_PAGE_URL,
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            },
            allow_redirects=True,
        )
        if resp.status_code != 200:
            return Result.error(
                f"Failed to load Facebook identify page (HTTP {resp.status_code})",
                url=SHOW_URL,
            )

        lsd = ""
        jazoest = ""

        # Strategy A: Extract from embedded __eqmc JSON
        eqmc_match = EQMC_REGEX.search(resp.text)
        if eqmc_match:
            try:
                eqmc_data = json.loads(eqmc_match.group(1))
                lsd = eqmc_data.get("l", "")
                if u_url := eqmc_data.get("u"):
                    parsed_u = urlparse(u_url)
                    qs = parse_qs(parsed_u.query)
                    if "jazoest" in qs:
                        jazoest = qs["jazoest"][0]
            except Exception:
                pass

        # Strategy B: Fallback regexes
        if not lsd:
            if lsd_m := LSD_REGEX.search(resp.text):
                lsd = lsd_m.group(1)
        if not jazoest:
            if jaz_m := JAZOEST_REGEX.search(resp.text):
                jazoest = jaz_m.group(1)

        if not lsd:
            return Result.error("Could not extract Facebook session tokens", url=SHOW_URL)

        # Step 2: Prepare query payload matching CAAFBAccountSearchViewQuery
        waterfall_id = str(uuid.uuid4())
        variables = {
            "params": {
                "cipher_text": None,
                "context": "recover",
                "event_request_id": str(uuid.uuid4()),
                "friend_name": "",
                "search_query": phone_target,
                "waterfall_id": waterfall_id,
            }
        }

        form_data = {
            "fb_api_caller_class": "RelayModern",
            "fb_api_req_friendly_name": SEARCH_FRIENDLY_NAME,
            "variables": json.dumps(variables),
            "doc_id": SEARCH_DOC_ID,
            "server_timestamps": "true",
            "lsd": lsd,
            "jazoest": jazoest or "2899",
            "__user": "0",
            "__a": "1",
        }

        gql_resp = await impersonate_request_async(
            GRAPHQL_URL,
            method="POST",
            data=form_data,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "X-FB-Friendly-Name": SEARCH_FRIENDLY_NAME,
                "X-FB-LSD": lsd,
                "X-ASBD-ID": ASBD_ID,
                "Origin": "https://www.facebook.com",
                "Referer": LOGIN_PAGE_URL,
                "Accept": "*/*",
            },
        )

        if gql_resp.status_code == 429:
            return Result.error("Facebook rate limit reached (HTTP 429)", url=SHOW_URL)

        if gql_resp.status_code != 200:
            return Result.error(
                f"Facebook GraphQL error (HTTP {gql_resp.status_code})",
                url=SHOW_URL,
            )

        try:
            data = gql_resp.json()
        except Exception:
            return Result.error("Invalid JSON from Facebook GraphQL", url=SHOW_URL)

        if "errors" in data and data["errors"]:
            err_msg = data["errors"][0].get("message", "Unknown GraphQL error")
            return Result.error(f"Facebook error: {err_msg}", url=SHOW_URL)

        search_result = data.get("data", {}).get("caa_ar_fb_account_search")
        if search_result is None:
            return Result.error("Unexpected response shape from Facebook GraphQL", url=SHOW_URL)

        num_results = search_result.get("num_results_shown", 0)
        accounts = search_result.get("accounts", [])

        # Account found
        if num_results > 0 and len(accounts) > 0:
            extra = {}
            media = {}
            first_acc = accounts[0]
            if name := first_acc.get("name"):
                # If name is not just the phone number, save as display name
                if name.strip() != phone_target.strip():
                    extra["name"] = name
            if pic := first_acc.get("profile_pic_url"):
                media["avatar"] = pic

            if len(accounts) > 1:
                account_names = [a.get("name", "").strip() for a in accounts if a.get("name")]
                extra["matched_accounts"] = len(accounts)
                if account_names:
                    extra["profiles"] = ", ".join(account_names)

            # Metadata enrichment: Extract masked email(s) via recovery initiate
            cipher = search_result.get("cipher")
            try:
                emails_found: list[str] = []
                for idx in range(min(len(accounts), 3)):
                    target_uri = None
                    if idx == 0 and (redirect_uri := search_result.get("redirect_uri")):
                        target_uri = redirect_uri
                    elif cipher:
                        sel_vars = {
                            "input": {
                                "actor_id": "0",
                                "client_mutation_id": str(idx + 1),
                                "access_flow_version": "pre_mt_behavior",
                                "cipher": cipher,
                                "idx": idx,
                                "waterfall_id": waterfall_id,
                            }
                        }
                        sel_resp = await impersonate_request_async(
                            GRAPHQL_URL,
                            method="POST",
                            data={
                                "fb_api_caller_class": "RelayModern",
                                "fb_api_req_friendly_name": SELECT_FRIENDLY_NAME,
                                "variables": json.dumps(sel_vars),
                                "doc_id": SELECT_DOC_ID,
                                "server_timestamps": "true",
                                "lsd": lsd,
                                "jazoest": jazoest or "2899",
                                "__user": "0",
                                "__a": "1",
                            },
                            headers={
                                "Content-Type": "application/x-www-form-urlencoded",
                                "X-FB-Friendly-Name": SELECT_FRIENDLY_NAME,
                                "X-FB-LSD": lsd,
                                "X-ASBD-ID": ASBD_ID,
                                "Origin": "https://www.facebook.com",
                                "Referer": LOGIN_PAGE_URL,
                                "Accept": "*/*",
                            },
                        )
                        if sel_resp.status_code == 200:
                            sel_data = sel_resp.json()
                            target_uri = (
                                sel_data.get("data", {})
                                .get("caa_ar_fb_search_select_account", {})
                                .get("select_uri")
                            )

                    if target_uri:
                        full_init_url = (
                            f"https://www.facebook.com{target_uri}"
                            if target_uri.startswith("/")
                            else target_uri
                        )
                        init_resp = await impersonate_request_async(
                            full_init_url,
                            headers={
                                "Referer": LOGIN_PAGE_URL,
                                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                                "Accept-Language": "en-US,en;q=0.9",
                            },
                            allow_redirects=True,
                        )
                        if init_resp.status_code == 200:
                            cleaned_html = (
                                init_resp.text.replace("\\n", " ").replace("\n", " ")
                            )
                            found = MASKED_EMAIL_REGEX.findall(cleaned_html)
                            for em in found:
                                if em not in emails_found:
                                    emails_found.append(em)

                if emails_found:
                    extra["email"] = ", ".join(emails_found)
            except Exception:
                pass

            return Result.taken(extra=extra, media=media, url=SHOW_URL)

        # Explicit not found
        if num_results == 0 or not accounts:
            return Result.available(url=SHOW_URL)

        return Result.available(url=SHOW_URL)

    except Exception as e:
        return Result.error(str(e), url=SHOW_URL)
