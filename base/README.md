# La base de données

| Fichier | Rôle |
|---|---|
| `schema.sql` | Script de création des 13 tables (livrable 2), en SQLite |
| `donnees/*.csv` | Le jeu de données fictif, un fichier par table (séparateur `;`, UTF-8) |
| `creer_base.py` | Fabrique `smartcampus.db` à partir de `schema.sql` et des CSV, puis vérifie la cohérence |
| `requetes_exemples.sql` | Les quatre requêtes d'exemple du sujet, testées sur la base |

Le jeu de données : 3 formations, 4 groupes, 21 cours, 12 salles dans 4 bâtiments, 10 enseignants,
8 étudiants, 175 séances (du 16/11 au 18/12/2026), 6 examens, 6 services et leurs horaires, 6 annonces.
Tout est fictif, sauf les intitulés, codes et ECTS des cours de L2 NM et les dates des examens de BDD
(19/11) et de contrôle de gestion (30/11).

## Refaire la base

```
python base/creer_base.py
```

Le script recrée `smartcampus.db` à la racine du dépôt et signale les incohérences : une salle prise par
deux cours en même temps, un groupe qui a deux séances à la fois, un examen dans une salle occupée.

## Mettre les données dans Access

1. Créer une base Access vide, `smartcampus.accdb`.
2. Pour chaque CSV, dans l'ordre de `creer_base.py` (BATIMENT d'abord, MORCEAU en dernier) :
   Données externes → Nouvelle source de données → À partir d'un fichier → Fichier texte.
   Choisir « Délimité », séparateur point-virgule, cocher « Première ligne contient les noms des champs »,
   et dans « Avancé », la page de codes « Unicode (UTF-8) ».
3. Mettre en **Texte** les colonnes de dates et d'heures (`date_seance`, `heure_debut`…). Si Access les
   transforme en date, elles reviennent au mauvais format à l'export.
4. Clé primaire : la colonne `id_…` de la table.
5. Outils de base de données → Relations : relier chaque clé étrangère à sa table, en cochant
   « Appliquer l'intégrité référentielle ».

## Repasser d'Access à la base en ligne

On modifie les données dans Access, puis :

1. Exporter chaque table en fichier texte (Données externes → Exporter → Fichier texte), délimité, point-virgule,
   avec les noms des champs, en UTF-8, sous le même nom dans `base/donnees/`.
2. Lancer `python base/creer_base.py`.
3. Envoyer sur GitHub les CSV et `smartcampus.db` : le site se met à jour.
