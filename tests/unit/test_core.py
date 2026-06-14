from pathlib import Path

import nina_core


def test_version():
    repo_root = Path(__file__).resolve().parents[2]
    version_file = repo_root / "VERSION"
    expected_version = version_file.read_text().strip().splitlines()[0].strip()
    assert nina_core.__version__ == expected_version
