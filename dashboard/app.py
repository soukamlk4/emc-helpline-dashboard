"""
Dashboard EMC Helpline — Jalon 3
Tableau de bord interactif connecté au data warehouse PostgreSQL.
Sections : indicateurs clés, graphiques, insights, recommandations,
import de nouvelles données, historique des imports.
"""

import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st
import plotly.express as px

from src.gold import kpi_calculator as kpi
from src.gold.insights import generer_insights, generer_recommandations
from src.ingestion.file_ingestion import ingest_file


def _mettre_en_evidence(texte: str, couleur: str) -> str:
    """Convertit le **gras** markdown en <span> coloré pour un rendu type BI."""
    return re.sub(
        rf'\*\*(.+?)\*\*',
        rf'<span style="color:{couleur}; font-weight:700;">\1</span>',
        texte,
    )


def rendre_cartes_insights(lignes: list[str], palette: list[str]) -> str:
    cartes = []
    for i, ligne in enumerate(lignes):
        couleur = palette[i % len(palette)]
        texte = _mettre_en_evidence(ligne, couleur)
        carte = (
            f'<div style="display:flex;align-items:flex-start;gap:14px;background:#FFFFFF;'
            f'border:1px solid #E2E8F0;border-left:4px solid {couleur};border-radius:10px;'
            f'padding:14px 16px;margin-bottom:10px;box-shadow:0 1px 3px rgba(15,23,42,0.06);">'
            f'<div style="min-width:30px;height:30px;border-radius:50%;background:{couleur}22;'
            f'color:{couleur};font-weight:700;font-size:13px;display:flex;align-items:center;'
            f'justify-content:center;flex-shrink:0;">{i + 1:02d}</div>'
            f'<div style="font-size:14.5px;color:#1E293B;line-height:1.55;padding-top:2px;">{texte}</div>'
            f'</div>'
        )
        cartes.append(carte)
    return '<div style="display:flex;flex-direction:column;">' + "".join(cartes) + '</div>'


def rendre_cartes_recommandations(lignes: list[str], palette: list[str]) -> str:
    cartes = []
    for i, ligne in enumerate(lignes):
        couleur = palette[i % len(palette)]
        texte = _mettre_en_evidence(ligne, couleur)
        carte = (
            f'<div style="background:{couleur}0F;border:1px solid {couleur}40;border-radius:10px;'
            f'padding:14px 16px;margin-bottom:10px;">'
            f'<span style="display:inline-block;background:{couleur};color:#FFFFFF;font-size:10.5px;'
            f'font-weight:700;letter-spacing:0.6px;padding:3px 9px;border-radius:5px;'
            f'margin-bottom:8px;">ACTION {i + 1:02d}</span>'
            f'<div style="font-size:14.5px;color:#1E293B;line-height:1.55;margin-top:8px;">{texte}</div>'
            f'</div>'
        )
        cartes.append(carte)
    return '<div style="display:flex;flex-direction:column;">' + "".join(cartes) + '</div>'


st.set_page_config(page_title="EMC Helpline — Tableau de bord", layout="wide")

# ================================================================
# PALETTE & STYLE
# ================================================================
# Palette de couleurs cohérente pour tout le dashboard (évite le "tout bleu")
PALETTE = ["#2563EB", "#F97316", "#10B981", "#EF4444", "#8B5CF6", "#F59E0B", "#06B6D4", "#EC4899"]
PALETTE_DIVERGENTE = ["#2563EB", "#F97316"]

