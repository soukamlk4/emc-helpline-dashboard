"""
Validator — dernière étape de la couche Silver.
Vérifie que chaque ligne nettoyée respecte les règles minimales avant
chargement en base. Les lignes invalides sont séparées et journalisées,
plutôt que de faire échouer tout le pipeline pour une seule ligne suspecte.
"""

import pandas as pd

from src.utils.logger import get_logger

logger = get_logger(__name__)

GENRES_VALIDES = {"Masculin", "Féminin", "Non renseigné"}
AGES_VALIDES = {"5-12 ans", "13-17 ans", "18-25 ans", "+26 ans", "Non renseigné"}
OUI_NON_VALIDES = {"Oui", "Non"}
LANGUES_VALIDES = {"fr", "ar"}


def _valider_ligne(row) -> list[str]:
    """Retourne la liste des raisons de rejet pour une ligne (vide si valide)."""
    erreurs = []

    if pd.isna(row.get("id")):
        erreurs.append("id manquant")

    if pd.isna(row.get("date")):
        erreurs.append("date invalide ou manquante")

    if row.get("genre") not in GENRES_VALIDES:
        erreurs.append(f"genre inattendu : {row.get('genre')!r}")

    if row.get("age") not in AGES_VALIDES:
        erreurs.append(f"tranche d'âge inattendue : {row.get('age')!r}")

    if not row.get("plateforme") or pd.isna(row.get("plateforme")):
        erreurs.append("plateforme manquante")

    if not row.get("cyberharcelementType") or pd.isna(row.get("cyberharcelementType")):
        erreurs.append("type de cyberviolence manquant")

    if row.get("accompagnement") not in OUI_NON_VALIDES:
        erreurs.append(f"accompagnement inattendu : {row.get('accompagnement')!r}")

    if row.get("anonymat") not in OUI_NON_VALIDES:
        erreurs.append(f"anonymat inattendu : {row.get('anonymat')!r}")

    if row.get("langue") not in LANGUES_VALIDES:
        erreurs.append(f"langue inattendue : {row.get('langue')!r}")

    return erreurs


def validate(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Sépare le DataFrame en (lignes_valides, lignes_invalides).
    lignes_invalides contient une colonne supplémentaire 'raison_rejet'.
    """
    logger.info(f"Validation de {len(df)} lignes...")

    resultats = df.apply(_valider_ligne, axis=1)
    est_valide = resultats.apply(len) == 0

    df_valides = df[est_valide].copy()
    df_invalides = df[~est_valide].copy()
    df_invalides["raison_rejet"] = resultats[~est_valide].apply("; ".join)

    logger.info(f"Validation terminée : {len(df_valides)} valides, {len(df_invalides)} rejetées.")
    if len(df_invalides) > 0:
        for _, row in df_invalides.iterrows():
            logger.warning(f"Ligne id={row.get('id')} rejetée : {row['raison_rejet']}")

    return df_valides, df_invalides
