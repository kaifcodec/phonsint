from dataclasses import FrozenInstanceError
import pytest
from phonsint.core.parser import parse_phone_number


def test_parse_valid_us_number():
    info = parse_phone_number("+16502530000")
    assert info.is_valid is True
    assert info.country_code == 1
    assert info.region_code == "US"
    assert info.e164 == "+16502530000"
    assert info.national_number == 6502530000
    assert info.international_format == "+1 650-253-0000"
    assert info.national_format == "(650) 253-0000"


def test_parse_valid_uk_number():
    info = parse_phone_number("+442079460000")
    assert info.is_valid is True
    assert info.country_code == 44
    assert info.region_code == "GB"
    assert info.e164 == "+442079460000"
    assert info.national_format == "020 7946 0000"


def test_parse_with_default_region():
    info = parse_phone_number("020 7946 0000", default_region="GB")
    assert info.is_valid is True
    assert info.e164 == "+442079460000"
    assert info.region_code == "GB"


def test_parse_us_local_with_default_region():
    info = parse_phone_number("6502530000", default_region="US")
    assert info.is_valid is True
    assert info.e164 == "+16502530000"
    assert info.country_code == 1
    assert info.region_code == "US"


def test_parse_invalid_number():
    info = parse_phone_number("+10000000000")
    assert info.is_valid is False

    bad_info = parse_phone_number("invalid-phone")
    assert bad_info.is_valid is False
    assert bad_info.country_code == 0
    assert bad_info.region_code == ""


def test_parse_empty_string():
    info = parse_phone_number("")
    assert info.is_valid is False
    assert info.country_code == 0


def test_phone_info_is_frozen():
    info = parse_phone_number("+16502530000")
    with pytest.raises(FrozenInstanceError):
        info.e164 = "+19999999999"  # type: ignore[misc]
