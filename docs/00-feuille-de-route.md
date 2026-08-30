# beamline-twin — feuille de route

Objectif : un jumeau numérique minimal d'un segment de ligne d'accélérateur, avec un
modèle IA **réellement branché sur le système de contrôle**, pas dans un notebook.

Deadline candidature : **5 novembre 2026**. Rythme : ~8 h / week-end.
Il reste ~9 week-ends. La marge est mince : chaque étape doit produire quelque chose
de montrable, même imparfait.

| # | Étape | Ce qu'on démontre | Effort |
|---|---|---|---|
| 1 | **Simulateur + IOC EPICS** — la ligne basse énergie (LBE) de SPIRAL2 en soft-IOC, ~70 PV nommées comme chez eux | On sait ce qu'est une PV, un IOC, un record, une alarme | 1 WE |
| 2 | **Historian + logbook** — collecteur Channel Access → PostgreSQL/TimescaleDB, API REST OpenAPI | On répond à leur manque déclaré (pas de logbook ni d'historian intégrés) | 1–1,5 WE |
| 3 | **Modèle IA** — détection d'anomalie / dérive multi-canaux, entraîné sur l'historian, tracé MLflow + DVC | On sait faire de la ML reproductible sur de la donnée d'exploitation | 1,5 WE |
| 4 | **Mise en production** — service d'inférence qui *lit* des PV et *écrit* des PV (`:PRED`, `:ANOM`, `:HEALTH`), Docker, CI GitLab, tests, supervision | **Le cœur du dossier** : le modèle est un équipement du système de contrôle | 2 WE |
| 5 | **IHM Flutter + synoptique SVG** — vue opérateur, alarmes IA, entrées de logbook | On reproduit délibérément leur architecture IHM | 1,5 WE |
| 6 | **FAIR + doc bilingue + démo** — métadonnées, vocabulaire contrôlé, README et notice FR/EN, démo de 10 min | On sait documenter et transmettre | 1 WE |

Bonus si le temps le permet : apprentissage fédéré (Flower) entre deux « sites »
simulés — l'annonce le mentionne, une maquette de 200 lignes suffit à en parler.

## Principe directeur

À chaque étape, la question est : *« qu'est-ce qui casse quand ça tourne en vrai ? »*
Un modèle qui tourne est facile ; un modèle qui tourne le mardi à 3 h du matin quand
un opérateur retouche un réglage, c'est le métier visé.
