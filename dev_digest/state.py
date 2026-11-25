import json
from pathlib import Path

STATE_FILE = Path(__file__).resolve().parent.parent / "data" / "state.json"


# Data saved by the last run; None on the first run
def load():
    if not STATE_FILE.exists():
        return None
    try:
        return json.loads(STATE_FILE.read_text())
    except json.JSONDecodeError:  # broken file: start over
        return None


def save(data):
    STATE_FILE.parent.mkdir(exist_ok=True)  # creates data/ on the first run
    STATE_FILE.write_text(json.dumps(data, indent=2))
