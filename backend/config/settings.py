import json
from pathlib import Path

_settings = None

def get_settings() -> dict:
    global _settings
    if _settings is None:
        settings_path = Path(__file__).parent / "settings.json"
        with open(settings_path) as f:
            _settings = json.load(f)
    return _settings
