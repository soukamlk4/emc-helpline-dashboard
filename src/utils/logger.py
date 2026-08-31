"""
Logger centralisé du pipeline EMC Helpline.

Chaque module (extractor, cleaner, validator, star_schema_builder) importe
get_logger(__name__) pour écrire ses messages à la fois dans la console
(pour un lancement manuel) et dans un fichier daté sous logs/ (pour garder
une trace après coup, utile si le pipeline tourne sans supervision directe).
"""

import logging
from datetime import date

from src.utils.config import LOGS_DIR

LOGS_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOGS_DIR / f"etl_{date.today().isoformat()}.log"

_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)

    if not logger.handlers:  # évite les doublons si get_logger est appelé plusieurs fois
        logger.setLevel(logging.INFO)

        file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(_FORMAT))

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(_FORMAT))

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger
