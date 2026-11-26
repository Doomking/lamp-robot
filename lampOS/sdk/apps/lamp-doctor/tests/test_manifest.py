"""The manifest never holds `net`: Lamp Doctor reads what was said (`conversation`), and lamp-control
refuses `conversation` beside `net` (#8726), so a later edit must not add it unseen."""

import json
from pathlib import Path

MANIFEST = json.loads((Path(__file__).resolve().parent.parent / "app.json").read_text())


def test_net_is_off():
    assert MANIFEST.get("net", False) is False


def test_net_is_not_among_the_grants():
    assert "net" not in MANIFEST["grants"]


def test_the_grants_are_exactly_the_four_the_design_names():
    assert sorted(MANIFEST["grants"]) == ["conversation", "model", "report", "turns"]


def test_the_entry_module_exists():
    here = Path(__file__).resolve().parent.parent / "src"
    module = MANIFEST["runtime"]["entry"].replace(".", "/")
    assert (here / f"{module}.py").is_file()
