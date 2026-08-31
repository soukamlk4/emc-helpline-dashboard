DROP TABLE IF EXISTS faits_signalements CASCADE;
DROP TABLE IF EXISTS dim_date CASCADE;
DROP TABLE IF EXISTS dim_genre CASCADE;
DROP TABLE IF EXISTS dim_age CASCADE;
DROP TABLE IF EXISTS dim_plateforme CASCADE;
DROP TABLE IF EXISTS dim_type_cyberviolence CASCADE;
DROP TABLE IF EXISTS dim_accompagnement CASCADE;
DROP TABLE IF EXISTS log_imports CASCADE;

CREATE TABLE dim_date (
    date_id     SERIAL PRIMARY KEY,
    date_complete DATE NOT NULL UNIQUE,
    annee       INTEGER NOT NULL,
    mois        INTEGER NOT NULL,
    trimestre   INTEGER NOT NULL,
    nom_mois    VARCHAR(20) NOT NULL
);

CREATE TABLE dim_genre (
    genre_id    SERIAL PRIMARY KEY,
    genre       VARCHAR(30) NOT NULL UNIQUE
);

CREATE TABLE dim_age (
    age_id      SERIAL PRIMARY KEY,
    tranche_age VARCHAR(30) NOT NULL UNIQUE,
    statut_age  VARCHAR(20) NOT NULL
);

CREATE TABLE dim_plateforme (
    plateforme_id SERIAL PRIMARY KEY,
    plateforme    VARCHAR(30) NOT NULL UNIQUE
);

CREATE TABLE dim_type_cyberviolence (
    type_id     SERIAL PRIMARY KEY,
    type_cyberviolence VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE dim_accompagnement (
    accomp_id     SERIAL PRIMARY KEY,
    accompagnement VARCHAR(10) NOT NULL,
    type_accompagnement VARCHAR(60),
    accomp_juridique   BOOLEAN NOT NULL DEFAULT FALSE,
    accomp_psychique   BOOLEAN NOT NULL DEFAULT FALSE,
    accomp_suppression BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (accompagnement, type_accompagnement)
);

CREATE TABLE faits_signalements (
    signalement_id  INTEGER PRIMARY KEY,
    date_id         INTEGER NOT NULL REFERENCES dim_date(date_id),
    genre_id        INTEGER NOT NULL REFERENCES dim_genre(genre_id),
    age_id          INTEGER NOT NULL REFERENCES dim_age(age_id),
    plateforme_id   INTEGER NOT NULL REFERENCES dim_plateforme(plateforme_id),
    type_id         INTEGER NOT NULL REFERENCES dim_type_cyberviolence(type_id),
    accomp_id       INTEGER NOT NULL REFERENCES dim_accompagnement(accomp_id),
    anonymat        VARCHAR(10) NOT NULL,
    langue          VARCHAR(5)  NOT NULL,
    nb_signalements INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX idx_faits_date ON faits_signalements(date_id);
CREATE INDEX idx_faits_genre ON faits_signalements(genre_id);
CREATE INDEX idx_faits_age ON faits_signalements(age_id);
CREATE INDEX idx_faits_plateforme ON faits_signalements(plateforme_id);
CREATE INDEX idx_faits_type ON faits_signalements(type_id);

-- Traçabilité des imports, avec hash du fichier pour détecter les
-- fichiers déjà traités (étape "import incrémental / historique").
CREATE TABLE log_imports (
    import_id           SERIAL PRIMARY KEY,
    fichier_source       VARCHAR(255) NOT NULL,
    fichier_hash          VARCHAR(64),          -- SHA-256 du contenu du fichier
    date_import           TIMESTAMP NOT NULL DEFAULT NOW(),
    nb_lignes_lues        INTEGER NOT NULL,
    nb_lignes_valides     INTEGER NOT NULL DEFAULT 0,
    nb_lignes_inserees    INTEGER NOT NULL,
    nb_lignes_ignorees    INTEGER NOT NULL DEFAULT 0,
    nb_lignes_rejetees    INTEGER NOT NULL DEFAULT 0,
    statut                VARCHAR(20) NOT NULL DEFAULT 'succes',
    message_erreur         TEXT
);

CREATE INDEX idx_log_imports_hash ON log_imports(fichier_hash);
