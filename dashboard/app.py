"""
Dashboard EMC Helpline — Jalon 3
Tableau de bord interactif connecté au data warehouse PostgreSQL.
Sections : indicateurs clés, graphiques, import de nouvelles données,
historique des imports.
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

from src.gold import kpi_calculator as kpi
from src.ingestion.file_ingestion import ingest_file


st.set_page_config(
    page_title="EMC Helpline — Tableau de bord",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ================================================================
# DESIGN TOKENS
# ================================================================
# Palette resserrée : un bleu "signature" pour les indicateurs neutres,
# un accent par famille de sens (alerte, positif, secondaire). On évite
# le rainbow-per-category sur les graphiques qui n'en ont pas besoin.
BLUE = "#2563EB"
BLUE_SOFT = "rgba(37, 99, 235, 0.14)"
ORANGE = "#F97316"
GREEN = "#10B981"
RED = "#EF4444"
PURPLE = "#8B5CF6"
SLATE = "#64748B"

# Palette catégorielle, réservée aux graphiques où chaque couleur porte
# une vraie information (typologie, plateforme) — pas utilisée sur les
# graphiques à 2-3 barres où une seule teinte suffit.
CATEGORICAL = [BLUE, ORANGE, GREEN, PURPLE, "#06B6D4", "#F59E0B", "#EC4899", RED]
DIVERGENT = [BLUE, ORANGE]

PLOTLY_TEMPLATE = go.layout.Template(
    layout=go.Layout(
        font=dict(family="Inter, -apple-system, sans-serif", size=13, color="#334155"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=24, b=24, l=8, r=8),
        xaxis=dict(showgrid=False, zeroline=False, linecolor="#E2E8F0"),
        yaxis=dict(showgrid=True, gridcolor="#F1F5F9", zeroline=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                    font=dict(size=12)),
        hoverlabel=dict(bgcolor="white", font_size=13, bordercolor="#E2E8F0"),
    )
)


def styled(fig, height=340, show_legend=False):
    """Applique le thème commun à toutes les figures Plotly du dashboard."""
    fig.update_layout(template=PLOTLY_TEMPLATE, height=height, showlegend=show_legend)
    return fig


# ================================================================
# CSS
# ================================================================
st.markdown(
    """
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
    html, body, [class*="css"] { font-family: 'Inter', -apple-system, sans-serif; }

    .block-container { padding-top: 1.6rem; padding-bottom: 3rem; max-width: 1300px; }

    /* ---- En-tête ---- */
    .emc-header { display:flex; align-items:center; gap:14px; margin-bottom:2px; }
    .emc-badge {
        background:#EFF6FF; color:#1D4ED8; font-weight:700; font-size:.72rem;
        padding:4px 10px; border-radius:999px; letter-spacing:.04em; text-transform:uppercase;
        border:1px solid #DBEAFE;
    }
    h1 { font-weight:800 !important; color:#0F172A !important; font-size:1.85rem !important; letter-spacing:-0.02em; }
    .emc-caption { color:#64748B; font-size:.92rem; margin-top:-6px; margin-bottom:1.2rem; }

    /* ---- Sidebar ---- */
    section[data-testid="stSidebar"] {
        background:#0F172A;
    }
    section[data-testid="stSidebar"] * { color:#E2E8F0 !important; }
    section[data-testid="stSidebar"] h1, section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3 { color:#F8FAFC !important; font-weight:700 !important; }
    section[data-testid="stSidebar"] .stRadio label { padding:2px 0; }
    section[data-testid="stSidebar"] hr { border-color:#1E293B; }

    /* ---- Cartes KPI custom (remplacent st.metric, pas de troncature) ---- */
    .kpi-card {
        background:#FFFFFF; border:1px solid #E2E8F0; border-radius:14px;
        padding:18px 20px; box-shadow:0 1px 2px rgba(15,23,42,0.04);
        height:108px; display:flex; flex-direction:column; justify-content:center;
    }
    .kpi-label {
        font-size:.76rem; font-weight:600; color:#64748B; text-transform:uppercase;
        letter-spacing:.03em; margin-bottom:6px;
    }
    .kpi-value { font-size:1.55rem; font-weight:800; color:#0F172A; line-height:1.15; }
    .kpi-delta { font-size:.78rem; font-weight:600; margin-top:4px; }
    .kpi-delta.up { color:#059669; }
    .kpi-delta.note { color:#94A3B8; font-weight:500; }

    /* ---- Sections ---- */
    .section-eyebrow {
        font-size:.72rem; font-weight:700; color:#2563EB; text-transform:uppercase;
        letter-spacing:.06em; margin-bottom:2px;
    }
    .section-title { font-size:1.15rem; font-weight:700; color:#0F172A; margin-bottom:14px; }
    .chart-caption { font-size:.82rem; font-weight:600; color:#475569; margin-bottom:2px; }

    /* ---- Tabs ---- */
    .stTabs [data-baseweb="tab-list"] { gap:4px; border-bottom:1px solid #E2E8F0; }
    .stTabs [data-baseweb="tab"] {
        height:38px; border-radius:8px 8px 0 0; padding:0 16px; font-weight:600; color:#64748B;
    }
    .stTabs [aria-selected="true"] { color:#2563EB !important; background:#EFF6FF; }

    /* ---- Boutons / inputs ---- */
    .stButton>button {
        background:#2563EB; color:white; border-radius:8px; font-weight:600; border:none;
        padding:.5rem 1.3rem;
    }
    .stButton>button:hover { background:#1D4ED8; }

    hr { margin-top:.8rem; margin-bottom:1.4rem; border-color:#EEF2F6; }
    </style>
    """,
    unsafe_allow_html=True,
)


def kpi_card(col, label, value, delta=None, note=None):
    """Carte KPI HTML — largeur pleine, pas de troncature de texte."""
    delta_html = ""
    if delta:
        delta_html = f'<div class="kpi-delta up">↑ {delta}</div>'
    elif note:
        delta_html = f'<div class="kpi-delta note">{note}</div>'
    col.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
            {delta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_header(eyebrow, title):
    st.markdown(
        f'<div class="section-eyebrow">{eyebrow}</div><div class="section-title">{title}</div>',
        unsafe_allow_html=True,
    )


# ================================================================
# EN-TÊTE
# ================================================================
st.markdown(
    '<div class="emc-header"><span style="font-size:1.6rem;">🛡️</span>'
    '<h1>Tableau de bord décisionnel — EMC Helpline</h1>'
    '<span class="emc-badge">Signalements 2025</span></div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="emc-caption">Les résultats affichés décrivent l\'échantillon de données '
    'transmis, et non nécessairement l\'ensemble des signalements EMC Helpline 2025.</div>',
    unsafe_allow_html=True,
)

st.sidebar.markdown("### 🛡️ EMC Helpline")
page = st.sidebar.radio(
    "Navigation",
    ["Tableau de bord", "Importer des données", "Historique des imports"],
    label_visibility="collapsed",
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
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Filtres")

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
    kpi_card(col1, "Total signalements", total)

    pct_feminin = df_genre.loc[df_genre["genre"] == "Féminin", "pct"].values
    kpi_card(col2, "Part Féminin", f"{pct_feminin[0]}%" if len(pct_feminin) else "—")

    if len(df_age):
        top_age = df_age.iloc[0]
        kpi_card(col3, "Tranche d'âge dominante", top_age["tranche_age"], delta=f"{top_age['pct']}%")
    else:
        kpi_card(col3, "Tranche d'âge dominante", "—")

    CATEGORIE_NON_PRECISEE = "Autres"
    note_type = None
    if len(df_type):
        top_type_row = df_type.iloc[0]
        if top_type_row["type_cyberviolence"].strip() == CATEGORIE_NON_PRECISEE:
            df_connus = df_type[df_type["type_cyberviolence"].str.strip() != CATEGORIE_NON_PRECISEE]
            if len(df_connus):
                top_type = df_connus.iloc[0]["type_cyberviolence"]
                note_type = f"hors « Autres » ({top_type_row['pct']}% du total, non précisé)"
            else:
                top_type = "Autres"
        else:
            top_type = top_type_row["type_cyberviolence"]
    else:
        top_type = "—"
    kpi_card(col4, "Type dominant", top_type, note=note_type)

    st.write("")
    st.write("")

    # ------------------------------------------------------------
    # ONGLETS
    # ------------------------------------------------------------
    tab_vue, tab_profil, tab_canaux, tab_prise_en_charge = st.tabs(
        ["📈 Vue d'ensemble", "👥 Profil des victimes", "🌐 Canaux & typologie", "🤝 Prise en charge"]
    )

    # ---- Vue d'ensemble : évolution temporelle ----
    with tab_vue:
        section_header("Tendance", "Évolution mensuelle du nombre de signalements")
        df_volume = kpi.kpi1_volume_mensuel(**filtres_sans_type)
        if len(df_volume):
            df_volume["periode"] = df_volume["annee"].astype(str) + "-" + df_volume["mois"].astype(str).str.zfill(2)
            fig1 = px.area(
                df_volume, x="periode", y="nb_signalements", markers=True,
                color_discrete_sequence=[BLUE],
            )
            fig1.update_traces(line=dict(width=3), fillcolor=BLUE_SOFT,
                                marker=dict(size=7, line=dict(width=2, color="white")))
            fig1.update_layout(hovermode="x unified", yaxis_title="Signalements", xaxis_title="")
            st.plotly_chart(styled(fig1, height=380), use_container_width=True)
        else:
            st.info("Pas de données pour la période sélectionnée.")

    # ---- Profil des victimes : genre + âge ----
    with tab_profil:
        section_header("Démographie", "Répartition des signalements selon le genre et la tranche d'âge")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown('<div class="chart-caption">Par genre</div>', unsafe_allow_html=True)
            fig2 = px.bar(df_genre, x="genre", y="nb", text="pct", color_discrete_sequence=[BLUE])
            fig2.update_traces(texttemplate="%{text}%", textposition="outside", marker_color=BLUE)
            fig2.update_layout(yaxis_title="", xaxis_title="")
            st.plotly_chart(styled(fig2), use_container_width=True)
        with c2:
            st.markdown('<div class="chart-caption">Par tranche d\'âge</div>', unsafe_allow_html=True)
            fig3 = px.bar(df_age, x="tranche_age", y="nb", text="pct", color_discrete_sequence=[ORANGE])
            fig3.update_traces(texttemplate="%{text}%", textposition="outside", marker_color=ORANGE)
            fig3.update_layout(yaxis_title="", xaxis_title="")
            st.plotly_chart(styled(fig3), use_container_width=True)

    # ---- Canaux & typologie ----
    with tab_canaux:
        section_header("Nature des signalements", "Typologie des cyberviolences")
        fig4 = px.bar(
            df_type, x="nb", y="type_cyberviolence", orientation="h",
            color="type_cyberviolence", color_discrete_sequence=CATEGORICAL,
        )
        fig4.update_yaxes(categoryorder="total ascending", title="")
        fig4.update_layout(xaxis_title="Nombre de signalements")
        st.plotly_chart(styled(fig4, height=360), use_container_width=True)

        st.markdown("<br>", unsafe_allow_html=True)
        section_header("Origine", "Canaux et langues utilisés")
        c3, c4 = st.columns(2)
        with c3:
            st.markdown('<div class="chart-caption">Par plateforme</div>', unsafe_allow_html=True)
            df_plat = kpi.kpi5_plateforme(**filtres_sans_type)
            fig5 = px.bar(df_plat, x="plateforme", y="nombre", text="pct",
                           color="plateforme", color_discrete_sequence=CATEGORICAL)
            fig5.update_traces(texttemplate="%{text}%", textposition="outside")
            fig5.update_layout(yaxis_title="", xaxis_title="")
            st.plotly_chart(styled(fig5), use_container_width=True)
        with c4:
            st.markdown('<div class="chart-caption">Par langue</div>', unsafe_allow_html=True)
            df_langue = kpi.kpi8_langue(**filtres_sans_type)
            fig8 = px.bar(df_langue, x="langue", y="nombre", text="pct",
                           color_discrete_sequence=[GREEN])
            fig8.update_traces(texttemplate="%{text}%", textposition="outside", marker_color=GREEN)
            fig8.update_layout(yaxis_title="", xaxis_title="")
            st.plotly_chart(styled(fig8), use_container_width=True)

    # ---- Prise en charge ----
    with tab_prise_en_charge:
        section_header("Accompagnement", "Prise en charge des signalements")
        c5, c6, c7 = st.columns(3)
        with c5:
            st.markdown('<div class="chart-caption">Taux d\'accompagnement</div>', unsafe_allow_html=True)
            df_accomp = kpi.kpi6_accompagnement(**filtres_sans_type)
            fig6 = px.pie(df_accomp, names="accompagnement", values="nb", hole=0.6,
                           color_discrete_sequence=DIVERGENT)
            fig6.update_traces(textinfo="percent+label", textfont_size=12)
            st.plotly_chart(styled(fig6, height=300, show_legend=False), use_container_width=True)
        with c6:
            st.markdown('<div class="chart-caption">Taux d\'anonymat</div>', unsafe_allow_html=True)
            df_anonymat = kpi.kpi7_anonymat(**filtres_sans_type)
            fig7 = px.pie(df_anonymat, names="anonymat", values="nb", hole=0.6,
                           color_discrete_sequence=[PURPLE, GREEN])
            fig7.update_traces(textinfo="percent+label", textfont_size=12)
            st.plotly_chart(styled(fig7, height=300, show_legend=False), use_container_width=True)
        with c7:
            st.markdown('<div class="chart-caption">Types d\'accompagnement sollicités</div>', unsafe_allow_html=True)
            df_type_accomp = kpi.kpi6b_type_accompagnement(**filtres_sans_type)
            df_type_accomp_long = df_type_accomp[["pct_juridique", "pct_psychique", "pct_suppression"]].T
            df_type_accomp_long.columns = ["pct"]
            df_type_accomp_long.index = ["Juridique", "Psychique", "Suppression"]
            df_type_accomp_long = df_type_accomp_long.reset_index().rename(columns={"index": "type"})
            fig9 = px.bar(df_type_accomp_long, x="type", y="pct", text="pct",
                           color_discrete_sequence=[BLUE])
            fig9.update_traces(texttemplate="%{text}%", textposition="outside", marker_color=BLUE)
            fig9.update_layout(yaxis_title="%", xaxis_title="")
            st.plotly_chart(styled(fig9, height=300), use_container_width=True)

# ================================================================
# PAGE : IMPORTER DES DONNÉES
# ================================================================
elif page == "Importer des données":
    section_header("Data warehouse", "Importer un nouveau fichier de signalements")
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
            m1, m2, m3, m4, m5 = st.columns(5)
            kpi_card(m1, "Lues", resultat.lues)
            kpi_card(m2, "Valides", resultat.valides)
            kpi_card(m3, "Insérées", resultat.inserees)
            kpi_card(m4, "Déjà présentes", resultat.ignorees)
            kpi_card(m5, "Rejetées", resultat.rejetees)
            st.info("Retournez sur l'onglet « Tableau de bord » pour voir les KPI actualisés.")
        else:
            st.error(resultat.message)

# ================================================================
# PAGE : HISTORIQUE DES IMPORTS
# ================================================================
elif page == "Historique des imports":
    section_header("Traçabilité", "Historique des imports")
    df_historique = kpi.historique_imports()
    if len(df_historique) == 0:
        st.info("Aucun import enregistré pour le moment.")
    else:
        st.dataframe(df_historique, use_container_width=True, hide_index=True)
