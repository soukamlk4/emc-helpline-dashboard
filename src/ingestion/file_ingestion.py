"""
file_ingestion.py - Version simplifiée pour Streamlit Cloud
L'import de données est désactivé sur la version cloud.
"""

from dataclasses import dataclass
from pathlib import Path
import shutil
import hashlib

@dataclass
class IngestionResult:
    succes: bool = False
    message: str = "L'import de données est désactivé sur la version cloud."
    deja_importe: bool = False
    lues: int = 0
    valides: int = 0
    inserees: int = 0
    ignorees: int = 0
    rejetees: int = 0


def ingest_file(file_path, deplacer_vers_bronze=True):
    """
    Version simplifiée : indique que l'import est désactivé.
    """
    return IngestionResult(
        succes=False,
        message="⚠️ L'import de données est désactivé sur la version cloud. Les données sont chargées depuis le fichier CSV existant.",
        deja_importe=False
    )
