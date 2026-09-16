import configparser
import os

SETTINGS_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "settings.ini"
)

DEFAULTS = {
    "start_folder": os.path.expanduser("~\\Documents"),
    "download_folder": os.path.expanduser("~\\Downloads"),
    "sounds_enabled": "yes",
    "server_address": "",
    "server_username": "",
    "server_password": "",
}


def load_settings():
    """Read settings from disk. Missing values fall back to defaults."""
    parser = configparser.ConfigParser()
    parser["general"] = DEFAULTS.copy()

    if os.path.exists(SETTINGS_FILE):
        parser.read(SETTINGS_FILE, encoding="utf-8")

    return parser


def save_settings(parser):
    """Write the settings back to disk."""
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        parser.write(f)


def get(parser, key):
    """Read one setting by name."""
    return parser["general"].get(key, DEFAULTS.get(key, ""))


def set_value(parser, key, value):
    """Change one setting, then save the file."""
    parser["general"][key] = str(value)
    save_settings(parser)