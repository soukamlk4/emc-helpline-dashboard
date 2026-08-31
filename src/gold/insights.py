"""
Insights & recommandations — couche Gold.
Génère des observations et pistes de recommandation à partir des KPI
réellement calculés, selon des règles analytiques simples (pas de LLM,
pas d'inférence statistique complexe). Chaque phrase est directement
dérivée d'un chiffre du data warehouse ; rien n'est inventé.

Ne s'appuie que sur la répartition par tranche d'âge brute (kpi3), sans
agrégation Mineur/Jeune adulte/Adulte, sur demande de l'encadrante.
"""

from src.gold import kpi_calculator as kpi

CATEGORIE_NON_PRECISEE = "Autres"


def _type_dominant_connu(df_type):
    """Retourne la ligne du type de cyberviolence le plus fréquent en
    excluant la catégorie 'Autres', qui ne renseigne pas sur la nature
    réelle de l'abus. Retourne None si aucun type connu n'est présent."""
    df_connus = df_type[df_type["type_cyberviolence"].str.strip() != CATEGORIE_NON_PRECISEE]
    if len(df_connus) == 0:
        return None
    return df_connus.iloc[0]


def generer_insights(date_debut=None, date_fin=None, plateforme=None) -> list:
    """Retourne une liste de phrases d'observation, ou une liste vide si
    aucune donnée ne correspond aux filtres (pas d'insight fabriqué)."""
    filtres = {"date_debut": date_debut, "date_fin": date_fin, "plateforme": plateforme}
    total = kpi.total_signalements(**filtres)
    if total == 0:
        return []

    insights = []

    df_type = kpi.kpi4_typologie(**filtres)
    if len(df_type):
        top = df_type.iloc[0]
        if top["type_cyberviolence"].strip() == CATEGORIE_NON_PRECISEE:
            insights.append(
                f"**{top['pct']}%** des signalements sont classés « Autres » (catégorie non "
                f"précisée), ce qui limite l'analyse fine de la typologie dominante."
            )
            type_connu = _type_dominant_connu(df_type)
            if type_connu is not None:
                insights.append(
                    f"Parmi les types de cyberviolence précisés, le plus représenté est "
                    f"**{type_connu['type_cyberviolence']}** ({type_connu['pct']}% des signalements)."
                )
        else:
            insights.append(
                f"Le type de cyberviolence le plus représenté est **{top['type_cyberviolence']}** "
                f"({top['pct']}% des signalements)."
            )

    df_plateforme = kpi.kpi5_plateforme(**filtres)
    if len(df_plateforme):
        top = df_plateforme.iloc[0]
        insights.append(
            f"La plateforme la plus représentée est **{top['plateforme']}** ({top['pct']}%)."
        )

    df_genre = kpi.kpi2_repartition_genre(**filtres)
    if len(df_genre):
        top = df_genre.iloc[0]
        insights.append(
            f"Les signalements concernent majoritairement le genre **{top['genre']}** ({top['pct']}%)."
        )

    df_volume = kpi.kpi1_volume_mensuel(**filtres)
    if len(df_volume):
        pic = df_volume.loc[df_volume["nb_signalements"].idxmax()]
        insights.append(
            f"La période présentant le plus de signalements est **{pic['nom_mois']} {pic['annee']}** "
            f"({int(pic['nb_signalements'])} signalements)."
        )

    df_age = kpi.kpi3_repartition_age(**filtres)
    if len(df_age):
        top_age = df_age.iloc[0]
        insights.append(
            f"La tranche d'âge la plus représentée est **{top_age['tranche_age']}** "
            f"({top_age['pct']}% des signalements)."
        )

    return insights


def generer_recommandations(date_debut=None, date_fin=None, plateforme=None) -> list:
    """Règles simples : si un indicateur dépasse un seuil, une piste de
    recommandation est proposée. Toujours présenté comme une piste
    d'action issue des données, jamais comme une décision automatique."""
    filtres = {"date_debut": date_debut, "date_fin": date_fin, "plateforme": plateforme}
    total = kpi.total_signalements(**filtres)
    if total == 0:
        return []

    recommandations = []

    SEUIL_PLATEFORME_DOMINANTE = 40.0
    df_plateforme = kpi.kpi5_plateforme(**filtres)
    if len(df_plateforme) and df_plateforme.iloc[0]["pct"] >= SEUIL_PLATEFORME_DOMINANTE:
        top = df_plateforme.iloc[0]
        recommandations.append(
            f"**{top['plateforme']}** concentre {top['pct']}% des signalements → "
            f"renforcer la sensibilisation et le suivi sur cette plateforme."
        )

    # La recommandation sur la typologie s'appuie sur le type dominant CONNU
    # (hors "Autres"), pour rester actionnable : on ne peut pas prioriser
    # une action de prévention sur une catégorie non précisée.
    SEUIL_TYPOLOGIE_DOMINANTE = 25.0
    df_type = kpi.kpi4_typologie(**filtres)
    type_connu = _type_dominant_connu(df_type) if len(df_type) else None
    if type_connu is not None and type_connu["pct"] >= SEUIL_TYPOLOGIE_DOMINANTE:
        recommandations.append(
            f"**{type_connu['type_cyberviolence']}** est la typologie connue la plus fréquente "
            f"({type_connu['pct']}%) → accorder une attention particulière à ce type d'abus "
            f"dans les actions de prévention."
        )

    SEUIL_AUTRES_ELEVE = 30.0
    if len(df_type):
        ligne_autres = df_type[df_type["type_cyberviolence"].str.strip() == CATEGORIE_NON_PRECISEE]
        pct_autres = ligne_autres["pct"].iloc[0] if len(ligne_autres) else 0.0
        if pct_autres >= SEUIL_AUTRES_ELEVE:
            recommandations.append(
                f"{pct_autres}% des signalements sont classés « Autres » → "
                f"envisager d'affiner les catégories du formulaire de signalement pour mieux "
                f"qualifier ces cas."
            )

    SEUIL_ACCOMPAGNEMENT_FAIBLE = 20.0
    df_accomp = kpi.kpi6_accompagnement(**filtres)
    if len(df_accomp):
        ligne_oui = df_accomp[df_accomp["accompagnement"] == "Oui"]
        pct_oui = ligne_oui["pct"].iloc[0] if len(ligne_oui) else 0.0
        if pct_oui < SEUIL_ACCOMPAGNEMENT_FAIBLE:
            recommandations.append(
                f"Seuls {pct_oui}% des signalements s'accompagnent d'une demande d'aide juridique/"
                f"psychologique → envisager de mieux faire connaître ce service aux victimes."
            )

    return recommandations