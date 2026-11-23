import datetime
import os
import sqlite3

import pandas as pd
import requests
import streamlit as st

from chat_donnees import repondre

# La base est lue en lecture seule : l'application ne peut rien y modifier.
CHEMIN_BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "smartcampus.db")
JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


def lire(requete, parametres=()):
    """Lance une requête SELECT sur smartcampus.db et renvoie le résultat en tableau."""
    connexion = sqlite3.connect(f"file:{CHEMIN_BASE}?mode=ro", uri=True)
    try:
        return pd.read_sql_query(requete, connexion, params=parametres)
    finally:
        connexion.close()


def date_en_francais(jour):
    """2026-11-17 -> « mardi 17/11/2026 »."""
    return f"{JOURS[jour.weekday()]} {jour.strftime('%d/%m/%Y')}"


def bornes_des_seances():
    """Première et dernière date présentes dans la table SEANCE."""
    bornes = lire("SELECT MIN(date_seance) AS debut, MAX(date_seance) AS fin FROM SEANCE")
    return (datetime.date.fromisoformat(bornes.debut[0]), datetime.date.fromisoformat(bornes.fin[0]))


def date_par_defaut(debut, fin):
    """Aujourd'hui si la base a des séances ce jour-là, sinon le premier jour de la base."""
    aujourd_hui = datetime.date.today()
    return aujourd_hui if debut <= aujourd_hui <= fin else debut


st.set_page_config(page_title="SmartCampus", page_icon="🎓")

st.title("SmartCampus")
st.caption("L'assistant de la vie universitaire — Toulouse Capitole")

chat, edt, actus = st.tabs(["Chat", "Mon emploi du temps", "Actualités"])

with chat:
    if "messages" not in st.session_state:
        st.session_state.messages = []

    groupes_chat = lire("SELECT nom FROM GROUPE ORDER BY nom").nom.tolist()
    groupe_chat = st.selectbox("Ton groupe", groupes_chat, key="groupe_chat",
                               index=groupes_chat.index("L2 NM groupe 2") if "L2 NM groupe 2" in groupes_chat else 0)

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
            if message.get("sql"):
                # On montre comment la réponse a été trouvée : la requête et ce que la base a renvoyé.
                with st.expander("Comment j'ai trouvé"):
                    st.code(message["sql"], language="sql")
                    if message.get("resultat") is not None:
                        st.dataframe(message["resultat"], hide_index=True, width="stretch")

    question = st.chat_input("Pose ta question")
    if question:
        st.session_state.messages.append({"role": "user", "content": question})
        try:
            compte, jeton = st.secrets["CF_ACCOUNT_ID"], st.secrets["CF_API_TOKEN"]
        except Exception:                 # pas de secrets (par exemple en local)
            compte = jeton = None
        if not compte or not jeton:
            st.session_state.messages.append({"role": "assistant",
                                              "content": "La clé Workers AI manque dans les secrets de l'application."})
        else:
            with st.spinner("Je cherche dans la base…"):
                try:
                    trouve = repondre(question, CHEMIN_BASE, date_en_francais(datetime.date.today()) +
                                      f" ({datetime.date.today().isoformat()})", groupe_chat, compte, jeton)
                except requests.RequestException:
                    trouve = {"reponse": "Je n'arrive pas à joindre l'IA pour l'instant. Réessaie dans un moment."}
            st.session_state.messages.append({"role": "assistant", "content": trouve["reponse"],
                                              "sql": trouve.get("sql"), "resultat": trouve.get("resultat")})
        st.rerun()

