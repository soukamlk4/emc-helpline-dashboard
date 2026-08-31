"""
Cleaner — couche Silver.
Reprend exactement le nettoyage validé au Jalon 2 : suppression des colonnes
inutiles, normalisation de la date, standardisation des variables
catégorielles, traitement des valeurs manquantes, décomposition de
typeAccompagnement.
"""

import pandas as pd

from src.utils.logger import get_logger

logger = get_logger(__name__)

AGE_MAP = {
    "Âges de 5 à 12 ans": "5-12 ans",
    "Âges de 13 à 17 ans": "13-17 ans",
    "Âges de 18 à 25 ans": "18-25 ans",
    "Plus de 26 ans": "+26 ans",
    "Non renseigné": "Non renseigné",
}

TYPES_ACCOMPAGNEMENT = ["Juridique", "Psychique", "Suppression"]


def _statut_age(tranche: str) -> str:
    if tranche in ["5-12 ans", "13-17 ans"]:
        return "Mineur"
    elif tranche == "18-25 ans":
        return "Jeune adulte"
    elif tranche == "+26 ans":
        return "Adulte"
    return "Non renseigné"


def clean(df: pd.DataFrame) -> pd.DataFrame:
    logger.info(f"Nettoyage de {len(df)} lignes...")
    df = df.copy()

    # Colonnes non utilisées
    df = df.drop(columns=["titulaire", "emetteur"], errors="ignore")

    # Date
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    df["annee"] = df["date"].dt.year
    df["mois"] = df["date"].dt.month
    df["trimestre"] = df["date"].dt.quarter

    # Standardisation de la casse
    df["accompagnement"] = df["accompagnement"].str.strip().str.capitalize()
    df["langue"] = df["langue"].str.strip().str.lower()
    df["cyberharcelementType"] = df["cyberharcelementType"].str.strip()

    # Valeurs manquantes catégorielles
    nb_nan_genre = df["genre"].isnull().sum()
    nb_nan_age = df["age"].isnull().sum()
    df["genre"] = df["genre"].fillna("Non renseigné")
    df["age"] = df["age"].fillna("Non renseigné")
    logger.info(f"Valeurs manquantes remplacées : genre={nb_nan_genre}, age={nb_nan_age}")

    # Simplification des tranches d'âge + statut
    df["age"] = df["age"].replace(AGE_MAP)
    df["statut_age"] = df["age"].apply(_statut_age)

    # Décomposition typeAccompagnement -> colonnes binaires
    for t in TYPES_ACCOMPAGNEMENT:
        df[f"accomp_{t.lower()}"] = df["typeAccompagnement"].apply(
            lambda x, t=t: t in str(x).split(";")
        )

    logger.info(f"Nettoyage terminé : {len(df)} lignes, {len(df.columns)} colonnes.")
    return df
