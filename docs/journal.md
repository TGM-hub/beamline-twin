# Cahier de bord

## Séance 1 — 30 août 2026 — Étape 1 (cours)

- Feuille de route arrêtée : 6 étapes, ~9 week-ends jusqu'au 5 novembre.
- Segment retenu pour le jumeau : **ligne basse énergie (LBE)** de SPIRAL2,
  source ECR → dipôle d'analyse → cage de Faraday. Le plus simple à comprendre,
  le plus riche en signaux.
- Choix technique : **caproto** (Python pur) plutôt qu'EPICS base dans Docker.
  Raison : installation sans compilation sous Windows, et c'est un vrai serveur
  Channel Access. Docker est reporté à l'étape 4, où il est justifié.
  Aller-retour soft IOC ↔ client CA vérifié avant la séance.
- Cours rédigé : `docs/01-cours-epics-et-ligne-basse-energie.md`.
- Reste à faire pour clore l'étape 1 : `config/pv_map.yaml`, `sim/beamline.py`,
  `sim/ioc.py`, `tests/`.
- Décision : base de PV « réaliste » (~70 canaux) pour l'étape 1, générée depuis
  `config/pv_map.yaml` — consignes, mesures, états, vide, pour tous les équipements
  de la LBE. Le coût marginal est faible puisque tout est déclaratif, et la démo
  finale y gagne beaucoup.

## Séance 2 — 7 septembre 2026 — Base de PV et préparation d'une journée sans PC

- `config/pv_map.yaml` écrit sur la branche `etape-01-pv-map` : **69 PV, 16 équipements**
  (15 consignes, 39 mesures, 14 états, 1 compteur ; 17 PV portent des seuils d'alarme).
- Choix de conception : le YAML décrit des **équipements et des signaux**, pas des noms.
  `sim/pvmap.py` dérive les noms par une règle unique. Personne ne peut inventer un nom
  hors convention parce qu'il n'y a nulle part où le taper — même principe que leur base
  de configuration PostgreSQL.
- Règles imposées par les tests : trois segments dans un nom, toute consigne a sa mesure,
  aucune alarme sur une consigne, description bilingue obligatoire, taille de la base
  figée à 69.
- Coquille corrigée en cours de route : `AQ_SET` donnait `AQ_SET_SP` — redondance entre
  le radical et le suffixe. Renommé en `AQ`.
- Rédigé pour la journée sans PC : `docs/01b-convention-de-nommage.md` (dont sept
  questions de revue), `docs/02-cours-historian-et-logbook.md`,
  `docs/fiches-revision.md` (28 questions).
- Dépôt à publier sur GitHub en public ; la revue du `pv_map` se fera en pull request.
