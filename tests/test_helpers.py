import inspect
import types

from phonsint.core import helpers
from phonsint.core.helpers import (
    ScanConfig,
    find_category,
    get_scan_func,
    get_site_name,
    is_loud,
    load_categories,
    load_modules,
)


def test_get_site_name():
    def make_mod(name: str) -> types.ModuleType:
        m = types.ModuleType(name.split(".")[-1])
        m.__name__ = name
        return m

    assert get_site_name(make_mod("facebook")) == "Facebook"
    assert get_site_name(make_mod("phonsint.modules.social.facebook")) == "Facebook"
    assert get_site_name(make_mod("chess_com")) == "Chess Com"


def test_find_category():
    def make_mod(name: str) -> types.ModuleType:
        m = types.ModuleType(name.split(".")[-1])
        m.__name__ = name
        return m

    assert find_category(make_mod("phonsint.modules.social.facebook")) == "Social"
    assert find_category(make_mod("phonsint.modules.auth.microsoft")) == "Auth"
    assert find_category(make_mod("standalone_module")) == "General"


def test_is_loud(monkeypatch):
    monkeypatch.setattr(helpers, "LOUD_MODULES", ["loud_site"])
    assert is_loud("loud_site") is True
    assert is_loud("LOUD_SITE") is True
    assert is_loud("quiet_site") is False


def test_scan_config_defaults():
    cfg = ScanConfig()
    assert cfg.allow_loud is False
    assert cfg.show_all is False
    assert cfg.verbose is False
    assert cfg.timeout is None
    assert cfg.concurrency == 15


def test_load_categories():
    cats = load_categories()
    assert isinstance(cats, dict)
    assert "auth" in cats
    assert "social" in cats
    assert "crm" in cats
    assert "shopping" in cats


def test_load_modules():
    cats = load_categories()
    auth_path = cats["auth"]
    mods = load_modules(auth_path)
    assert len(mods) >= 1
    mod_names = [m.__name__.split(".")[-1] for m in mods]
    assert "microsoft" in mod_names


def test_get_scan_func():
    cats = load_categories()
    social_path = cats["social"]
    mods = load_modules(social_path)
    fb_mod = next(m for m in mods if "facebook" in m.__name__)
    func = get_scan_func(fb_mod)
    assert func is not None
    assert callable(func)
    assert inspect.iscoroutinefunction(func)

    empty_mod = types.ModuleType("dummy")
    assert get_scan_func(empty_mod) is None
