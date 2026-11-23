"""Découpe les documents de l'université en morceaux pour le RAG (table MORCEAU).

Utilisation, depuis le dossier du projet :
    python base/decouper_documents.py
    python base/creer_base.py

Les PDF sont dans documents/, avec leur titre et leur lien dans documents/sources.csv
(fichier;titre;lien). Chaque page est coupée en morceaux d'environ TAILLE caractères,
aux fins de phrase, avec un léger chevauchement pour ne pas couper une idée en deux.
Le résultat va dans base/donnees/MORCEAU.csv ; la colonne vecteur reste vide :
les embeddings sont calculés par l'application, avec Workers AI (voir rag.py).
"""

import csv
import os
import re

from pypdf import PdfReader

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOSSIER_DOCS = os.path.join(RACINE, "documents")
SORTIE = os.path.join(RACINE, "base", "donnees", "MORCEAU.csv")
TAILLE = 900          # caractères par morceau, environ une demi-page
CHEVAUCHEMENT = 150   # caractères repris du morceau précédent
TAILLE_MIN = 120      # en dessous, un bout de page (titre seul, numéro) est ignoré

# Mots qui rattachent un morceau à un service de la table SERVICE (clé étrangère id_service).
SERVICES = {
    1: ["scolarité", "inscription administrative", "certificat de scolarité", "mondossierweb"],
    2: ["bibliothèque", "bu ", "emprunt"],
    3: ["restaurant universitaire", "crous", "restauration"],
    4: ["santé", "médecin", "psychologue", "sse"],
    5: ["orientation", "insertion professionnelle", "stage"],
    6: ["international", "mobilité", "erasmus"],
}


def nettoyer(texte):
    """Recolle les mots coupés en fin de ligne et ramène les espaces à un seul."""
    texte = re.sub(r"-\n(\w)", r"\1", texte)
    texte = re.sub(r"\s+", " ", texte)
    return texte.strip()


def couper(texte):
    """Coupe un texte en morceaux d'environ TAILLE caractères, aux fins de phrase."""
    phrases = re.split(r"(?<=[.!?:;])\s+", texte)
    morceaux, courant = [], ""
    for phrase in phrases:
        if len(courant) + len(phrase) > TAILLE and len(courant) >= TAILLE_MIN:
            morceaux.append(courant.strip())
            courant = courant[-CHEVAUCHEMENT:]           # on garde la fin pour le contexte
            courant = courant[courant.find(" ") + 1:]    # sans couper un mot
        courant += " " + phrase
    if len(courant.strip()) >= TAILLE_MIN:
        morceaux.append(courant.strip())
    return morceaux


def service_de(texte):
    """Renvoie le service dont le morceau parle le plus, ou None."""
    bas = texte.lower()
    scores = {num: sum(bas.count(mot) for mot in mots) for num, mots in SERVICES.items()}
    meilleur = max(scores, key=scores.get)
    return meilleur if scores[meilleur] > 0 else None


def main():
    with open(os.path.join(DOSSIER_DOCS, "sources.csv"), encoding="utf-8-sig", newline="") as fichier:
        sources = list(csv.DictReader(fichier, delimiter=";"))
    lignes, numero = [], 0
    for source in sources:
        lecteur = PdfReader(os.path.join(DOSSIER_DOCS, source["fichier"]))
        avant = len(lignes)
        for page, contenu in enumerate(lecteur.pages, start=1):
            for morceau in couper(nettoyer(contenu.extract_text() or "")):
                numero += 1
                lignes.append([numero, morceau, "", source["titre"], page, source["lien"],
                               service_de(morceau) or ""])
        print(f"{source['titre']} : {len(lecteur.pages)} pages, {len(lignes) - avant} morceaux")
    with open(SORTIE, "w", encoding="utf-8", newline="") as fichier:
        ecrivain = csv.writer(fichier, delimiter=";", lineterminator="\n")
        ecrivain.writerow(["id_morceau", "texte", "vecteur", "titre_document", "page", "lien", "id_service"])
        ecrivain.writerows(lignes)
    print(f"{len(lignes)} morceaux écrits dans {SORTIE}")


if __name__ == "__main__":
    main()
