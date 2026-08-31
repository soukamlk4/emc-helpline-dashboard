import psycopg2
import pandas as pd

from src.utils.config import DB_CONFIG
from src.utils.logger import get_logger

logger = get_logger(__name__)

MOIS_FR = {
    1: "Janvier", 2: "Février", 3: "Mars", 4: "Avril", 5: "Mai", 6: "Juin",
    7: "Juillet", 8: "Août", 9: "Septembre", 10: "Octobre", 11: "Novembre", 12: "Décembre",
}


def _get_or_create_date(cur, date_complete, annee, mois, trimestre, nom_mois):
    cur.execute("SELECT date_id FROM dim_date WHERE date_complete = %s", (date_complete,))
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute(
        "INSERT INTO dim_date (date_complete, annee, mois, trimestre, nom_mois) "
        "VALUES (%s, %s, %s, %s, %s) RETURNING date_id",
        (date_complete, annee, mois, trimestre, nom_mois),
    )
    return cur.fetchone()[0]


def _get_or_create(cur, table, id_col, unique_cols, values):
    where_clause = " AND ".join([f"{c} = %s" for c in unique_cols])
    cur.execute(f"SELECT {id_col} FROM {table} WHERE {where_clause}", values)
    row = cur.fetchone()
    if row:
        return row[0]
    cols = ", ".join(unique_cols)
    placeholders = ", ".join(["%s"] * len(values))
    cur.execute(
        f"INSERT INTO {table} ({cols}) VALUES ({placeholders}) RETURNING {id_col}",
        values,
    )
    return cur.fetchone()[0]


def load(df_valid: pd.DataFrame, fichier_source: str, nb_lignes_lues: int,
         nb_lignes_rejetees: int, fichier_hash: str = None) -> dict:
    """
    Charge les lignes validées dans le data warehouse, dans une seule
    transaction (tout ou rien). Journalise l'import (succès ou échec)
    dans log_imports, avec le hash du fichier pour l'étape d'idempotence
    au niveau fichier (voir file_ingestion.py).
    """
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    nb_inserees = 0
    nb_ignorees = 0

    try:
        logger.info(f"Début du chargement de {len(df_valid)} lignes validées...")

        for _, row in df_valid.iterrows():
            date_id = _get_or_create_date(
                cur, row["date"].date(), int(row["annee"]), int(row["mois"]),
                int(row["trimestre"]), MOIS_FR[row["mois"]],
            )
            genre_id = _get_or_create(cur, "dim_genre", "genre_id", ["genre"], [row["genre"]])
            age_id = _get_or_create(
                cur, "dim_age", "age_id", ["tranche_age", "statut_age"],
                [row["age"], row["statut_age"]],
            )
            plateforme_id = _get_or_create(
                cur, "dim_plateforme", "plateforme_id", ["plateforme"], [row["plateforme"]]
            )
            type_id = _get_or_create(
                cur, "dim_type_cyberviolence", "type_id",
                ["type_cyberviolence"], [row["cyberharcelementType"]],
            )
            accomp_id = _get_or_create(
                cur, "dim_accompagnement", "accomp_id",
                ["accompagnement", "type_accompagnement"],
                [row["accompagnement"], row["typeAccompagnement"]],
            )
            cur.execute(
                "UPDATE dim_accompagnement SET accomp_juridique=%s, accomp_psychique=%s, "
                "accomp_suppression=%s WHERE accomp_id=%s",
                (bool(row["accomp_juridique"]), bool(row["accomp_psychique"]),
                 bool(row["accomp_suppression"]), accomp_id),
            )

            cur.execute(
                """
                INSERT INTO faits_signalements
                    (signalement_id, date_id, genre_id, age_id, plateforme_id,
                     type_id, accomp_id, anonymat, langue, nb_signalements)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 1)
                ON CONFLICT (signalement_id) DO NOTHING
                """,
                (int(row["id"]), date_id, genre_id, age_id, plateforme_id,
                 type_id, accomp_id, row["anonymat"], row["langue"]),
            )
            if cur.rowcount == 1:
                nb_inserees += 1
            else:
                nb_ignorees += 1

        cur.execute(
            "INSERT INTO log_imports (fichier_source, fichier_hash, nb_lignes_lues, "
            "nb_lignes_valides, nb_lignes_inserees, nb_lignes_ignorees, nb_lignes_rejetees, statut) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (fichier_source, fichier_hash, nb_lignes_lues, len(df_valid),
             nb_inserees, nb_ignorees, nb_lignes_rejetees, "succes"),
        )

        conn.commit()
        logger.info(f"Chargement réussi : {nb_inserees} insérées, {nb_ignorees} déjà présentes.")

    except Exception as e:
        conn.rollback()
        logger.error(f"Échec du chargement, rollback effectué. Raison : {e}")
        try:
            cur.execute(
                "INSERT INTO log_imports (fichier_source, fichier_hash, nb_lignes_lues, "
                "nb_lignes_valides, nb_lignes_inserees, nb_lignes_ignorees, nb_lignes_rejetees, "
                "statut, message_erreur) VALUES (%s, %s, %s, 0, 0, 0, %s, %s, %s)",
                (fichier_source, fichier_hash, nb_lignes_lues, nb_lignes_rejetees, "echec", str(e)),
            )
            conn.commit()
        except Exception:
            conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()

    return {"lues": nb_lignes_lues, "inserees": nb_inserees, "ignorees": nb_ignorees,
            "rejetees": nb_lignes_rejetees}
