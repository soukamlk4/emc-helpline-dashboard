"""
KPI calculator — couche Gold.
Version simplifiée pour Streamlit Cloud : lit les données depuis le CSV
(au lieu de PostgreSQL).
"""

import warnings
import pandas as pd
import streamlit as st
from pathlib import Path

warnings.filterwarnings("ignore", message="pandas only supports SQLAlchemy")

# ================================================================
# CHARGEMENT DES DONNÉES
# ================================================================

@st.cache_data
def load_data():
    """Charge les données depuis le fichier CSV."""
    possible_paths = [
        Path('data/silver/signalements_clean.csv'),
        Path('../data/silver/signalements_clean.csv'),
        Path('/mount/src/emc-helpline-dashboard/data/silver/signalements_clean.csv'),
        Path('emc_helpline_data_platform/data/silver/signalements_clean.csv'),
    ]
    
    for path in possible_paths:
        if path.exists():
            df = pd.read_csv(path)
            df['date'] = pd.to_datetime(df['date'])
            return df
    
    # Fallback : chercher n'importe où
    for path in Path('.').rglob('signalements_clean.csv'):
        if path.exists():
            df = pd.read_csv(path)
            df['date'] = pd.to_datetime(df['date'])
            return df
    
    st.error("❌ Fichier de données non trouvé !")
    return pd.DataFrame()

# Charger les données une fois
df_global = load_data()

# ================================================================
# FONCTIONS DE FILTRAGE
# ================================================================

def appliquer_filtres(df, filtres):
    """Applique les filtres sur le DataFrame."""
    if df is None or df.empty:
        return df
    
    df_filtre = df.copy()
    
    if 'date_debut' in filtres and filtres['date_debut']:
        df_filtre = df_filtre[df_filtre['date'] >= pd.to_datetime(filtres['date_debut'])]
    if 'date_fin' in filtres and filtres['date_fin']:
        df_filtre = df_filtre[df_filtre['date'] <= pd.to_datetime(filtres['date_fin'])]
    if 'plateforme' in filtres and filtres['plateforme']:
        df_filtre = df_filtre[df_filtre['plateforme'].isin(filtres['plateforme'])]
    if 'type_cyberviolence' in filtres and filtres['type_cyberviolence']:
        df_filtre = df_filtre[df_filtre['cyberharcelementType'].isin(filtres['type_cyberviolence'])]
    
    return df_filtre


def _ajouter_pourcentage(df, colonne_nb="nb"):
    """Ajoute une colonne de pourcentage."""
    total = df[colonne_nb].sum()
    df["pct"] = (df[colonne_nb] / total * 100).round(1) if total > 0 else 0.0
    return df


def total_signalements(**filtres):
    """Total des signalements."""
    df = appliquer_filtres(df_global, filtres)
    return len(df) if not df.empty else 0


def kpi1_volume_mensuel(**filtres):
    """KPI 1 : Évolution mensuelle."""
    df = appliquer_filtres(df_global, filtres)
    if df.empty:
        return pd.DataFrame()
    
    df['mois'] = df['date'].dt.month
    df['annee'] = df['date'].dt.year
    result = df.groupby(['annee', 'mois']).size().reset_index(name='nb_signalements')
    result['nom_mois'] = pd.to_datetime(result['mois'].astype(str) + '-01').dt.strftime('%B')
    return result.sort_values(['annee', 'mois'])


def kpi2_repartition_genre(**filtres):
    """KPI 2 : Répartition par genre."""
    df = appliquer_filtres(df_global, filtres)
    if df.empty:
        return pd.DataFrame()
    
    result = df['genre'].value_counts().reset_index()
    result.columns = ['genre', 'nb']
    return _ajouter_pourcentage(result)


def kpi3_repartition_age(**filtres):
    """KPI 3 : Répartition par tranche d'âge."""
    df = appliquer_filtres(df_global, filtres)
    if df.empty:
        return pd.DataFrame()
    
    # Nettoyer les libellés
    age_mapping = {
        'Âges de 18 à 25 ans': '18-25 ans',
        'Âges de 26 ans et plus': '+26 ans',
        'Âges de 13 à 17 ans': '13-17 ans',
        'Âges de 5 à 12 ans': '5-12 ans'
    }
    df['tranche_age'] = df['age'].replace(age_mapping).fillna('Non renseigné')
    
    result = df['tranche_age'].value_counts().reset_index()
    result.columns = ['tranche_age', 'nb']
    return _ajouter_pourcentage(result)


