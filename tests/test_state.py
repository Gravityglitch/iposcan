import json
from pathlib import Path

from iposcan.state import load_alerted, save_alerted


def test_load_alerted_returns_empty_set_when_file_missing(tmp_path: Path):
    assert load_alerted(tmp_path / "missing.json") == set()


def test_load_alerted_reads_existing_names(tmp_path: Path):
    path = tmp_path / "state.json"
    path.write_text(json.dumps({"alerted": ["Ardee Industries", "Milky Mist"]}))
    assert load_alerted(path) == {"Ardee Industries", "Milky Mist"}


def test_save_alerted_writes_sorted_json(tmp_path: Path):
    path = tmp_path / "nested" / "state.json"
    save_alerted(path, {"Zeta Corp", "Ardee Industries"})
    data = json.loads(path.read_text())
    assert data == {"alerted": ["Ardee Industries", "Zeta Corp"]}


def test_round_trip_through_load_and_save(tmp_path: Path):
    path = tmp_path / "state.json"
    save_alerted(path, {"Foo", "Bar"})
    assert load_alerted(path) == {"Foo", "Bar"}
