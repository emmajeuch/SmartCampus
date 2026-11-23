"""Chat SmartCampus : voie « données » (SQL vérifié) et assemblage avec la voie « documents » (rag.py).

Une question en français devient une requête SQL, la requête est vérifiée,
lancée sur smartcampus.db, puis l'IA rédige la réponse à partir du résultat.

    question --(1. IA)--> SQL --(2. vérification)--> résultat --(3. IA)--> réponse

L'IA est Workers AI de Cloudflare, appelée par son API REST.
La clé est dans les secrets de Streamlit, jamais dans le dépôt.
"""

import re
import sqlite3

import pandas as pd
import requests

import rag

MODELE = "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
LIGNES_MAX = 50          # on ne renvoie jamais plus de 50 lignes à l'IA
ESSAIS_MAX = 2           # si la requête plante, l'IA a droit à une seconde chance
# Colonnes dont on donne les valeurs possibles à l'IA, pour qu'elle filtre avec les vrais mots.
COLONNES_A_VALEURS = {"categorie", "type", "niveau", "jour_semaine"}

# Mots qui modifient la base ou sortent de nos tables : refusés d'office.
MOTS_INTERDITS = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "REPLACE",
                  "ATTACH", "DETACH", "PRAGMA", "VACUUM", "REINDEX", "TRIGGER", "GRANT"]


# ---------------------------------------------------------------- l'IA

def appeler_ia(messages, compte, jeton):
    """Envoie la conversation à Workers AI et renvoie le texte de sa réponse."""
    adresse = f"https://api.cloudflare.com/client/v4/accounts/{compte}/ai/run/{MODELE}"
    reponse = requests.post(adresse, headers={"Authorization": f"Bearer {jeton}"},
                            json={"messages": messages, "temperature": 0, "max_tokens": 600},
                            timeout=60)
    reponse.raise_for_status()
    return reponse.json()["result"]["response"].strip()


# ---------------------------------------------------------------- le schéma donné à l'IA

