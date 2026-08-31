"""
File ingestion — point d'entrée unique pour tout nouveau fichier de
signalements, qu'il vienne de la ligne de commande (etl_main.py) ou d'un
upload depuis le dashboard Streamlit.

Responsabilités :
- calculer une empreinte (hash) du fichier pour détecter un import déjà fait ;
- sauvegarder le fichier dans data/bronze/ (couche brute, jamais modifiée) ;
- déclencher le pipeline extract -> clean -> validate -> load ;
- ne jamais faire planter l'appelant : les erreurs sont renvoyées sous
  forme de résultat structuré, pas d'exception qui remonterait jusqu'à
  l'interface Streamlit.
"""

import hashlib
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import psycopg2

from src.bronze.extractor import extract
from src.silver.cleaner import clean
from src.silver.validator import validate
from src.gold.star_schema_builder import load
from src.utils.config import DB_CONFIG, DATA_BRONZE_DIR
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ResultatIngestion:
    succes: bool
    deja_importe: bool = False
    message: str = ""
    lues: int = 0
    valides: int = 0
    inserees: int = 0
    ignorees: int = 0
    rejetees: int = 0


def _calculer_hash(chemin_fichier: Path) -> str:
    """Empreinte SHA-256 du contenu du fichier, pour détecter un fichier
    déjà importé même s'il a été renommé."""
    sha256 = hashlib.sha256()
    with open(chemin_fichier, "rb") as f:
        for bloc in iter(lambda: f.read(8192), b""):
            sha256.update(bloc)
    return sha256.hexdigest()


def _fichier_deja_importe(fichier_hash: str) -> bool:
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM log_imports WHERE fichier_hash = %s AND statut = 'succes' LIMIT 1",
            (fichier_hash,),
        )
        return cur.fetchone() is not None
    finally:
        conn.close()


def _sauvegarder_dans_bronze(fichier_source: Path) -> Path:
    """Copie le fichier uploadé dans data/bronze/, avec un nom daté pour
    ne jamais écraser un import précédent."""
    DATA_BRONZE_DIR.mkdir(parents=True, exist_ok=True)
    horodatage = datetime.now().strftime("%Y%m%d_%H%M%S")
    nom_cible = f"{horodatage}_{fichier_source.name}"
    chemin_cible = DATA_BRONZE_DIR / nom_cible
    shutil.copy(fichier_source, chemin_cible)
    return chemin_cible


def ingest_file(chemin_fichier, deplacer_vers_bronze: bool = True) -> ResultatIngestion:
    """
    Point d'entrée unique d'ingestion d'un fichier Excel de signalements.

    Args:
        chemin_fichier : chemin vers le fichier Excel à importer.
        deplacer_vers_bronze : si True, copie d'abord le fichier dans
            data/bronze/ (cas d'un upload) ; si False, le fichier est déjà
            à sa place (cas d'un import en ligne de commande sur un
            fichier déjà présent dans data/bronze/).

    Ne lève jamais d'exception : toute erreur est renvoyée dans le
    ResultatIngestion, pour que l'appelant (notamment Streamlit) puisse
    afficher un message clair sans planter.
    """
    chemin_fichier = Path(chemin_fichier)
    logger.info(f"Ingestion demandée : {chemin_fichier.name}")

    if not chemin_fichier.exists():
        return ResultatIngestion(succes=False, message=f"Fichier introuvable : {chemin_fichier}")

    try:
        fichier_hash = _calculer_hash(chemin_fichier)
    except Exception as e:
        logger.error(f"Impossible de lire le fichier : {e}")
        return ResultatIngestion(succes=False, message=f"Fichier illisible : {e}")

    if _fichier_deja_importe(fichier_hash):
        logger.warning(f"Fichier déjà importé (hash identique) : {chemin_fichier.name}")
        return ResultatIngestion(
            succes=False, deja_importe=True,
            message="⚠️ Ce fichier a déjà été importé (contenu identique détecté).",
        )

    if deplacer_vers_bronze:
        chemin_bronze = _sauvegarder_dans_bronze(chemin_fichier)
    else:
        chemin_bronze = chemin_fichier

    try:
        df_brut = extract(str(chemin_bronze))
    except Exception as e:
        logger.error(f"Échec de l'extraction : {e}")
        return ResultatIngestion(
            succes=False, message=f"Fichier invalide ou format inattendu : {e}"
        )

    if len(df_brut) == 0:
        logger.warning("Fichier vide, aucune ligne à importer.")
        return ResultatIngestion(succes=False, message="Le fichier est vide (0 ligne).")

    try:
        df_propre = clean(df_brut)
        df_valide, df_invalide = validate(df_propre)
    except Exception as e:
        logger.error(f"Échec du nettoyage/validation : {e}")
        return ResultatIngestion(
            succes=False, message=f"Erreur lors du nettoyage des données : {e}", lues=len(df_brut)
        )

    if len(df_valide) == 0:
        logger.warning("Aucune ligne valide après validation.")
        return ResultatIngestion(
            succes=False, lues=len(df_brut), rejetees=len(df_invalide),
            message="Aucune ligne valide dans ce fichier (toutes rejetées par la validation).",
        )

    try:
        resultat = load(df_valide, str(chemin_bronze), len(df_brut), len(df_invalide), fichier_hash)
    except Exception as e:
        logger.error(f"Échec du chargement en base : {e}")
        return ResultatIngestion(
            succes=False, lues=len(df_brut), valides=len(df_valide), rejetees=len(df_invalide),
            message=f"Erreur lors du chargement en base (transaction annulée) : {e}",
        )

    logger.info(f"Ingestion réussie pour {chemin_fichier.name} : {resultat}")
    return ResultatIngestion(
        succes=True,
        message=f"Import réussi : {resultat['inserees']} nouvelles lignes ajoutées.",
        lues=resultat["lues"], valides=len(df_valide),
        inserees=resultat["inserees"], ignorees=resultat["ignorees"],
        rejetees=resultat["rejetees"],
    )
