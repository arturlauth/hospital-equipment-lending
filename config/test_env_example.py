import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_env_example_lists_every_variable_settings_reads():
    settings = (ROOT / "config" / "settings.py").read_text(encoding="utf-8")
    read = set(re.findall(r"os\.environ(?:\.get\(|\[)\"(\w+)\"", settings))
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    listed = {line.split("=", 1)[0] for line in example.splitlines() if "=" in line}
    assert read - listed == set()
