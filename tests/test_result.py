from phonsint.core.result import Result, Status
from phonsint.core.helpers import ScanConfig


def test_result_creation_and_status():
    res = Result.taken(url="https://example.com", extra={"name": "Alice"})
    assert res.status == Status.TAKEN
    assert res.status.to_label() == "Registered"
    assert res.url == "https://example.com"
    assert res.extra["name"] == "Alice"

    avail = Result.available(url="https://example.com")
    assert avail.status == Status.AVAILABLE
    assert avail.status.to_label() == "Not Registered"

    err = Result.error("Network timeout")
    assert err.status == Status.ERROR
    assert err.reason == "Network timeout"
    assert err.status.to_label() == "Error"

    skip = Result.skipped("Loud module")
    assert skip.status == Status.SKIPPED
    assert skip.reason == "Loud module"


def test_result_is_found():
    assert Result.taken().is_found() is True
    assert Result.available().is_found() is False
    assert Result.error("fail").is_found() is False
    assert Result.skipped("loud").is_found() is False


def test_result_visibility():
    default_cfg = ScanConfig(show_all=False)
    all_cfg = ScanConfig(show_all=True)

    taken = Result.taken()
    assert taken.is_visible(default_cfg) is True
    assert taken.is_visible(all_cfg) is True

    avail = Result.available()
    assert avail.is_visible(default_cfg) is False
    assert avail.is_visible(all_cfg) is True

    err = Result.error("err")
    assert err.is_visible(default_cfg) is False
    assert err.is_visible(all_cfg) is True

    skip = Result.skipped("skip")
    assert skip.is_visible(default_cfg) is True
    assert skip.is_visible(all_cfg) is True


def test_result_extra_and_media_cleaning():
    res = Result.taken()
    res.update(
        extra={" Full Name: ": "Bob Smith", "Empty": "", "NoneVal": None},
        media={" Avatar ": "https://example.com/avatar.jpg", "EmptyMedia": ""},
    )
    assert "full_name" in res.extra
    assert res.extra["full_name"] == "Bob Smith"
    assert "empty" not in res.extra
    assert "noneval" not in res.extra

    assert "avatar" in res.media
    assert res.media["avatar"] == "https://example.com/avatar.jpg"
    assert "emptymedia" not in res.media


def test_result_console_output_tree_formatting():
    res = Result.taken(
        url="https://example.com/alice",
        extra={"name": "Alice Doe", "bio": "Security researcher"},
        media={"avatar": "https://example.com/avatar.jpg"},
    )
    res.update(phone="+14155552671", site_name="Example")

    output = res.get_console_output(ScanConfig(verbose=True))
    assert "[✔]" in output
    assert "Example" in output
    assert "[https://example.com/alice]" in output
    assert "(+14155552671)" in output
    assert "Registered" in output
    assert "├──" in output
    assert "└──" in output
    assert "name: Alice Doe" in output
    assert "avatar: https://example.com/avatar.jpg" in output


def test_result_serialization():
    res = Result.taken(
        url="https://example.com/test",
        extra={"city": "San Francisco"},
        media={"avatar": "https://example.com/pic.png"},
    )
    res.update(phone="+14155552671", site_name="TestSite", category="Social")

    d = res.to_dict()
    assert d["phone"] == "+14155552671"
    assert d["site_name"] == "TestSite"
    assert d["category"] == "Social"
    assert d["status"] == "Registered"
    assert d["extra"]["city"] == "San Francisco"
    assert d["media"]["avatar"] == "https://example.com/pic.png"

    json_str = res.to_json()
    assert "San Francisco" in json_str

    csv_line = res.to_csv()
    assert "+14155552671" in csv_line
    assert "Registered" in csv_line


def test_result_show_runs(capsys):
    res = Result.taken(url="https://example.com")
    res.update(phone="+14155552671", site_name="ExampleSite")
    res.show(ScanConfig())
    out = capsys.readouterr().out
    assert "ExampleSite" in out