st.markdown(
    """
    <style>
    .block-container { padding-top: 2rem; padding-bottom: 3rem; }

    div[data-testid="stMetric"] {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 16px 18px;
    }
    div[data-testid="stMetricLabel"] { font-weight: 600; color: #475569; }
    div[data-testid="stMetricValue"] {
        color: #0F172A;
        overflow: hidden;
        white-space: nowrap;
        text-overflow: ellipsis;
        font-size: 1.7rem;
    }

    h1 { font-weight: 700; color: #0F172A; }
    h2, h3 { color: #1E293B; }

    section[data-testid="stSidebar"] { background-color: #F8FAFC; }

    hr { margin-top: 1.2rem; margin-bottom: 1.2rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Tableau de bord décisionnel — EMC Helpline")
st.caption(
    "Les résultats affichés décrivent l'échantillon de données transmis, "
    "et non nécessairement l'ensemble des signalements EMC Helpline 2025."
)

page = st.sidebar.radio(
    "Navigation",
    ["Tableau de bord", "Importer des données", "Historique des imports"],
)

# ================================================================
# PAGE : TABLEAU DE BORD
# ================================================================
if page == "Tableau de bord":

    total_global = kpi.total_signalements()
    if total_global == 0:
        st.warning("Aucune donnée en base pour le moment. Importez un fichier depuis l'onglet « Importer des données ».")
        st.stop()

    # ------------------------------------------------------------
    # FILTRES
    # ------------------------------------------------------------
    st.sidebar.header("Filtres")

    plateformes_disponibles = kpi.liste_plateformes()
    plateformes_choisies = st.sidebar.multiselect(
        "Plateforme", options=plateformes_disponibles, default=plateformes_disponibles
    )

    types_disponibles = kpi.liste_types_cyberviolence()
    types_choisis = st.sidebar.multiselect(
        "Type de cyberviolence (optionnel)", options=types_disponibles, default=[]
    )

    date_min, date_max = kpi.bornes_dates()
    date_debut, date_fin = st.sidebar.date_input(
        "Période", value=(date_min, date_max), min_value=date_min, max_value=date_max
    )

    if date_debut > date_fin:
        st.sidebar.error("La date de début doit être antérieure à la date de fin.")
        st.stop()

    filtres = {
        "date_debut": date_debut,
        "date_fin": date_fin,
        "plateforme": plateformes_choisies if plateformes_choisies else None,
        "type_cyberviolence": types_choisis if types_choisis else None,
    }
    # kpi4 et kpi6b n'acceptent pas le filtre type_cyberviolence (il n'aurait
    # pas de sens de filtrer la typologie par elle-même) -> filtres réduits
    filtres_sans_type = {k: v for k, v in filtres.items() if k != "type_cyberviolence"}

    total = kpi.total_signalements(**filtres)

    if not plateformes_choisies:
        st.info("Aucune plateforme sélectionnée — sélectionnez au moins une plateforme dans le filtre.")
        st.stop()

    if total == 0:
        st.warning("Aucune donnée ne correspond à cette sélection de filtres.")
        st.stop()

    # ------------------------------------------------------------
    # KPI CARDS
    # ------------------------------------------------------------
    df_genre = kpi.kpi2_repartition_genre(**filtres)
    df_age = kpi.kpi3_repartition_age(**filtres)
    df_type = kpi.kpi4_typologie(**filtres_sans_type)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total signalements", total)

    pct_feminin = df_genre.loc[df_genre["genre"] == "Féminin", "pct"].values
    col2.metric("Part Féminin", f"{pct_feminin[0]}%" if len(pct_feminin) else "—")

    # Tranche d'âge dominante (répartition brute uniquement, sans
    # agrégation Mineur/Jeune adulte/Adulte)
    if len(df_age):
        top_age = df_age.iloc[0]
        col3.metric("Tranche d'âge dominante", top_age["tranche_age"], f"{top_age['pct']}%")
    else:
        col3.metric("Tranche d'âge dominante", "—")

    # Type dominant : si "Autres" arrive en tête, on affiche plutôt le
    # type connu le plus fréquent (plus informatif pour la décision)
    CATEGORIE_NON_PRECISEE = "Autres"
    if len(df_type):
        top_type_row = df_type.iloc[0]
        if top_type_row["type_cyberviolence"].strip() == CATEGORIE_NON_PRECISEE:
            df_connus = df_type[df_type["type_cyberviolence"].str.strip() != CATEGORIE_NON_PRECISEE]
            if len(df_connus):
                top_type = f"{df_connus.iloc[0]['type_cyberviolence']} *"
            else:
                top_type = "Autres"
        else:
            top_type = top_type_row["type_cyberviolence"]
    else:
        top_type = "—"
    col4.metric("Type dominant", top_type if len(str(top_type)) < 22 else str(top_type)[:20] + "…")
    if len(df_type) and df_type.iloc[0]["type_cyberviolence"].strip() == CATEGORIE_NON_PRECISEE:
        col4.caption(f"* hors « Autres » ({df_type.iloc[0]['pct']}% du total, non précisé)")

    st.divider()

    # ------------------------------------------------------------
    # TENDANCE TEMPORELLE
    # ------------------------------------------------------------
    st.subheader("Évolution mensuelle du nombre de signalements")
    df_volume = kpi.kpi1_volume_mensuel(**filtres_sans_type)
    if len(df_volume):
        df_volume["periode"] = df_volume["annee"].astype(str) + "-" + df_volume["mois"].astype(str).str.zfill(2)
        fig1 = px.area(
            df_volume, x="periode", y="nb_signalements", markers=True,
            color_discrete_sequence=[PALETTE[0]],
        )
        fig1.update_traces(line=dict(width=3), fillcolor="rgba(37, 99, 235, 0.12)")
        fig1.update_layout(hovermode="x unified", margin=dict(t=10, b=10))
        st.plotly_chart(fig1, use_container_width=True)

    st.divider()

    # ------------------------------------------------------------
    # PROFIL DES VICTIMES
    # ------------------------------------------------------------
    st.subheader("Profil des personnes concernées")
    c1, c2 = st.columns(2)
    with c1:
        st.caption("Répartition par genre")
        fig2 = px.bar(
            df_genre, x="genre", y="nb", text="pct", color="genre",
            color_discrete_sequence=PALETTE,
        )
        fig2.update_traces(texttemplate="%{text}%", textposition="outside")
        fig2.update_layout(showlegend=False, margin=dict(t=10, b=10))
        st.plotly_chart(fig2, use_container_width=True)
    with c2:
        st.caption("Répartition par tranche d'âge")
        fig3 = px.bar(
            df_age, x="tranche_age", y="nb", text="pct", color="tranche_age",
            color_discrete_sequence=PALETTE,
        )
        fig3.update_traces(texttemplate="%{text}%", textposition="outside")
        fig3.update_layout(showlegend=False, margin=dict(t=10, b=10))
        st.plotly_chart(fig3, use_container_width=True)

    st.divider()

    # ------------------------------------------------------------
    # NATURE DES SIGNALEMENTS
    # ------------------------------------------------------------
    st.subheader("Typologie des cyberviolences")
    fig4 = px.bar(
        df_type, x="nb", y="type_cyberviolence", orientation="h",
        color="type_cyberviolence", color_discrete_sequence=PALETTE,
    )
    fig4.update_yaxes(categoryorder="total ascending")
    fig4.update_layout(showlegend=False, margin=dict(t=10, b=10))
    st.plotly_chart(fig4, use_container_width=True)

    st.divider()

    # ------------------------------------------------------------
    # CANAUX & LANGUE
    # ------------------------------------------------------------
    st.subheader("Canaux et langues utilisés")
    c3, c4 = st.columns(2)
    with c3:
        st.caption("Répartition par plateforme")
        df_plat = kpi.kpi5_plateforme(**filtres_sans_type)
        fig5 = px.bar(
            df_plat, x="plateforme", y="nb", text="pct", color="plateforme",
            color_discrete_sequence=PALETTE,
        )
        fig5.update_traces(texttemplate="%{text}%", textposition="outside")
        fig5.update_layout(showlegend=False, margin=dict(t=10, b=10))
        st.plotly_chart(fig5, use_container_width=True)
    with c4:
        st.caption("Répartition par langue")
        df_langue = kpi.kpi8_langue(**filtres_sans_type)
        fig8 = px.bar(
            df_langue, x="langue", y="nb", text="pct", color="langue",
            color_discrete_sequence=PALETTE,
        )
        fig8.update_traces(texttemplate="%{text}%", textposition="outside")
        fig8.update_layout(showlegend=False, margin=dict(t=10, b=10))
        st.plotly_chart(fig8, use_container_width=True)

    st.divider()

    # ------------------------------------------------------------
    # PRISE EN CHARGE
    # ------------------------------------------------------------
    st.subheader("Prise en charge des signalements")
    c5, c6 = st.columns(2)
    with c5:
        st.caption("Taux d'accompagnement")
        df_accomp = kpi.kpi6_accompagnement(**filtres_sans_type)
        fig6 = px.pie(
            df_accomp, names="accompagnement", values="nb", hole=0.5,
            color_discrete_sequence=PALETTE_DIVERGENTE,
        )
        fig6.update_traces(textinfo="percent+label")
        fig6.update_layout(margin=dict(t=10, b=10))
        st.plotly_chart(fig6, use_container_width=True)
    with c6:
        st.caption("Taux d'anonymat")
        df_anonymat = kpi.kpi7_anonymat(**filtres_sans_type)
        fig7 = px.pie(
            df_anonymat, names="anonymat", values="nb", hole=0.5,
            color_discrete_sequence=[PALETTE[4], PALETTE[2]],
        )
        fig7.update_traces(textinfo="percent+label")
        fig7.update_layout(margin=dict(t=10, b=10))
        st.plotly_chart(fig7, use_container_width=True)

    st.divider()

    # ------------------------------------------------------------
    # INSIGHTS & RECOMMANDATIONS
    # ------------------------------------------------------------
    ci, cr = st.columns(2)
    with ci:
        st.subheader("Insights")
        insights = generer_insights(**filtres_sans_type)
        st.markdown(rendre_cartes_insights(insights, PALETTE), unsafe_allow_html=True)
    with cr:
        st.subheader("Pistes de recommandations")
        recos = generer_recommandations(**filtres_sans_type)
        if recos:
            st.markdown(rendre_cartes_recommandations(recos, PALETTE), unsafe_allow_html=True)
        else:
            st.markdown(
                '<div style="background:#F8FAFC;border:1px dashed #CBD5E1;border-radius:10px;'
                'padding:18px;text-align:center;color:#64748B;font-size:14px;">'
                "Aucun seuil d'alerte franchi sur la sélection actuelle.</div>",
                unsafe_allow_html=True,
            )

# ================================================================
# PAGE : IMPORTER DES DONNÉES
# ================================================================
elif page == "Importer des données":
    st.subheader("Importer un nouveau fichier de signalements")
    st.write(
        "Le fichier sera nettoyé, validé, puis ajouté au data warehouse. "
        "Les lignes déjà présentes ne sont jamais dupliquées."
    )

    fichier_uploade = st.file_uploader("Choisir un fichier Excel (.xlsx)", type=["xlsx"])

    if fichier_uploade is not None and st.button("Importer"):
        with st.spinner("Import en cours..."):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
                tmp.write(fichier_uploade.getvalue())
                chemin_temporaire = tmp.name

            resultat = ingest_file(chemin_temporaire, deplacer_vers_bronze=True)

        if resultat.deja_importe:
            st.warning(resultat.message)
        elif resultat.succes:
            st.success(resultat.message)
            st.write(
                f"Lignes lues : {resultat.lues} · valides : {resultat.valides} · "
                f"insérées : {resultat.inserees} · déjà présentes : {resultat.ignorees} · "
                f"rejetées : {resultat.rejetees}"
            )
            st.info("Retournez sur l'onglet « Tableau de bord » pour voir les KPI actualisés.")
        else:
            st.error(resultat.message)

# ================================================================
# PAGE : HISTORIQUE DES IMPORTS
# ================================================================
elif page == "Historique des imports":
    st.subheader("Historique des imports")
    df_historique = kpi.historique_imports()
    if len(df_historique) == 0:
        st.info("Aucun import enregistré pour le moment.")
    else:
        st.dataframe(df_historique, use_container_width=True)
