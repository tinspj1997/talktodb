import json
import os
import tempfile

# Local JSON file that holds the application's own state: one entry per
# saved connection with its id and the schema read on --connect.
CORE_STATE_PATH = "talktodb_state.json"


class StateError(Exception):
    """The state file exists but cannot be read."""


def load_state() -> dict:
    """Return the saved state, or an empty one if the file does not exist."""
    try:
        with open(CORE_STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"connections": {}}
    except json.JSONDecodeError as exc:
        raise StateError(f"{CORE_STATE_PATH} is not valid JSON ({exc}). Fix or delete it.") from exc


def save_state(state: dict) -> None:
    """Write the state atomically: a temp file in the same folder replaces the
    old file in one step, so a crash mid-write never leaves it half written."""
    folder = os.path.dirname(os.path.abspath(CORE_STATE_PATH))
    fd, tmp_path = tempfile.mkstemp(dir=folder, prefix=".talktodb_state.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        os.replace(tmp_path, CORE_STATE_PATH)
    except BaseException:
        os.unlink(tmp_path)
        raise
