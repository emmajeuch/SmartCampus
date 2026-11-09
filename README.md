# SmartCampus

Assistant web de la vie universitaire, projet de l'Atelier Numérique et Management
(L2 MIASHS, Toulouse Capitole, 2026-2027).

Trois onglets :

- **Chat** : on pose une question en français (salles, cours, examens, règlement) et l'application répond.
- **Mon emploi du temps** : les cours de la semaine pour un groupe, et les salles libres.
- **Actualités** : les annonces de l'université, résumées et rangées par catégorie.

## Lancer l'application sur son PC

```
pip install -r requirements.txt
streamlit run app.py
```

L'application s'ouvre dans le navigateur.

## Organisation du dépôt

| Fichier | Rôle |
|---|---|
| `app.py` | L'application Streamlit |
| `requirements.txt` | Les bibliothèques Python à installer |

La base de données (Access, puis `smartcampus.db`), les documents et les scripts
arriveront au fil du projet.

## Règles

- On ne modifie les données que dans Access, puis on relance le script de recopie.
- La clé de l'IA n'est jamais dans le code : seulement dans les réglages secrets de Streamlit.
- Chaque envoi (commit) dit en une phrase ce qui a changé.
