# beamline-twin

Jumeau numérique minimal d'un segment de ligne d'accélérateur, avec un modèle IA
branché sur le système de contrôle EPICS — pas dans un notebook.

Projet d'apprentissage et de démonstration, construit en vue du poste
« Ingénieur support logiciel IA » au GANIL (projet TwinRISE).

> **Simplifications assumées.** La physique est réduite à des lois de comportement
> paramétrées (dérives, optima gaussiens, bruit). L'effort porte sur l'infrastructure :
> système de contrôle, archivage, reproductibilité, mise en production, IHM.

## État

| Étape | Sujet | État |
|---|---|---|
| 1 | Simulateur + IOC EPICS | 🚧 en cours |
| 2 | Historian + logbook | ⬜ |
| 3 | Modèle IA (MLflow / DVC) | ⬜ |
| 4 | Service d'inférence sur le bus CA | ⬜ |
| 5 | IHM Flutter + synoptique SVG | ⬜ |
| 6 | FAIR, documentation bilingue, démo | ⬜ |

Feuille de route détaillée : [`docs/00-feuille-de-route.md`](docs/00-feuille-de-route.md).

## Démarrage rapide

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
python -m sim.ioc             # démarre le soft IOC
# dans un autre terminal :
caproto-monitor LBE:ACCT-01:ITF
```

## Documentation

- [`docs/00-feuille-de-route.md`](docs/00-feuille-de-route.md) — le plan
- [`docs/01-cours-epics-et-ligne-basse-energie.md`](docs/01-cours-epics-et-ligne-basse-energie.md) — cours de l'étape 1
- [`docs/journal.md`](docs/journal.md) — cahier de bord des séances
