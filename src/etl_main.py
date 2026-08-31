"""
Point d'entrée du pipeline ETL complet.
Orchestre : extract -> clean -> validate -> load, avec les logs et la
gestion d'erreurs déjà intégrés dans chaque module.

Usage : python3 -m src.etl_main data/bronze/signalements.xlsx
"""

import sys

from src.bronze.extractor import extract
from src.silver.cleaner import clean
from src.silver.validator import validate
from src.gold.star_schema_builder import load
from src.utils.logger import get_logger

logger = get_logger(__name__)


def run_pipeline(fichier_excel: str) -> dict:
    logger.info(f"=== Démarrage du pipeline ETL pour {fichier_excel} ===")

    df_brut = extract(fichier_excel)
    df_propre = clean(df_brut)
    df_valide, df_invalide = validate(df_propre)

    resultat = load(df_valide, fichier_excel, len(df_brut), len(df_invalide))

    logger.info(f"=== Pipeline terminé : {resultat} ===")
    return resultat


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage : python3 -m src.etl_main <chemin_fichier.xlsx>")
        sys.exit(1)

    resultat = run_pipeline(sys.argv[1])
    print(
        f"Import terminé : {resultat['lues']} lues, {resultat['inserees']} insérées, "
        f"{resultat['ignorees']} déjà présentes, {resultat['rejetees']} rejetées (validation)."
    )