def decrire_base(chemin_base):
    """Écrit le MLD de la base (tables et colonnes), lu directement dans smartcampus.db.

    Le lire dans la base plutôt que l'écrire à la main évite qu'il soit faux
    le jour où une table change.
    """
    connexion = sqlite3.connect(f"file:{chemin_base}?mode=ro", uri=True)
    try:
        tables = [ligne[0] for ligne in connexion.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")]
        lignes = []
        for table in tables:
            colonnes = connexion.execute(f"PRAGMA table_info({table})").fetchall()
            cles = connexion.execute(f"PRAGMA foreign_key_list({table})").fetchall()
            vers = {cle[3]: f"{cle[2]}.{cle[4]}" for cle in cles}
            morceaux = []
            for colonne in colonnes:
                nom, est_cle = colonne[1], colonne[5]
                texte = nom + (" (clé primaire)" if est_cle else "")
                if nom in vers:
                    texte += f" -> {vers[nom]}"
                if nom in COLONNES_A_VALEURS:
                    valeurs = [v[0] for v in connexion.execute(
                        f"SELECT DISTINCT {nom} FROM {table} WHERE {nom} IS NOT NULL ORDER BY 1")]
                    texte += " [valeurs : " + ", ".join(f"'{v}'" for v in valeurs) + "]"
                morceaux.append(texte)
            lignes.append(f"{table}({', '.join(morceaux)})")
        return "\n".join(lignes), set(tables)
    finally:
        connexion.close()


# ---------------------------------------------------------------- 1. question -> SQL

def consigne_sql(schema, aujourd_hui, groupe):
    return f"""Tu traduis des questions d'étudiants de l'université Toulouse Capitole en UNE requête SQLite.

Tables de la base :
{schema}

Règles :
- Réponds uniquement par la requête SQL, sans explication et sans ```.
- Une seule requête SELECT. Jamais INSERT, UPDATE, DELETE, DROP ni rien qui modifie la base.
- Écris les jointures dans le WHERE (FROM A, B WHERE A.x = B.x), pas de JOIN.
- Les dates sont du texte AAAA-MM-JJ et les heures du texte HH:MM : compare-les avec <, >, =.
- Pour chercher un nom (cours, service, salle), utilise LIKE '%mot%' plutôt que =.
- Sélectionne toutes les colonnes utiles à la réponse : pour un cours ou un examen, la date, les heures, l'intitulé, le type et la salle ; pour un service, le jour et les horaires.
- SEANCE.type vaut 'CM', 'TD' ou 'TP'. HORAIRE_SERVICE.jour_semaine est en minuscules ('lundi'...).
- Aujourd'hui, nous sommes le {aujourd_hui}. « Demain », « jeudi », « cette semaine » se calculent à partir de cette date.
- L'étudiant qui pose la question est dans le groupe « {groupe} » (table GROUPE, colonne nom).
- Un cours, un examen ou une salle se cherchent dans SEANCE, EXAMEN et SALLE. ANNONCE ne sert que si on demande une annonce ou une actualité.
- « Mon prochain examen » : les examens des cours de la formation du groupe, à partir d'aujourd'hui, triés par date et heure, LIMIT 1.

Exemples (groupe « L2 NM groupe 2 », aujourd'hui 2026-11-23) :
Question : quels cours j'ai demain ?
SELECT SE.date_seance, SE.heure_debut, SE.heure_fin, C.intitule, SE.type, SA.nom AS salle FROM SEANCE SE, COURS C, SALLE SA, GROUPE G WHERE SE.id_cours = C.id_cours AND SE.id_salle = SA.id_salle AND SE.id_groupe = G.id_groupe AND G.nom = 'L2 NM groupe 2' AND SE.date_seance = '2026-11-24' ORDER BY SE.heure_debut
Question : c'est quand mon prochain exam ?
SELECT EX.date_examen, EX.heure_debut, EX.heure_fin, C.intitule, EX.type, SA.nom AS salle FROM EXAMEN EX, COURS C, SALLE SA, GROUPE G WHERE EX.id_cours = C.id_cours AND EX.id_salle = SA.id_salle AND C.id_formation = G.id_formation AND G.nom = 'L2 NM groupe 2' AND EX.date_examen >= '2026-11-23' ORDER BY EX.date_examen, EX.heure_debut LIMIT 1
Question : quels sont les horaires de la bibliothèque ?
SELECT H.jour_semaine, H.heure_ouverture, H.heure_fermeture FROM SERVICE S, HORAIRE_SERVICE H WHERE S.id_service = H.id_service AND S.nom LIKE '%Bibliothèque%'

- Si la question contient plusieurs demandes, écris la requête pour celle qui concerne la base et ignore les autres.
- Seulement si aucune partie de la question ne concerne la base (cours, salles, examens, services, annonces), réponds exactement : HORS_BASE"""


def nettoyer(texte):
    """Enlève les ``` et le mot sql que l'IA ajoute parfois autour de la requête."""
    texte = re.sub(r"^```(?:sql)?\s*|\s*```$", "", texte.strip(), flags=re.IGNORECASE)
    return texte.strip()


# ---------------------------------------------------------------- 2. vérification

def verifier(sql):
    """Renvoie None si la requête est acceptable, sinon la raison du refus.

    C'est le « SQL vérifié » du sujet : on ne lance pas aveuglément ce que l'IA écrit.
    La base est en plus ouverte en lecture seule : même une requête qui passerait
    ce filtre ne pourrait rien modifier.
    """
    requete = sql.strip().rstrip(";").strip()
    if ";" in requete:
        return "plusieurs requêtes à la suite"
    if not re.match(r"^(SELECT|WITH)\b", requete, flags=re.IGNORECASE):
        return "ce n'est pas un SELECT"
    sans_textes = re.sub(r"'[^']*'", "''", requete)     # on ignore ce qui est entre guillemets
    for mot in MOTS_INTERDITS:
        if re.search(rf"\b{mot}\b", sans_textes, flags=re.IGNORECASE):
            return f"mot interdit : {mot}"
    if re.search(r"\bsqlite_", sans_textes, flags=re.IGNORECASE):
        return "accès aux tables internes de SQLite"
    # Une table inconnue n'est pas vérifiée ici : SQLite la refuse lui-même,
    # et l'erreur est renvoyée à l'IA pour qu'elle corrige.
    return None


def executer(sql, chemin_base):
    """Lance la requête en lecture seule et garde au plus LIGNES_MAX lignes."""
    connexion = sqlite3.connect(f"file:{chemin_base}?mode=ro", uri=True)
    try:
        resultat = pd.read_sql_query(sql.strip().rstrip(";"), connexion).head(LIGNES_MAX)
    finally:
        connexion.close()
    # Deux colonnes peuvent porter le même nom (le nom du cours et celui de la salle) :
    # on numérote les doublons, sinon le tableau de Streamlit refuse de s'afficher.
    vus, noms = {}, []
    for nom in resultat.columns:
        vus[nom] = vus.get(nom, 0) + 1
        noms.append(nom if vus[nom] == 1 else f"{nom}_{vus[nom]}")
    resultat.columns = noms
    return resultat


# ---------------------------------------------------------------- 3. résultat -> réponse

CONSIGNE_REPONSE = """Tu es SmartCampus, l'assistant des étudiants de l'université Toulouse Capitole.
Tu tutoies l'étudiant et tu réponds en français, en trois ou quatre phrases au plus, à partir de ce qu'on te donne et de rien d'autre :
le résultat d'une requête sur la base de l'université, et des passages de documents officiels de l'université.
Le résultat de la base a déjà été filtré par une requête SQL : chaque ligne répond à la question (la bonne date, le bon groupe, le bon cours). S'il contient des lignes, donne-les.
Pour une démarche ou une règle, appuie-toi sur les passages et cite la source entre parenthèses, par exemple (Guide de l'étudiant 2026-2027, p. 26).
Écris les dates en JJ/MM/AAAA et les heures comme 14 h 30.
N'invente jamais une salle, une heure, un nom, une date ou une règle absents de ce qu'on te donne.
Si une partie de la question ne trouve de réponse ni dans le résultat ni dans les passages, dis-le en une phrase et conseille le service de l'université concerné."""


def rediger(question, sql, resultat, passages, compte, jeton):
    contexte = []
    if sql:
        tableau = "(aucune ligne)" if resultat is None or resultat.empty else resultat.to_csv(index=False, sep=";")
        contexte.append(f"Requête lancée :\n{sql}\n\nRésultat de la base :\n{tableau}")
    else:
        contexte.append("Résultat de la base : (aucune requête, la question ne porte pas sur la base)")
    if passages:
        textes = "\n\n".join(f"[{p['titre']}, p. {p['page']}]\n{p['texte']}" for p in passages)
        contexte.append(f"Passages des documents de l'université :\n{textes}")
    else:
        contexte.append("Passages des documents de l'université : (aucun passage sur ce sujet)")
    messages = [{"role": "system", "content": CONSIGNE_REPONSE},
                {"role": "user", "content": f"Question : {question}\n\n" + "\n\n".join(contexte)}]
    return appeler_ia(messages, compte, jeton)


# ---------------------------------------------------------------- tout ensemble

def interroger_base(question, chemin_base, aujourd_hui, groupe, compte, jeton):
    """Voie « données » : renvoie (requête, résultat, remarque). La requête vaut None si
    la question ne porte pas sur la base."""
    schema, _ = decrire_base(chemin_base)
    messages = [{"role": "system", "content": consigne_sql(schema, aujourd_hui, groupe)},
                {"role": "user", "content": question}]
    sql = ""
    for _ in range(ESSAIS_MAX):
        sql = nettoyer(appeler_ia(messages, compte, jeton))
        if sql.upper().startswith("HORS_BASE"):
            return None, None, None
        refus = verifier(sql)
        if refus:
            return sql, None, f"requête refusée : {refus}"
        try:
            return sql, executer(sql, chemin_base), None
        except Exception as exc:          # requête mal écrite : on renvoie l'erreur à l'IA
            messages += [{"role": "assistant", "content": sql},
                         {"role": "user", "content": f"SQLite répond : {exc}. Corrige la requête."}]
    return sql, None, "la requête n'a pas marché après deux essais"


def repondre(question, chemin_base, aujourd_hui, groupe, compte, jeton):
    """Les deux voies ensemble : la base (SQL vérifié) et les documents (RAG).
    Renvoie la réponse, et de quoi montrer comment on l'a trouvée."""
    passages = rag.chercher(question, chemin_base, compte, jeton)
    sql, resultat, remarque = interroger_base(question, chemin_base, aujourd_hui, groupe, compte, jeton)
    if sql is None and not passages:
        return {"reponse": "Je réponds aux questions sur la vie à l'université : cours, salles, examens, "
                           "services, annonces et démarches. Là, je n'ai rien trouvé sur ce sujet.",
                "sql": None, "resultat": None, "passages": []}
    reponse = rediger(question, sql if resultat is not None else None, resultat, passages, compte, jeton)
    return {"reponse": reponse, "sql": sql, "resultat": resultat, "passages": passages, "remarque": remarque}
