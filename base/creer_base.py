"""Fabrique smartcampus.db (SQLite) à partir de schema.sql et des fichiers CSV.

Utilisation, depuis le dossier du projet :
    python base/creer_base.py

Les CSV sont dans base/donnees/, un fichier par table, séparés par des points-virgules,
encodés en UTF-8. Ce sont aussi les fichiers qu'on importe dans Access, puis ceux
qu'Access réexporte : on modifie les données dans Access, on exporte, on relance ce script.
"""

import csv
import os
import sqlite3

DOSSIER_BASE = os.path.dirname(os.path.abspath(__file__))
DOSSIER_DONNEES = os.path.join(DOSSIER_BASE, "donnees")
SCHEMA = os.path.join(DOSSIER_BASE, "schema.sql")
SORTIE = os.path.join(os.path.dirname(DOSSIER_BASE), "smartcampus.db")

# Ordre de remplissage : une table passe après celles dont elle reprend la clé.
TABLES = [
    "BATIMENT", "SALLE", "FORMATION", "GROUPE", "ETUDIANT", "ENSEIGNANT",
    "COURS", "SEANCE", "EXAMEN", "SERVICE", "HORAIRE_SERVICE", "ANNONCE", "MORCEAU",
]


def lire_csv(table):
    """Renvoie les noms de colonnes et les lignes du CSV d'une table (cellule vide = NULL)."""
    chemin = os.path.join(DOSSIER_DONNEES, table + ".csv")
    with open(chemin, encoding="utf-8-sig", newline="") as fichier:
        lignes = list(csv.reader(fichier, delimiter=";"))
    colonnes = lignes[0]
    valeurs = [[cellule if cellule != "" else None for cellule in ligne] for ligne in lignes[1:] if ligne]
    return colonnes, valeurs


def remplir(connexion, table):
    """Insère les lignes du CSV dans la table et renvoie leur nombre."""
    colonnes, valeurs = lire_csv(table)
    trous = ", ".join("?" for _ in colonnes)
    requete = f"INSERT INTO {table} ({', '.join(colonnes)}) VALUES ({trous})"
    connexion.executemany(requete, valeurs)
    return len(valeurs)


def verifier(connexion):
    """Contrôles de cohérence : renvoie la liste des problèmes trouvés."""
    problemes = []
    # Deux cours différents dans la même salle au même moment (un CM commun à deux groupes est permis).
    conflits_salle = connexion.execute("""
        SELECT A.date_seance, A.heure_debut, S.nom
        FROM SEANCE A, SEANCE B, SALLE S
        WHERE A.id_seance < B.id_seance
          AND A.id_salle = B.id_salle AND A.id_salle = S.id_salle
          AND A.date_seance = B.date_seance
          AND A.heure_debut < B.heure_fin AND B.heure_debut < A.heure_fin
          AND A.id_cours <> B.id_cours""").fetchall()
    problemes += [f"salle {s} prise deux fois le {d} à {h}" for d, h, s in conflits_salle]
    # Un groupe qui a deux séances en même temps.
    conflits_groupe = connexion.execute("""
        SELECT A.date_seance, A.heure_debut, G.nom
        FROM SEANCE A, SEANCE B, GROUPE G
        WHERE A.id_seance < B.id_seance
          AND A.id_groupe = B.id_groupe AND A.id_groupe = G.id_groupe
          AND A.date_seance = B.date_seance
          AND A.heure_debut < B.heure_fin AND B.heure_debut < A.heure_fin""").fetchall()
    problemes += [f"{g} a deux séances le {d} à {h}" for d, h, g in conflits_groupe]
    # Un examen dans une salle occupée par un cours.
    conflits_examen = connexion.execute("""
        SELECT E.date_examen, E.heure_debut, S.nom
        FROM EXAMEN E, SEANCE A, SALLE S
        WHERE E.id_salle = A.id_salle AND E.id_salle = S.id_salle
          AND E.date_examen = A.date_seance
          AND E.heure_debut < A.heure_fin AND A.heure_debut < E.heure_fin""").fetchall()
    problemes += [f"examen du {d} à {h} dans {s}, salle déjà prise par un cours" for d, h, s in conflits_examen]
    return problemes


def main():
    if os.path.exists(SORTIE):
        os.remove(SORTIE)
    connexion = sqlite3.connect(SORTIE)
    connexion.execute("PRAGMA foreign_keys = ON")
    with open(SCHEMA, encoding="utf-8") as fichier:
        connexion.executescript(fichier.read())
    for table in TABLES:
        print(f"{table:16} {remplir(connexion, table):4} lignes")
    connexion.commit()
    problemes = verifier(connexion)
    connexion.close()
    for probleme in problemes:
        print("Attention :", probleme)
    print("Base écrite :", SORTIE if not problemes else SORTIE + " (avec des incohérences)")


if __name__ == "__main__":
    main()
