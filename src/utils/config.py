"""
Configuration centralisée du pipeline ETL EMC Helpline.

Lit les paramètres sensibles depuis le fichier .env situé à la racine du
projet — jamais en dur dans le code. Le chemin du .env est calculé à partir
de l'emplacement de ce fichier (pas du dossier depuis lequel on lance un
script), pour que ça fonctionne peu importe d'où le pipeline est exécuté
(racine du projet, dossier src/, etc.).
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# src/utils/config.py -> remonte de 2 niveaux -> racine du projet
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / ".env"

# Détecter si on est sur Streamlit Cloud
IS_CLOUD = os.environ.get('IS_STREAMLIT_CLOUD', 'false').lower() == 'true'

# Si on est sur le cloud, on ignore le .env (ou on le crée s'il n'existe pas)
if IS_CLOUD:
    # Créer un .env factice si nécessaire
    if not ENV_PATH.exists():
        ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(ENV_PATH, 'w') as f:
            f.write("DB_HOST=localhost\nDB_PORT=5432\nDB_NAME=emc_helpline\nDB_USER=postgres\nDB_PASSWORD=dummy")
    
    # Charger les variables d'environnement (ou utiliser des valeurs par défaut)
    load_dotenv(dotenv_path=ENV_PATH)
else:
    if not ENV_PATH.exists():
        raise FileNotFoundError(
            f"Fichier .env introuvable à {ENV_PATH}. "
            f"Copie .env.example en .env à la racine du projet et remplis tes identifiants."
        )
    load_dotenv(dotenv_path=ENV_PATH)

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 5432)),
    "dbname": os.getenv("DB_NAME", "emc_helpline"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "soukaina2004"),
}

if IS_CLOUD:
    # Sur le cloud, PostgreSQL n'est pas utilisé - on désactive la vérification
    pass
elif not DB_CONFIG["password"]:
    raise RuntimeError(
        "DB_PASSWORD manquant : vérifie le contenu de ton fichier .env."
    )

# Chemins utiles, centralisés ici pour que tous les modules (extractor,
# cleaner, logger...) pointent vers les mêmes dossiers sans les recalculer.
DATA_BRONZE_DIR = PROJECT_ROOT / "data" / "bronze"
DATA_SILVER_DIR = PROJECT_ROOT / "data" / "silver"
LOGS_DIR = PROJECT_ROOT / "logs"
