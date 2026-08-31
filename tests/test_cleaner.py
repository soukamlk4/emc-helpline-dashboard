"""
Tests unitaires pour src/silver/cleaner.py
"""

import pandas as pd
import pytest

from src.silver.cleaner import clean, _statut_age


def _df_minimal(**overrides) -> pd.DataFrame:
    """Construit une ligne minimale valide, avec possibilité de surcharger des champs."""
    base = {
        "id": 1,
        "titulaire": "Oui",
        "emetteur": "public",
        "cyberharcelementType": " Diffamation",
        "plateforme": "Facebook",
        "accompagnement": "OUI",
        "date": pd.Timestamp("2025-03-15"),
        "genre": "Féminin",
        "age": "Âges de 18 à 25 ans",
        "typeAccompagnement": "Juridique;Suppression",
        "langue": "FR",
        "anonymat": "Oui",
    }
    base.update(overrides)
    return pd.DataFrame([base])


def test_supprime_titulaire_et_emetteur():
    df = clean(_df_minimal())
    assert "titulaire" not in df.columns
    assert "emetteur" not in df.columns


def test_standardise_accompagnement_casse():
    for valeur_brute in ["oui", "OUI", "Oui", " oui "]:
        df = clean(_df_minimal(accompagnement=valeur_brute))
        assert df.loc[0, "accompagnement"] == "Oui"


def test_standardise_langue_casse():
    for valeur_brute in ["fr", "FR", " fr "]:
        df = clean(_df_minimal(langue=valeur_brute))
        assert df.loc[0, "langue"] == "fr"


def test_supprime_espaces_type_cyberviolence():
    df = clean(_df_minimal(cyberharcelementType=" Diffamation "))
    assert df.loc[0, "cyberharcelementType"] == "Diffamation"


def test_genre_manquant_devient_non_renseigne():
    df = clean(_df_minimal(genre=None))
    assert df.loc[0, "genre"] == "Non renseigné"


def test_age_manquant_devient_non_renseigne():
    df = clean(_df_minimal(age=None))
    assert df.loc[0, "age"] == "Non renseigné"


def test_simplifie_libelle_age():
    df = clean(_df_minimal(age="Âges de 13 à 17 ans"))
    assert df.loc[0, "age"] == "13-17 ans"


@pytest.mark.parametrize("age_brut,statut_attendu", [
    ("Âges de 5 à 12 ans", "Mineur"),
    ("Âges de 13 à 17 ans", "Mineur"),
    ("Âges de 18 à 25 ans", "Jeune adulte"),
    ("Plus de 26 ans", "Adulte"),
    (None, "Non renseigné"),
])
def test_statut_age_correct_selon_tranche(age_brut, statut_attendu):
    df = clean(_df_minimal(age=age_brut))
    assert df.loc[0, "statut_age"] == statut_attendu


def test_decompose_type_accompagnement_en_colonnes_binaires():
    df = clean(_df_minimal(typeAccompagnement="Juridique;Psychique;Suppression"))
    assert df.loc[0, "accomp_juridique"] == True
    assert df.loc[0, "accomp_psychique"] == True
    assert df.loc[0, "accomp_suppression"] == True


def test_accompagnement_partiel_seul_juridique():
    df = clean(_df_minimal(typeAccompagnement="Juridique"))
    assert df.loc[0, "accomp_juridique"] == True
    assert df.loc[0, "accomp_psychique"] == False
    assert df.loc[0, "accomp_suppression"] == False


def test_date_invalide_devient_nat_sans_planter():
    df = clean(_df_minimal(date="pas-une-date"))
    assert pd.isna(df.loc[0, "date"])


def test_ne_modifie_pas_le_nombre_de_lignes():
    df_brut = pd.concat([_df_minimal(id=i) for i in range(5)], ignore_index=True)
    df_propre = clean(df_brut)
    assert len(df_propre) == len(df_brut)