with edt:
    debut, fin = bornes_des_seances()
    groupes = lire("SELECT id_groupe, nom FROM GROUPE ORDER BY nom")

    st.subheader("Mes cours")
    noms = groupes.nom.tolist()
    groupe = st.selectbox("Ton groupe", noms, index=noms.index("L2 NM groupe 2") if "L2 NM groupe 2" in noms else 0)
    id_groupe = int(groupes[groupes.nom == groupe].id_groupe.iloc[0])
    jour = st.date_input("Jour", value=date_par_defaut(debut, fin), min_value=debut, max_value=fin, format="DD/MM/YYYY")

    cours_du_jour = lire("""
        SELECT SE.heure_debut AS "Début", SE.heure_fin AS "Fin", C.intitule AS "Cours",
               SE.type AS "Type", SA.nom AS "Salle", B.nom AS "Bâtiment"
        FROM SEANCE SE, COURS C, SALLE SA, BATIMENT B
        WHERE SE.id_cours = C.id_cours AND SE.id_salle = SA.id_salle
          AND SA.id_batiment = B.id_batiment
          AND SE.id_groupe = ? AND SE.date_seance = ?
        ORDER BY SE.heure_debut""", (id_groupe, jour.isoformat()))
    if cours_du_jour.empty:
        st.info(f"Pas de cours le {date_en_francais(jour)}.")
    else:
        st.write(f"**{date_en_francais(jour).capitalize()}**")
        st.dataframe(cours_du_jour, hide_index=True, width="stretch")

    examens = lire("""
        SELECT EX.date_examen AS "Date", EX.heure_debut AS "Début", EX.heure_fin AS "Fin",
               C.intitule AS "Cours", SA.nom AS "Salle"
        FROM EXAMEN EX, COURS C, SALLE SA, GROUPE G
        WHERE EX.id_cours = C.id_cours AND EX.id_salle = SA.id_salle
          AND C.id_formation = G.id_formation AND G.id_groupe = ?
          AND EX.date_examen >= ?
        ORDER BY EX.date_examen, EX.heure_debut""", (id_groupe, jour.isoformat()))
    if not examens.empty:
        examens["Date"] = [datetime.date.fromisoformat(d).strftime("%d/%m/%Y") for d in examens["Date"]]
        st.write("**Prochains examens de ta formation**")
        st.dataframe(examens, hide_index=True, width="stretch")

    st.subheader("Salles libres")
    jour_libre = st.date_input("Jour ", value=date_par_defaut(debut, fin), min_value=debut, max_value=fin,
                               format="DD/MM/YYYY", key="jour_salles")
    heures = [f"{h:02d}:{m:02d}" for h in range(8, 21) for m in (0, 30)]
    colonne_debut, colonne_fin = st.columns(2)
    heure_debut = colonne_debut.selectbox("De", heures, index=heures.index("14:00"))
    heure_fin = colonne_fin.selectbox("À", heures, index=heures.index("16:00"))

    if heure_debut >= heure_fin:
        st.warning("L'heure de fin doit être après l'heure de début.")
    else:
        # Une salle est prise si une séance ou un examen chevauche le créneau.
        libres = lire("""
            SELECT SA.nom AS "Salle", SA.type AS "Type", SA.capacite AS "Places", B.nom AS "Bâtiment"
            FROM SALLE SA, BATIMENT B
            WHERE SA.id_batiment = B.id_batiment
              AND SA.id_salle NOT IN (SELECT id_salle FROM SEANCE WHERE date_seance = ?
                                      AND heure_debut < ? AND heure_fin > ?)
              AND SA.id_salle NOT IN (SELECT id_salle FROM EXAMEN WHERE date_examen = ?
                                      AND heure_debut < ? AND heure_fin > ?)
            ORDER BY B.nom, SA.nom""",
            (jour_libre.isoformat(), heure_fin, heure_debut, jour_libre.isoformat(), heure_fin, heure_debut))
        st.write(f"{len(libres)} salle(s) libre(s) le {date_en_francais(jour_libre)} de {heure_debut} à {heure_fin}")
        st.dataframe(libres, hide_index=True, width="stretch")

with actus:
    annonces = lire("SELECT titre, lien, date_pub, categorie, resume FROM ANNONCE ORDER BY date_pub DESC")
    categories = ["toutes"] + sorted(annonces.categorie.unique().tolist())
    choix = st.radio("Catégorie", categories, horizontal=True)
    if choix != "toutes":
        annonces = annonces[annonces.categorie == choix]

    for annonce in annonces.itertuples():
        with st.container(border=True):
            date_pub = datetime.date.fromisoformat(annonce.date_pub).strftime("%d/%m/%Y")
            st.markdown(f"**{annonce.titre}**")
            st.caption(f"{date_pub} · {annonce.categorie}")
            st.write(annonce.resume if annonce.resume else "Résumé à venir : il sera écrit par l'IA.")
            st.markdown(f"[Lire l'annonce]({annonce.lien})")

    st.caption("Annonces fictives pour l'instant.")
