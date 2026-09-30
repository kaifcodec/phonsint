from dataclasses import dataclass
from typing import Optional
import phonenumbers


@dataclass(frozen=True)
class PhoneInfo:
    """Represents a validated and normalized phone number for platform checks."""
    raw_input: str
    is_valid: bool
    e164: str
    international_format: str
    national_format: str
    country_code: int
    national_number: int
    region_code: str


def parse_phone_number(raw: str, default_region: Optional[str] = None) -> PhoneInfo:
    """
    Parse and normalize a raw phone number into standard formats (E.164, national, country code).
    """
    cleaned = raw.strip()
    test_parse = cleaned if (cleaned.startswith("+") or default_region) else ("+" + cleaned)

    try:
        parsed = phonenumbers.parse(cleaned if cleaned.startswith("+") else test_parse, default_region)
    except phonenumbers.NumberParseException:
        try:
            parsed = phonenumbers.parse(cleaned, default_region or "US")
        except phonenumbers.NumberParseException:
            return PhoneInfo(
                raw_input=raw,
                is_valid=False,
                e164=cleaned,
                international_format=cleaned,
                national_format=cleaned,
                country_code=0,
                national_number=0,
                region_code="",
            )

    is_valid = phonenumbers.is_valid_number(parsed)
    e164 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    intl = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
    natl = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.NATIONAL)
    country_code = parsed.country_code
    national_number = parsed.national_number
    region_code = phonenumbers.region_code_for_number(parsed) or ""

    return PhoneInfo(
        raw_input=raw,
        is_valid=is_valid,
        e164=e164,
        international_format=intl,
        national_format=natl,
        country_code=country_code or 0,
        national_number=int(national_number) if national_number is not None else 0,
        region_code=region_code,
    )
