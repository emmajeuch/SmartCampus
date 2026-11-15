-- SmartCampus : script de création de la base (SQLite)
-- Tables issues du MCD (conception/mcd.mcd). Une association (1,1) devient une clé étrangère.
-- Les dates sont du texte AAAA-MM-JJ et les heures du texte HH:MM : SQLite sait alors les comparer.

PRAGMA foreign_keys = ON;

CREATE TABLE BATIMENT (
    id_batiment   INTEGER PRIMARY KEY,
    nom           TEXT NOT NULL,
    adresse       TEXT
);

CREATE TABLE SALLE (
    id_salle      INTEGER PRIMARY KEY,
    nom           TEXT NOT NULL,
    capacite      INTEGER,
    type          TEXT,                 -- amphi, TD, TP info, examen
    id_batiment   INTEGER NOT NULL REFERENCES BATIMENT(id_batiment)
);

CREATE TABLE FORMATION (
    id_formation  INTEGER PRIMARY KEY,
    intitule      TEXT NOT NULL,
    niveau        TEXT                  -- L1, L2, L3
);

CREATE TABLE GROUPE (
    id_groupe     INTEGER PRIMARY KEY,
    nom           TEXT NOT NULL,
    id_formation  INTEGER NOT NULL REFERENCES FORMATION(id_formation)
);

CREATE TABLE ETUDIANT (
    id_etudiant   INTEGER PRIMARY KEY,
    nom           TEXT NOT NULL,
    prenom        TEXT NOT NULL,
    email         TEXT,
    id_groupe     INTEGER NOT NULL REFERENCES GROUPE(id_groupe)
);

CREATE TABLE ENSEIGNANT (
    id_enseignant INTEGER PRIMARY KEY,
    nom           TEXT NOT NULL,
    prenom        TEXT NOT NULL,
    email         TEXT
);

CREATE TABLE COURS (
    id_cours      INTEGER PRIMARY KEY,
    intitule      TEXT NOT NULL,
    code          TEXT,
    ects          INTEGER,
    id_formation  INTEGER NOT NULL REFERENCES FORMATION(id_formation),
    id_enseignant INTEGER NOT NULL REFERENCES ENSEIGNANT(id_enseignant)
);

CREATE TABLE SEANCE (
    id_seance     INTEGER PRIMARY KEY,
    date_seance   TEXT NOT NULL,        -- AAAA-MM-JJ
    heure_debut   TEXT NOT NULL,        -- HH:MM
    heure_fin     TEXT NOT NULL,        -- HH:MM
    type          TEXT,                 -- CM, TD, TP
    id_cours      INTEGER NOT NULL REFERENCES COURS(id_cours),
    id_groupe     INTEGER NOT NULL REFERENCES GROUPE(id_groupe),
    id_salle      INTEGER NOT NULL REFERENCES SALLE(id_salle)
);

CREATE TABLE EXAMEN (
    id_examen     INTEGER PRIMARY KEY,
    date_examen   TEXT NOT NULL,        -- AAAA-MM-JJ
    heure_debut   TEXT NOT NULL,
    heure_fin     TEXT NOT NULL,
    type          TEXT,                 -- partiel, écrit, oral, QCM
    id_cours      INTEGER NOT NULL REFERENCES COURS(id_cours),
    id_salle      INTEGER NOT NULL REFERENCES SALLE(id_salle)
);

CREATE TABLE SERVICE (
    id_service    INTEGER PRIMARY KEY,
    nom           TEXT NOT NULL,
    categorie     TEXT,
    telephone     TEXT,
    email         TEXT,
    lien          TEXT,
    id_batiment   INTEGER NOT NULL REFERENCES BATIMENT(id_batiment)
);

CREATE TABLE HORAIRE_SERVICE (
    id_horaire       INTEGER PRIMARY KEY,
    jour_semaine     TEXT NOT NULL,     -- lundi, mardi, ... dimanche
    heure_ouverture  TEXT NOT NULL,     -- HH:MM
    heure_fermeture  TEXT NOT NULL,     -- HH:MM
    id_service       INTEGER NOT NULL REFERENCES SERVICE(id_service)
);

CREATE TABLE ANNONCE (
    id_annonce    INTEGER PRIMARY KEY,
    titre         TEXT NOT NULL,
    lien          TEXT,
    date_pub      TEXT,                 -- AAAA-MM-JJ
    categorie     TEXT,                 -- scolarité, vie étudiante, examens, stages et emploi
    resume        TEXT                  -- rempli plus tard par l'IA
);

CREATE TABLE MORCEAU (
    id_morceau     INTEGER PRIMARY KEY,
    texte          TEXT NOT NULL,
    vecteur        TEXT,                -- embedding, rempli plus tard (RAG)
    titre_document TEXT,
    page           INTEGER,
    lien           TEXT,
    id_service     INTEGER REFERENCES SERVICE(id_service)   -- peut rester vide (0,1)
);
