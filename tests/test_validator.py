"""
Tests unitaires pour src/silver/validator.py
"""

import pandas as pd

from src.silver.cleaner import clean
from src.silver.validator import validate


def _df_valide(**overrides) -> pd.DataFrame:
    """Une ligne déjà nettoyée (post-clean) et valide par défaut."""
    base = {
        "id": 1,
        "titulaire": "Oui",
        "emetteur": "public",
        "cyberharcelementType": "Diffamation",
        "plateforme": "Facebook",
        "accompagnement": "Oui",
        "date": pd.Timestamp("2025-03-15"),
        "genre": "Féminin",
        "age": "Âges de 18 à 25 ans",
        "typeAccompagnement": "Juridique;Suppression",
        "langue": "fr",
        "anonymat": "Oui",
    }
    base.update(overrides)
    return clean(pd.DataFrame([base]))


def test_ligne_correcte_est_validee():
    df_valid, df_invalid = validate(_df_valide())
    assert len(df_valid) == 1
    assert len(df_invalid) == 0


def test_id_manquant_est_rejete():
    df = _df_valide()
    df.loc[0, "id"] = None
    df_valid, df_invalid = validate(df)
    assert len(df_valid) == 0
    assert len(df_invalid) == 1
    assert "id manquant" in df_invalid.loc[0, "raison_rejet"]


def test_date_invalide_est_rejetee():
    df = _df_valide(date="pas-une-date")  # clean() la transforme en NaT
    df_valid, df_invalid = validate(df)
    assert len(df_valid) == 0
    assert "date" in df_invalid.loc[0, "raison_rejet"]


def test_plateforme_manquante_est_rejetee():
    df = _df_valide()
    df.loc[0, "plateforme"] = None
    df_valid, df_invalid = validate(df)
    assert len(df_valid) == 0
    assert "plateforme" in df_invalid.loc[0, "raison_rejet"]


def test_type_cyberviolence_manquant_est_rejete():
    df = _df_valide()
    df.loc[0, "cyberharcelementType"] = None
    df_valid, df_invalid = validate(df)
    assert len(df_valid) == 0
    assert "cyberviolence" in df_invalid.loc[0, "raison_rejet"]


def test_genre_non_renseigne_reste_valide():
    """'Non renseigné' est une valeur ACCEPTÉE (pas une erreur) — ce n'est
    pas une valeur manquante brute, c'est le résultat volontaire du
    nettoyage (cf. cleaner.py)."""
    df_valid, df_invalid = validate(_df_valide(genre=None))
    assert len(df_valid) == 1
    assert len(df_invalid) == 0


def test_plusieurs_lignes_valides_et_invalides_melangees():
    df_ok = _df_valide(id=1)
    df_ko = _df_valide(id=2)
    df_ko.loc[0, "plateforme"] = None
    df = pd.concat([df_ok, df_ko], ignore_index=True)

    df_valid, df_invalid = validate(df)

    assert len(df_valid) == 1
    assert len(df_invalid) == 1
    assert df_valid["id"].iloc[0] == 1
    assert df_invalid["id"].iloc[0] == 2


def test_lignes_valides_ne_sont_pas_modifiees():
    """La validation ne doit jamais changer les valeurs des lignes valides."""
    df_original = _df_valide()
    df_valid, _ = validate(df_original.copy())
    assert df_valid.loc[0, "genre"] == df_original.loc[0, "genre"]
    assert df_valid.loc[0, "plateforme"] == df_original.loc[0, "plateforme"]
