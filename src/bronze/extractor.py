"""
Extractor — couche Bronze.
Se contente de lire le fichier source tel quel, sans aucune transformation.
"""

import pandas as pd

from src.utils.logger import get_logger

logger = get_logger(__name__)


def extract(fichier_excel: str) -> pd.DataFrame:
    """Lit le fichier Excel brut de signalements, sans le modifier."""
    logger.info(f"Extraction du fichier : {fichier_excel}")
    df = pd.read_excel(fichier_excel)
    logger.info(f"{len(df)} lignes extraites, {len(df.columns)} colonnes.")
    return df
