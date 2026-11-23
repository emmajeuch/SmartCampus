"""Voie « documents » du chat : retrouver les passages des documents de l'université
qui répondent à une question (RAG).

1. Chaque morceau de la table MORCEAU est transformé en vecteur (embedding) par le
   modèle bge-m3 de Workers AI. C'est fait une seule fois au démarrage de l'application,
   puis gardé en mémoire.
2. La question est transformée en vecteur de la même façon.
3. On garde les morceaux dont le vecteur est le plus proche de celui de la question
   (similarité cosinus) : ce sont eux qu'on donne à l'IA pour rédiger la réponse.
"""

import sqlite3

import numpy as np
import requests

MODELE_EMBEDDING = "@cf/baai/bge-m3"
PAR_APPEL = 50        # morceaux envoyés à Workers AI en une fois
NB_PASSAGES = 4       # passages donnés à l'IA
SEUIL = 0.45          # en dessous, le passage est jugé sans rapport avec la question

_cache = {}           # vecteurs des morceaux, calculés une fois par démarrage


def vectoriser(textes, compte, jeton):
    """Renvoie une matrice : une ligne (un vecteur) par texte."""
    adresse = f"https://api.cloudflare.com/client/v4/accounts/{compte}/ai/run/{MODELE_EMBEDDING}"
    vecteurs = []
    for debut in range(0, len(textes), PAR_APPEL):
        reponse = requests.post(adresse, headers={"Authorization": f"Bearer {jeton}"},
                                json={"text": textes[debut:debut + PAR_APPEL]}, timeout=60)
        reponse.raise_for_status()
        resultat = reponse.json()["result"]
        vecteurs += resultat.get("data") or resultat.get("response")
    matrice = np.array(vecteurs, dtype=float)
    # On normalise : le produit de deux vecteurs normalisés est leur similarité cosinus.
    return matrice / np.linalg.norm(matrice, axis=1, keepdims=True)


def lire_morceaux(chemin_base):
    connexion = sqlite3.connect(f"file:{chemin_base}?mode=ro", uri=True)
    try:
        return connexion.execute(
            "SELECT id_morceau, texte, titre_document, page, lien FROM MORCEAU ORDER BY id_morceau").fetchall()
    finally:
        connexion.close()


def chercher(question, chemin_base, compte, jeton):
    """Renvoie les passages les plus proches de la question, avec leur score."""
    morceaux = lire_morceaux(chemin_base)
    if not morceaux:
        return []
    cle = (chemin_base, len(morceaux), morceaux[-1][0])
    if cle not in _cache:
        _cache[cle] = vectoriser([m[1] for m in morceaux], compte, jeton)
    vecteurs = _cache[cle]
    scores = vecteurs @ vectoriser([question], compte, jeton)[0]
    meilleurs = np.argsort(scores)[::-1][:NB_PASSAGES]
    return [{"texte": morceaux[i][1], "titre": morceaux[i][2], "page": morceaux[i][3],
             "lien": morceaux[i][4], "score": round(float(scores[i]), 2)}
            for i in meilleurs if scores[i] >= SEUIL]
