"""Voie « données » du chat SmartCampus.

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

MODELE = "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
LIGNES_MAX = 50          # on ne renvoie jamais plus de 50 lignes à l'IA
ESSAIS_MAX = 2           # si la requête plante, l'IA a droit à une seconde chance

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
- Si la question ne concerne pas la base (cours, salles, examens, services, annonces), réponds exactement : HORS_BASE"""


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
        return pd.read_sql_query(sql.strip().rstrip(";"), connexion).head(LIGNES_MAX)
    finally:
        connexion.close()


# ---------------------------------------------------------------- 3. résultat -> réponse

CONSIGNE_REPONSE = """Tu es SmartCampus, l'assistant des étudiants de l'université Toulouse Capitole.
Tu tutoies l'étudiant et tu réponds en français, en deux ou trois phrases, à partir du résultat de la base qu'on te donne et de lui seul.
Le résultat a déjà été filtré par une requête SQL : chaque ligne répond à la question (la bonne date, le bon groupe, le bon cours). S'il contient des lignes, donne-les.
Écris les dates en JJ/MM/AAAA et les heures comme 14 h 30.
Seulement si le résultat indique « (aucune ligne) », dis que tu n'as rien trouvé dans la base et propose de reformuler.
N'invente jamais une salle, une heure ou un nom absent du résultat."""


def rediger(question, sql, resultat, compte, jeton):
    tableau = "(aucune ligne)" if resultat.empty else resultat.to_csv(index=False, sep=";")
    messages = [{"role": "system", "content": CONSIGNE_REPONSE},
                {"role": "user", "content": f"Question : {question}\n\nRequête lancée :\n{sql}\n\nRésultat de la base :\n{tableau}"}]
    return appeler_ia(messages, compte, jeton)


# ---------------------------------------------------------------- tout ensemble

def repondre(question, chemin_base, aujourd_hui, groupe, compte, jeton):
    """Renvoie un dictionnaire : la réponse, et de quoi montrer comment on l'a trouvée."""
    schema, _ = decrire_base(chemin_base)
    messages = [{"role": "system", "content": consigne_sql(schema, aujourd_hui, groupe)},
                {"role": "user", "content": question}]
    sql, erreur = "", ""
    for _ in range(ESSAIS_MAX):
        sql = nettoyer(appeler_ia(messages, compte, jeton))
        if sql.upper().startswith("HORS_BASE"):
            return {"reponse": "Je réponds pour l'instant aux questions sur les cours, les salles, "
                               "les examens, les services et les annonces de l'université.",
                    "sql": None, "resultat": None}
        refus = verifier(sql)
        if refus:
            return {"reponse": f"Je n'ai pas lancé la requête préparée ({refus}).", "sql": sql, "resultat": None}
        try:
            resultat = executer(sql, chemin_base)
            return {"reponse": rediger(question, sql, resultat, compte, jeton), "sql": sql, "resultat": resultat}
        except Exception as exc:          # requête mal écrite : on renvoie l'erreur à l'IA
            erreur = str(exc)
            messages += [{"role": "assistant", "content": sql},
                         {"role": "user", "content": f"SQLite répond : {erreur}. Corrige la requête."}]
    return {"reponse": "Je n'ai pas réussi à trouver la réponse dans la base. Essaie de reformuler.",
            "sql": sql, "resultat": None, "erreur": erreur}
