"""A class of six submissions, named as students name their package
(``<ident>_<surname>``, not the reference's name), read by the typical errors
of the encapsulation principle (Review Focus 1)."""

from __future__ import annotations

import shutil
from pathlib import Path

from pythonarchtesting.cli import main
from pythonarchtesting.mcp_server.reports import class_overview, explain_target

_PRINCIPLE = (
    Path(__file__).resolve().parents[2] / "example" / "principles" / "encapsulation"
)
_CLASS = {
    "ok_basic": "xxxx01_novak",
    "err_sell_bypasses_remove": "xxxx02_dvorak",
    "err_restock_writes_log": "xxxx03_svoboda",
    "err_clear_out_replaces_stock": "xxxx04_cerna",
    "ok_wrong_math": "xxxx05_kral",
    # Reading a private attribute (forbid_private_access, static). dvorak's
    # code reads _stock too, on the line before its write; cerna's reads it
    # on the line that replaces it, which is part of that write (one finding).
    "err_report_reads_private": "xxxx06_benes",
}
# Built from ok_basic in the test: shop.py raises on import, so nothing is
# judged; clear_out deletes Inventory.log, which no typical error declares.
_BROKEN = "xxxx07_horak"
_DELETES = "xxxx08_ruzicka"


def _variant(submissions: Path, student: str, old: str, new: str) -> None:
    shutil.copytree(_PRINCIPLE / "assignments" / "ok_basic", submissions / student)
    shop = submissions / student / "shop.py"
    text = shop.read_text(encoding="utf-8")
    assert old in text
    shop.write_text(text.replace(old, new, 1), encoding="utf-8")


def test_class_overview_of_six_submissions(tmp_path: Path) -> None:
    submissions = tmp_path / "submissions"
    for variant, student in _CLASS.items():
        shutil.copytree(_PRINCIPLE / "assignments" / variant, submissions / student)
    _variant(
        submissions,
        _BROKEN,
        "from .inventory import Inventory\n",
        "from .inventory import Inventory\n\nraise RuntimeError('half-finished')\n",
    )
    _variant(
        submissions,
        _DELETES,
        "    return quantity\n",
        "    del inventory.log\n    return quantity\n",
    )
    report = tmp_path / "report.json"
    main(
        [
            "--source",
            str(_PRINCIPLE),
            "--targets-dir",
            str(submissions),
            "--format",
            "json",
            "--output",
            str(report),
            "--dynamic",
        ]
    )

    overview = class_overview(str(report), "encapsulation")

    counts = (
        overview["submissions"],
        overview["passed"],
        overview["failed"],
        overview["not_judged"],
    )
    assert counts == (8, 2, 5, 1)
    counts = {error_id: b["count"] for error_id, b in overview["by_error"].items()}
    assert counts == {
        "bypass_method": 1,
        "mutate_container": 1,
        "replace_attribute": 1,
        "read_private": 2,
        "unclassified": 1,
    }
    names = {error_id: b["submissions"] for error_id, b in overview["by_error"].items()}
    assert names == {
        "bypass_method": ["xxxx02_dvorak"],
        "mutate_container": ["xxxx03_svoboda"],
        "replace_attribute": ["xxxx04_cerna"],
        "read_private": ["xxxx02_dvorak", "xxxx06_benes"],
        "unclassified": [_DELETES],
    }
    assert {
        reason: b["submissions"]
        for reason, b in overview["not_judged_by_reason"].items()
    } == {"probe_import_error": [_BROKEN]}
    rows = {row["name"]: row for row in overview["submissions_page"]}
    assert set(rows) == {*_CLASS.values(), _BROKEN, _DELETES}
    assert rows["xxxx06_benes"]["errors"] == ["read_private"]
    assert rows["xxxx05_kral"]["errors"] == []
    assert rows["xxxx06_benes"]["verdict"] == "failed"
    assert rows[_BROKEN]["verdict"] == "not_judged"
    assert rows[_DELETES]["verdict"] == "failed"

    deleted = explain_target(str(report), _DELETES, principle="encapsulation")
    [finding] = deleted["findings"]
    assert finding["error_id"] is None and "not_judged" not in finding
    assert finding["facts"]["change"] == "deleted"
    assert finding["target"] == "shop:clear_out"
    broken = explain_target(str(report), _BROKEN, principle="encapsulation")
    assert broken["verdict"] == "not_judged"
    assert {f["reason"] for f in broken["findings"]} == {"probe_import_error"}
    assert all(f["not_judged"] and f["target"] for f in broken["findings"])

    found = explain_target(str(report), "xxxx04_cerna", principle="encapsulation")
    # `inventory._stock = {... inventory._stock.items() ...}`: the read on
    # the line of the write is part of it.
    [finding] = found["findings"]
    assert finding["error_id"] == "replace_attribute"
    assert finding["target"] == "shop:clear_out"
    assert "`Inventory._stock`" in finding["what"]
    benes = explain_target(str(report), "xxxx06_benes", principle="encapsulation")
    assert [f["error_id"] for f in benes["findings"]] == ["read_private"] * 2
    assert all(f["target"] == "shop:report" for f in benes["findings"])
