import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixture_json():
    def load(name: str):
        return json.loads((FIXTURES / name).read_text())

    return load


@pytest.fixture
def fixture_text():
    def load(name: str) -> str:
        return (FIXTURES / name).read_text()

    return load


@pytest.fixture(autouse=True)
def isolated_cwd(tmp_path, monkeypatch):
    """Run every test inside an empty temp directory.

    Relative paths in configs (data/jobhunter.db, config/cv/master.tex, ...) then resolve
    there, so a test can never read or modify the person's real database, CV or output.
    """
    monkeypatch.chdir(tmp_path)
