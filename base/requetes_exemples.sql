-- Les quatre requêtes d'exemple du sujet, écrites en SQLite.
-- Dates et heures sont du texte (AAAA-MM-JJ, HH:MM) : les comparaisons < et > marchent.
-- Les jointures s'écrivent dans le WHERE, comme en cours de BDD.

-- 1. « Quel est mon emploi du temps demain ? »
--    Pour l'étudiante n° 3 (groupe L2 NM groupe 2), le mardi 17/11/2026.
SELECT SE.heure_debut, SE.heure_fin, C.intitule, SE.type, SA.nom AS salle, B.nom AS batiment
FROM ETUDIANT E, SEANCE SE, COURS C, SALLE SA, BATIMENT B
WHERE E.id_groupe = SE.id_groupe
  AND SE.id_cours = C.id_cours
  AND SE.id_salle = SA.id_salle
  AND SA.id_batiment = B.id_batiment
  AND E.id_etudiant = 3
  AND SE.date_seance = '2026-11-17'
ORDER BY SE.heure_debut;

-- 2. « Dans quelle salle a lieu l'examen de Bases de données ? »
SELECT EX.date_examen, EX.heure_debut, EX.heure_fin, SA.nom AS salle, B.nom AS batiment
FROM EXAMEN EX, COURS C, SALLE SA, BATIMENT B
WHERE EX.id_cours = C.id_cours
  AND EX.id_salle = SA.id_salle
  AND SA.id_batiment = B.id_batiment
  AND C.intitule = 'Base de données';

-- 3. « Quelles salles sont libres jeudi de 14 h à 16 h ? » (jeudi 19/11/2026)
--    Une salle est prise si une séance ou un examen chevauche le créneau :
--    début de l'occupation < 16:00 et fin de l'occupation > 14:00.
SELECT SA.nom, SA.type, SA.capacite, B.nom AS batiment
FROM SALLE SA, BATIMENT B
WHERE SA.id_batiment = B.id_batiment
  AND SA.id_salle NOT IN (SELECT id_salle FROM SEANCE
                          WHERE date_seance = '2026-11-19'
                            AND heure_debut < '16:00' AND heure_fin > '14:00')
  AND SA.id_salle NOT IN (SELECT id_salle FROM EXAMEN
                          WHERE date_examen = '2026-11-19'
                            AND heure_debut < '16:00' AND heure_fin > '14:00')
ORDER BY B.nom, SA.nom;

-- 4. « Quels sont les horaires de la bibliothèque ? »
SELECT H.jour_semaine, H.heure_ouverture, H.heure_fermeture
FROM SERVICE S, HORAIRE_SERVICE H
WHERE S.id_service = H.id_service
  AND S.nom LIKE '%Bibliothèque%'
ORDER BY CASE H.jour_semaine
           WHEN 'lundi' THEN 1 WHEN 'mardi' THEN 2 WHEN 'mercredi' THEN 3
           WHEN 'jeudi' THEN 4 WHEN 'vendredi' THEN 5 WHEN 'samedi' THEN 6 ELSE 7 END;
