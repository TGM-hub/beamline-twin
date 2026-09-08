# beamline-twin — feuille de route

Objectif : un jumeau numérique minimal d'un segment de ligne d'accélérateur, avec un
modèle IA **réellement branché sur le système de contrôle**, pas dans un notebook.

## Le calendrier réel

Le dossier de candidature est parti. Le 5 novembre 2026 est la clôture des
candidatures, pas l'échéance de ce projet. **L'échéance, c'est l'audition** — attendue
entre mi-novembre et mi-décembre, la prise de poste étant fixée au 1ᵉʳ janvier 2027.
Soit une dizaine de week-ends utiles à ~8 h, plus une réserve.

## Le principe : une tranche verticale d'abord

On ne construit pas les six étapes l'une après l'autre. Ce plan-là finit toujours de la
même façon : quatre couches superbes et rien qui tourne de bout en bout le jour de
l'entretien.

On construit d'abord une **chaîne complète et laide**, puis on l'épaissit. À partir du
jalon 1, il existe une démo à tout instant. Si le temps manque, elle est moins belle —
elle n'est jamais absente.

C'est aussi la discipline attendue dans le poste : livrer une chaîne complète avant de
l'optimiser.

## Jalons

| # | Quand | Contenu | Sortie visible |
|---|---|---|---|
| **0** | semaine du 8 sept | Calibration sur données réelles (BOOSTR, Fermilab), simulateur de la LBE, soft IOC caproto | 77 canaux qui vivent, `camonitor` répond |
| **1** | 12–13 sept | **La tranche mince** : collecteur CA → stockage → modèle bête (seuil glissant) → PV `:ANOM` réécrite sur le bus → page HTML | **Bout en bout. Laid, mais complet.** |
| **2** | 19–20 sept | Historian réel (TimescaleDB), API FastAPI/OpenAPI, logbook et capture automatique, `docker compose` | La donnée s'archive et se raconte |
| **3** | 26–27 sept | Le vrai modèle : détection d'anomalie multi-canaux, MLflow, DVC, validation externe sur BOOSTR | Un modèle traçable et reproductible |
| **4** | 3–4 oct | Industrialisation : service d'inférence propre, CI, tests, supervision, rejeu d'archive | **Le cœur du dossier** |
| **5** | 10–11 et 17–18 oct | IHM : synoptique SVG. HTML d'abord, Flutter ensuite si l'avance le permet | Un opérateur peut lire la sortie du modèle |
| **6** | 24–25 oct, 31 oct–1ᵉʳ nov | FAIR, documentation bilingue, notice d'exploitation, répétition de la démo | Le dossier est transmissible |
| **R** | nov–déc | Réserve : marge, répétitions, apprentissage fédéré en bonus | — |

## La démo de dix minutes

C'est elle qu'on protège avant tout le reste. Tout ce qui ne sert pas ces six gestes est
du bonus.

1. `docker compose up` — la ligne démarre
2. le synoptique affiche les 77 canaux en vie
3. on injecte une fuite de vide sur `VAC-02`
4. la sortie `:ANOM` du modèle part **avant** le déclenchement du seuil opérateur
5. une entrée de logbook s'est créée toute seule
6. on remonte au run MLflow qui a produit le modèle déployé

## Deux règles de priorité

**Le déploiement passe avant le modèle.** Un modèle médiocre correctement branché sur le
bus bat un excellent modèle dans un notebook — pour ce poste précisément. Si le jalon 4
est menacé, on sacrifie le jalon 3, jamais l'inverse.

**L'IHM est la variable d'ajustement.** C'est ce qui coûte le plus cher par unité de
conviction. La version HTML suffit à la démo ; Flutter et le synoptique SVG sont un
bonus qui parle à leur architecture, pas une condition.

## Données réelles

Le simulateur ne remplace pas des données réelles, il fait ce qu'elles ne peuvent pas
faire : fournir un bus vivant sur lequel écrire, des pannes provoquées avec leur vérité
terrain, et un logbook aligné. Les données réelles font l'inverse — elles donnent des
ordres de grandeur qu'on n'invente pas.

On utilise donc **BOOSTR** (Fermilab, Booster à 15 Hz, lectures *et* consignes, CC-BY)
à deux endroits : pour calibrer les statistiques du simulateur avant de l'écrire (bruit,
échelles de dérive, irrégularité d'échantillonnage), et comme jeu de validation externe
au jalon 3. Réponse d'avance à l'objection « vos données sont fausses ».

> Zenodo n'est pas joignable depuis la session : le fichier est à télécharger à la main
> depuis <https://zenodo.org/records/4088982> et à déposer dans `data/boostr/`
> (620 Mo, ignoré par git).
