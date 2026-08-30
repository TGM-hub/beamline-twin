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