def kpi4_typologie(**filtres):
    """KPI 4 : Typologie des cyberviolences."""
    df = appliquer_filtres(df_global, filtres)
    if df.empty:
        return pd.DataFrame()
    
    result = df['cyberharcelementType'].value_counts().reset_index()
    result.columns = ['type_cyberviolence', 'nb']
    return _ajouter_pourcentage(result)


def kpi5_plateforme(**filtres):
    """KPI 5 : Répartition par plateforme."""
    df = appliquer_filtres(df_global, filtres)
    if df.empty:
        return pd.DataFrame()
    
    result = df['plateforme'].value_counts().reset_index()
    result.columns = ['plateforme', 'nb']
    return _ajouter_pourcentage(result)


def kpi6_accompagnement(**filtres):
    """KPI 6 : Taux d'accompagnement."""
    df = appliquer_filtres(df_global, filtres)
    if df.empty:
        return pd.DataFrame()
    
    result = df['accompagnement'].value_counts().reset_index()
    result.columns = ['accompagnement', 'nb']
    return _ajouter_pourcentage(result)


def kpi6b_type_accompagnement(**filtres):
    """KPI 6b : Détail des types d'accompagnement."""
    df = appliquer_filtres(df_global, filtres)
    if df.empty:
        return pd.DataFrame()
    
    df_accomp = df[df['accompagnement'] == 'Oui'].copy()
    if df_accomp.empty:
        return pd.DataFrame({'nb_juridique': [0], 'nb_psychique': [0], 'nb_suppression': [0], 'total': [0]})
    
    nb_juridique = df_accomp['typeAccompagnement'].str.contains('Juridique', na=False).sum()
    nb_psychique = df_accomp['typeAccompagnement'].str.contains('Psychique', na=False).sum()
    nb_suppression = df_accomp['typeAccompagnement'].str.contains('Suppression', na=False).sum()
    total = len(df_accomp)
    
    df_result = pd.DataFrame({
        'nb_juridique': [nb_juridique],
        'nb_psychique': [nb_psychique],
        'nb_suppression': [nb_suppression],
        'total': [total]
    })
    
    for col in ['nb_juridique', 'nb_psychique', 'nb_suppression']:
        df_result[col.replace('nb_', 'pct_')] = round(100.0 * df_result.loc[0, col] / total, 1) if total > 0 else 0.0
    
    return df_result


def kpi7_anonymat(**filtres):
    """KPI 7 : Taux d'anonymat."""
    df = appliquer_filtres(df_global, filtres)
    if df.empty:
        return pd.DataFrame()
    
    result = df['anonymat'].value_counts().reset_index()
    result.columns = ['anonymat', 'nb']
    return _ajouter_pourcentage(result)


def kpi8_langue(**filtres):
    """KPI 8 : Répartition par langue."""
    df = appliquer_filtres(df_global, filtres)
    if df.empty:
        return pd.DataFrame()
    
    result = df['langue'].value_counts().reset_index()
    result.columns = ['langue', 'nb']
    return _ajouter_pourcentage(result)


def liste_plateformes():
    """Retourne la liste des plateformes disponibles."""
    if df_global.empty:
        return []
    return df_global['plateforme'].dropna().unique().tolist()


def liste_types_cyberviolence():
    """Retourne la liste des types de cyberviolence disponibles."""
    if df_global.empty:
        return []
    return df_global['cyberharcelementType'].dropna().unique().tolist()


def bornes_dates():
    """Retourne les dates min et max."""
    if df_global.empty:
        return pd.Timestamp('2025-01-01').date(), pd.Timestamp('2025-12-31').date()
    return df_global['date'].min().date(), df_global['date'].max().date()


def historique_imports():
    """Retourne un DataFrame vide (pas d'historique sans PostgreSQL)."""
    return pd.DataFrame(columns=['fichier_source', 'date_import', 'nb_lignes_lues', 
                                 'nb_lignes_inserees', 'nb_lignes_rejetees', 'statut'])
