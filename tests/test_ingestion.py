"""
Tests pour src/ingestion/file_ingestion.py

Ces tests nécessitent une base PostgreSQL accessible (contrairement à
test_cleaner.py / test_validator.py, qui sont de purs tests unitaires
sans dépendance externe). Chaque test réinitialise les tables concernées
pour rester indépendant des autres.
"""

import pandas as pd
import psycopg2
import pytest

from src.ingestion.file_ingestion import ingest_file
from src.utils.config import DB_CONFIG


@pytest.fixture(autouse=True)
def base_propre():
    """Vide les tables avant chaque test, pour que chaque test parte
    d'un état connu et ne dépende pas de l'ordre d'exécution."""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute(
        "TRUNCATE faits_signalements, dim_date, dim_genre, dim_age, "
        "dim_plateforme, dim_type_cyberviolence, dim_accompagnement, "
        "log_imports RESTART IDENTITY CASCADE;"
    )
    conn.commit()
    cur.close()
    conn.close()
    yield


def _fichier_valide(tmp_path, id_debut=1, n_lignes=3, nom="signalements.xlsx"):
    lignes = []
    for i in range(n_lignes):
        lignes.append({
            "id": id_debut + i, "titulaire": "Oui", "emetteur": "public",
            "cyberharcelementType": "Diffamation", "plateforme": "Facebook",
            "accompagnement": "Non", "date": pd.Timestamp("2025-03-15"),
            "genre": "Féminin", "age": "Âges de 18 à 25 ans",
            "typeAccompagnement": "Suppression", "langue": "fr", "anonymat": "Oui",
        })
    chemin = tmp_path / nom
    pd.DataFrame(lignes).to_excel(chemin, index=False)
    return chemin


def test_import_fichier_valide(tmp_path):
    chemin = _fichier_valide(tmp_path)
    resultat = ingest_file(str(chemin), deplacer_vers_bronze=False)
    assert resultat.succes is True
    assert resultat.inserees == 3
    assert resultat.lues == 3


def test_import_fichier_vide(tmp_path):
    chemin = tmp_path / "vide.xlsx"
    pd.DataFrame(columns=[
        "id", "titulaire", "emetteur", "cyberharcelementType", "plateforme",
        "accompagnement", "date", "genre", "age", "typeAccompagnement",
        "langue", "anonymat",
    ]).to_excel(chemin, index=False)
    resultat = ingest_file(str(chemin), deplacer_vers_bronze=False)
    assert resultat.succes is False
    assert "vide" in resultat.message.lower()


def test_import_mauvais_format(tmp_path):
    chemin = tmp_path / "invalide.xlsx"
    chemin.write_text("ceci n'est pas un fichier excel")
    resultat = ingest_file(str(chemin), deplacer_vers_bronze=False)
    assert resultat.succes is False
    assert resultat.deja_importe is False


def test_fichier_deja_importe_est_detecte(tmp_path):
    chemin = _fichier_valide(tmp_path)
    premier = ingest_file(str(chemin), deplacer_vers_bronze=False)
    assert premier.succes is True

    deuxieme = ingest_file(str(chemin), deplacer_vers_bronze=False)
    assert deuxieme.succes is False
    assert deuxieme.deja_importe is True


def test_import_incremental_deux_fichiers_differents(tmp_path):
    fichier_a = _fichier_valide(tmp_path, id_debut=1, n_lignes=3, nom="a.xlsx")
    fichier_b = _fichier_valide(tmp_path, id_debut=100, n_lignes=2, nom="b.xlsx")

    resultat_a = ingest_file(str(fichier_a), deplacer_vers_bronze=False)
    resultat_b = ingest_file(str(fichier_b), deplacer_vers_bronze=False)

    assert resultat_a.succes is True
    assert resultat_b.succes is True

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM faits_signalements;")
    total = cur.fetchone()[0]
    conn.close()

    assert total == 5  # 3 (fichier A) + 2 (fichier B), rien supprimé


def test_donnees_partiellement_invalides_charge_les_lignes_valides(tmp_path):
    lignes = [
        {"id": 1, "titulaire": "Oui", "emetteur": "public",
         "cyberharcelementType": "Diffamation", "plateforme": "Facebook",
         "accompagnement": "Non", "date": pd.Timestamp("2025-03-15"),
         "genre": "Féminin", "age": "Âges de 18 à 25 ans",
         "typeAccompagnement": "Suppression", "langue": "fr", "anonymat": "Oui"},
        {"id": 2, "titulaire": "Oui", "emetteur": "public",
         "cyberharcelementType": "Diffamation", "plateforme": None,  # invalide : plateforme manquante
         "accompagnement": "Non", "date": pd.Timestamp("2025-03-16"),
         "genre": "Masculin", "age": "Âges de 18 à 25 ans",
         "typeAccompagnement": "Suppression", "langue": "fr", "anonymat": "Oui"},
    ]
    chemin = tmp_path / "mixte.xlsx"
    pd.DataFrame(lignes).to_excel(chemin, index=False)

    resultat = ingest_file(str(chemin), deplacer_vers_bronze=False)

    assert resultat.succes is True
    assert resultat.lues == 2
    assert resultat.inserees == 1
    assert resultat.rejetees == 1


def test_fichier_inexistant():
    resultat = ingest_file("/chemin/qui/n_existe/pas.xlsx", deplacer_vers_bronze=False)
    assert resultat.succes is False
    assert "introuvable" in resultat.message.lower()
