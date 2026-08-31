"""
KPI calculator — couche Gold.
Recalcule les 8 KPI depuis PostgreSQL, avec filtres optionnels
(période, plateforme). Fournit aussi l'historique des imports pour le
dashboard.
"""

import warnings

import pandas as pd
import psycopg2

from src.utils.config import DB_CONFIG
from src.utils.logger import get_logger

logger = get_logger(__name__)
warnings.filterwarnings("ignore", message="pandas only supports SQLAlchemy")


def _query(sql: str, params: list = None) -> pd.DataFrame:
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        df = pd.read_sql_query(sql, conn, params=params or [])
    finally:
        conn.close()
    return df


def _clause_filtre(date_debut=None, date_fin=None, plateforme=None, type_cyberviolence=None):
    conditions = []
    params = []
    if date_debut:
        conditions.append("d.date_complete >= %s")
        params.append(date_debut)
    if date_fin:
        conditions.append("d.date_complete <= %s")
        params.append(date_fin)
    if plateforme:
        conditions.append("p.plateforme = ANY(%s)")
        params.append(list(plateforme))
    if type_cyberviolence:
        conditions.append("t.type_cyberviolence = ANY(%s)")
        params.append(list(type_cyberviolence))
    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    return where_sql, params


def _ajouter_pourcentage(df: pd.DataFrame, colonne_nb: str = "nb") -> pd.DataFrame:
    total = df[colonne_nb].sum()
    df["pct"] = (df[colonne_nb] / total * 100).round(1) if total > 0 else 0.0
    return df


def _base_joins(besoin_type=False):
    joins = "JOIN dim_date d ON f.date_id = d.date_id JOIN dim_plateforme p ON f.plateforme_id = p.plateforme_id"
    if besoin_type:
        joins += " JOIN dim_type_cyberviolence t ON f.type_id = t.type_id"
    return joins


def _requete_dimension(table_dim, id_col, label_cols, date_debut=None, date_fin=None,
                        plateforme=None, type_cyberviolence=None) -> pd.DataFrame:
    where_sql, params = _clause_filtre(date_debut, date_fin, plateforme, type_cyberviolence)
    besoin_type = type_cyberviolence is not None
    sql = f"""
        SELECT {label_cols}, count(*) AS nb
        FROM faits_signalements f
        JOIN {table_dim} dim ON f.{id_col} = dim.{id_col}
        {_base_joins(besoin_type)}
        {where_sql}
        GROUP BY {label_cols}
        ORDER BY nb DESC;
    """
    return _ajouter_pourcentage(_query(sql, params))


def kpi1_volume_mensuel(date_debut=None, date_fin=None, plateforme=None,
                         type_cyberviolence=None) -> pd.DataFrame:
    where_sql, params = _clause_filtre(date_debut, date_fin, plateforme, type_cyberviolence)
    besoin_type = type_cyberviolence is not None
    sql = f"""
        SELECT d.annee, d.mois, d.nom_mois, count(*) AS nb_signalements
        FROM faits_signalements f
        {_base_joins(besoin_type)}
        {where_sql}
        GROUP BY d.annee, d.mois, d.nom_mois
        ORDER BY d.annee, d.mois;
    """
    return _query(sql, params)


def kpi2_repartition_genre(date_debut=None, date_fin=None, plateforme=None,
                            type_cyberviolence=None) -> pd.DataFrame:
    return _requete_dimension("dim_genre", "genre_id", "dim.genre",
                               date_debut, date_fin, plateforme, type_cyberviolence)


def kpi3_repartition_age(date_debut=None, date_fin=None, plateforme=None,
                          type_cyberviolence=None) -> pd.DataFrame:
    return _requete_dimension("dim_age", "age_id", "dim.tranche_age, dim.statut_age",
                               date_debut, date_fin, plateforme, type_cyberviolence)


def kpi4_typologie(date_debut=None, date_fin=None, plateforme=None) -> pd.DataFrame:
    return _requete_dimension("dim_type_cyberviolence", "type_id", "dim.type_cyberviolence",
                               date_debut, date_fin, plateforme)


