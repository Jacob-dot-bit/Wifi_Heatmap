"""Translation catalogues shared by the web front-end and the CLI."""

import json
import logging
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)

LOCALES_DIR = Path(__file__).resolve().parent.parent / "locales"
DEFAULT_LANGUAGE = "en"


def available_languages() -> List[Dict[str, str]]:
    """List the languages shipped in locales/, as {code, name} entries."""
    languages = []
    for path in sorted(LOCALES_DIR.glob("*.json")):
        try:
            with open(path, encoding="utf-8") as f:
                name = json.load(f).get("language.name", path.stem)
        except Exception as e:
            logger.warning(f"Unreadable catalogue {path.name}: {e}")
            continue
        languages.append({"code": path.stem, "name": name})
    return languages


def load_catalogue(language: str) -> Dict[str, str]:
    path = LOCALES_DIR / f"{language}.json"
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception as e:
        logger.warning(f"Unreadable catalogue {path.name}: {e}")
        return {}


class Translator:
    """Looks a key up in the active catalogue, falling back to English.

    A missing key returns the key itself rather than raising, so a partial
    translation degrades into readable output instead of breaking a screen.
    """

    def __init__(self, language: str = DEFAULT_LANGUAGE):
        self.fallback = load_catalogue(DEFAULT_LANGUAGE)
        self.set_language(language)

    def set_language(self, language: str) -> None:
        self.language = language or DEFAULT_LANGUAGE
        self.catalogue = (
            self.fallback
            if self.language == DEFAULT_LANGUAGE
            else load_catalogue(self.language) or self.fallback
        )

    def t(self, key: str, **params) -> str:
        text = self.catalogue.get(key) or self.fallback.get(key) or key
        if not params:
            return text
        try:
            return text.format(**params)
        except (KeyError, IndexError, ValueError):
            # A malformed placeholder must not crash a screen.
            return text
