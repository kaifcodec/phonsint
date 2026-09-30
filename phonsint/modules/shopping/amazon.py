import html
import re
from urllib.parse import urljoin
from phonsint.core.impersonate import impersonate_request_async
from phonsint.core.parser import PhoneInfo
from phonsint.core.result import Result

LOGIN_PAGE_URL = (
    "https://www.amazon.com/ap/signin"
    "?openid.return_to=https%3A%2F%2Fwww.amazon.com%2F%3Fref_%3Dnav_ya_signin"
    "&openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select"
    "&openid.assoc_handle=usflex"
    "&openid.mode=checkid_setup"
    "&openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select"
    "&openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0"
)
SHOW_URL = "https://www.amazon.com"

FORM_ACTION_REGEX = re.compile(r'<form[^>]*action="([^"]+)"', re.IGNORECASE)
INPUT_REGEX = re.compile(r'<input\s+[^>]*name="([^"]+)"[^>]*value="([^"]*)"', re.IGNORECASE)
EMAIL_INPUT_REGEX = re.compile(r'<input[^>]*id="ap_email_login"[^>]*name="([^"]+)"', re.IGNORECASE)

NO_ACCOUNT_TOKEN = "Looks like you're new to Amazon"


async def validate_amazon(info: PhoneInfo) -> Result:
    phone_target = info.e164
    try:
        # Step 1: Fetch signin page
        resp = await impersonate_request_async(
            LOGIN_PAGE_URL,
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            },
            allow_redirects=True,
        )
        if resp.status_code != 200:
            return Result.error(f"Failed to load signin page (HTTP {resp.status_code})", url=SHOW_URL)

        body = resp.text
        if "validateCaptcha" in body or "Type the characters you see in this image" in body:
            return Result.error("Amazon presented a bot CAPTCHA", url=SHOW_URL)

        # Step 2: Extract form fields and unescape HTML action URL
        action_match = FORM_ACTION_REGEX.search(body)
        raw_action = action_match.group(1) if action_match else resp.url or LOGIN_PAGE_URL
        action_url = html.unescape(urljoin(resp.url or LOGIN_PAGE_URL, raw_action))

        form_data = {}
        for m in INPUT_REGEX.finditer(body):
            name, val = m.group(1), m.group(2)
            form_data[name] = val

        # Determine target input field
        login_field = "email"
        if "id=\"ap_email_login\"" in body:
            if email_match := EMAIL_INPUT_REGEX.search(body):
                login_field = email_match.group(1)

        form_data[login_field] = phone_target

        # Step 3: Post form
        post_resp = await impersonate_request_async(
            action_url,
            method="POST",
            data=form_data,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": LOGIN_PAGE_URL,
                "Origin": "https://www.amazon.com",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
            allow_redirects=True,
        )

        res_text = post_resp.text

        # Step 4: Analyze response
        if NO_ACCOUNT_TOKEN in res_text or "cannot find an account" in res_text.lower() or "We cannot find an account" in res_text:
            return Result.available(url=SHOW_URL)

        if 'name="password"' in res_text or "Enter your password" in res_text or "auth-password-container" in res_text:
            return Result.taken(url=SHOW_URL)

        if "cvf" in (post_resp.url or "") or "verification" in (post_resp.url or "").lower():
            return Result.taken(url=SHOW_URL)

        if "validateCaptcha" in res_text:
            return Result.error("Amazon CAPTCHA challenge encountered", url=SHOW_URL)

        return Result.error(f"Unexpected response state (HTTP {post_resp.status_code})", url=SHOW_URL)

    except Exception as e:
        return Result.error(str(e), url=SHOW_URL)