def kpi5_plateforme(date_debut=None, date_fin=None, plateforme=None,
                     type_cyberviolence=None) -> pd.DataFrame:
    return _requete_dimension("dim_plateforme", "plateforme_id", "dim.plateforme",
                               date_debut, date_fin, plateforme, type_cyberviolence)


def kpi6_accompagnement(date_debut=None, date_fin=None, plateforme=None,
                         type_cyberviolence=None) -> pd.DataFrame:
    return _requete_dimension("dim_accompagnement", "accomp_id", "dim.accompagnement",
                               date_debut, date_fin, plateforme, type_cyberviolence)


def kpi6b_type_accompagnement(date_debut=None, date_fin=None, plateforme=None) -> pd.DataFrame:
    where_sql, params = _clause_filtre(date_debut, date_fin, plateforme)
    sql = f"""
        SELECT
            sum(CASE WHEN ac.accomp_juridique THEN 1 ELSE 0 END) AS nb_juridique,
            sum(CASE WHEN ac.accomp_psychique THEN 1 ELSE 0 END) AS nb_psychique,
            sum(CASE WHEN ac.accomp_suppression THEN 1 ELSE 0 END) AS nb_suppression,
            count(*) AS total
        FROM faits_signalements f
        JOIN dim_accompagnement ac ON f.accomp_id = ac.accomp_id
        {_base_joins()}
        {where_sql};
    """
    df = _query(sql, params)
    total = df.loc[0, "total"]
    for col in ["nb_juridique", "nb_psychique", "nb_suppression"]:
        df[col.replace("nb_", "pct_")] = round(100.0 * df.loc[0, col] / total, 1) if total > 0 else 0.0
    return df


def kpi7_anonymat(date_debut=None, date_fin=None, plateforme=None,
                   type_cyberviolence=None) -> pd.DataFrame:
    where_sql, params = _clause_filtre(date_debut, date_fin, plateforme, type_cyberviolence)
    besoin_type = type_cyberviolence is not None
    sql = f"""
        SELECT f.anonymat, count(*) AS nb
        FROM faits_signalements f
        {_base_joins(besoin_type)}
        {where_sql}
        GROUP BY f.anonymat
        ORDER BY nb DESC;
    """
    return _ajouter_pourcentage(_query(sql, params))


def kpi8_langue(date_debut=None, date_fin=None, plateforme=None,
                 type_cyberviolence=None) -> pd.DataFrame:
    where_sql, params = _clause_filtre(date_debut, date_fin, plateforme, type_cyberviolence)
    besoin_type = type_cyberviolence is not None
    sql = f"""
        SELECT f.langue, count(*) AS nb
        FROM faits_signalements f
        {_base_joins(besoin_type)}
        {where_sql}
        GROUP BY f.langue
        ORDER BY nb DESC;
    """
    return _ajouter_pourcentage(_query(sql, params))


def liste_plateformes() -> list:
    return _query("SELECT plateforme FROM dim_plateforme ORDER BY plateforme;")["plateforme"].tolist()


def liste_types_cyberviolence() -> list:
    return _query(
        "SELECT type_cyberviolence FROM dim_type_cyberviolence ORDER BY type_cyberviolence;"
    )["type_cyberviolence"].tolist()


def bornes_dates() -> tuple:
    df = _query("SELECT min(date_complete) AS min_d, max(date_complete) AS max_d FROM dim_date;")
    return df.loc[0, "min_d"], df.loc[0, "max_d"]


def total_signalements(date_debut=None, date_fin=None, plateforme=None,
                        type_cyberviolence=None) -> int:
    where_sql, params = _clause_filtre(date_debut, date_fin, plateforme, type_cyberviolence)
    besoin_type = type_cyberviolence is not None
    sql = f"""
        SELECT count(*) AS total FROM faits_signalements f
        {_base_joins(besoin_type)}
        {where_sql};
    """
    df = _query(sql, params)
    return int(df.loc[0, "total"]) if len(df) else 0


def historique_imports() -> pd.DataFrame:
    """Utilisé par la page 'Historique des imports' du dashboard."""
    sql = """
        SELECT fichier_source, date_import, nb_lignes_lues, nb_lignes_inserees,
               nb_lignes_rejetees, statut
        FROM log_imports
        ORDER BY date_import DESC;
    """
    return _query(sql)
