import json
from os import getenv
from pathlib import Path

from IPython.display import Markdown, display


def ensure_env_file():
    """Ensure .env file exists in the examples directory."""
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        env_path.touch()
        print("Created empty .env file")
    return env_path


def check_env_variables(required_keys: list[str]) -> bool:
    """Check if all required environment variables are set.

    Returns True if all keys exist, False otherwise.
    """
    import dotenv

    dotenv.load_dotenv()

    missing_keys = []
    for key in required_keys:
        if not getenv(key):
            missing_keys.append(key)

    if missing_keys:
        current_dir = Path(__file__).parent
        print(f"Missing required environment variables: {', '.join(missing_keys)}")
        print(f"Please add them to your .env file in the {current_dir} directory")
        return False
    return True


def setup_notebook(required_keys: list[str] | None = None):
    """Perform common setup for notebooks.

    Common setup for notebooks includes:
    1. Ensures .env file exists
    2. Checks required environment variables
    3. Returns True if setup is successful
    """
    ensure_env_file()
    if required_keys:
        return check_env_variables(required_keys)
    return True


def json_pretty_print(title: str, json_dict: dict) -> None:
    """Pretty print a JSON dictionary."""
    display(Markdown(f"{title}\n```json\n{json.dumps(json_dict, indent=2)}\n```"))
