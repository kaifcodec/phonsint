import csv
import json
import sys
import pytest

from phonsint.__main__ import export_results, list_modules, print_banner, main
from phonsint.core.result import Result


def test_export_results_json(tmp_path):
    out_file = tmp_path / "out.json"
    res1 = Result.taken(url="https://example.com/user", extra={"username": "testuser"})
    res1.update(phone="+14155552671", site_name="Example", category="Social")

    res2 = Result.available(url="https://example.com/login")
    res2.update(phone="+14155552671", site_name="Other", category="Auth")

    export_results([res1, res2], str(out_file), fmt="json")

    assert out_file.exists()
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert len(data) == 2
    assert data[0]["phone"] == "+14155552671"
    assert data[0]["site_name"] == "Example"
    assert data[0]["status"] == "Registered"
    assert data[0]["extra"]["username"] == "testuser"
    assert data[1]["status"] == "Not Registered"


def test_export_results_csv(tmp_path):
    out_file = tmp_path / "out.csv"
    res = Result.taken(url="https://example.com/profile", extra={"role": "admin"})
    res.update(phone="+14155552671", site_name="Portal", category="CRM")

    export_results([res], str(out_file), fmt="csv")

    assert out_file.exists()
    with open(out_file, newline="", encoding="utf-8") as f:
        reader = list(csv.reader(f))
    assert len(reader) == 2
    header = reader[0]
    row = reader[1]
    assert header == ["site_name", "category", "phone", "status", "url", "extra", "media", "reason"]
    assert row[0] == "Portal"
    assert row[1] == "CRM"
    assert row[2] == "+14155552671"
    assert row[3] == "Registered"
    assert "admin" in row[5]


def test_list_modules_runs(capsys):
    list_modules()
    out = capsys.readouterr().out
    assert "Available Scan Modules" in out
    assert "Facebook" in out or "facebook" in out


def test_print_banner(capsys):
    print_banner()
    out = capsys.readouterr().out
    assert "phonsint" in out.lower()


def test_main_without_args_exits(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["phonsint"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1


def test_main_list_flag(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["phonsint", "-l"])
    main()
    out = capsys.readouterr().out
    assert "Available Scan Modules" in out
