# beamline-twin

Jumeau numérique minimal d'un segment de ligne d'accélérateur, avec un modèle IA
branché sur le système de contrôle EPICS — pas dans un notebook.

Projet d'apprentissage et de démonstration, construit en vue du poste
« Ingénieur support logiciel IA » au GANIL (projet TwinRISE).

> **Simplifications assumées.** La physique est réduite à des lois de comportement
> paramétrées (dérives, optima gaussiens, bruit), calées sur le profil statistique
> d'un vrai jeu de données d'accélérateur. L'effort porte sur l'infrastructure :
> système de contrôle, archivage, reproductibilité, mise en production, IHM.

## État

| Jalon | Sujet | État |
|---|---|---|
| 0 | Calibration sur données réelles, simulateur, soft IOC | ✅ 77 PV, 25 tests |
| 1 | Chaîne complète : collecteur → modèle → PV `:ANOM` → page | 🚧 |
| 2 | Historian TimescaleDB, logbook, API OpenAPI | ⬜ |
| 3 | Le vrai modèle : MLflow, DVC, validation externe | ⬜ |
| 4 | Industrialisation : service d'inférence, CI, supervision | ⬜ |
| 5 | IHM : synoptique SVG, puis Flutter | ⬜ |
| 6 | FAIR, documentation bilingue, démonstration | ⬜ |

## Démarrage

**Terminal 1 — la machine.** Il doit rester ouvert.

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
pip install -r requirements.txt

pytest tests -q                   # 25 tests
python -m sim.pvmap               # la base de PV et ses contrôles
python -m sim.ioc --vitesse 300   # six heures de machine en une minute
```

**Terminal 2 — le client Channel Access.**

```bash
python -m caproto.commandline.monitor LBE:ACCT-01:ITF LBE:MACH-01:TRANS LBE:VAC-02:P
python -m caproto.commandline.put LBE:SOL-01:I_SP 150      # désaccorde la ligne
python -m caproto.commandline.put SIM:FUITE_VIDE 1.7e-7    # installe une fuite de vide
```

`caget` / `caput` / `camonitor` sont les exécutables d'EPICS base, qui ne sont pas
installés ici. caproto fournit les mêmes clients en Python pur — même protocole,
même usage contre un IOC réel.

## Documentation

- [`docs/00-feuille-de-route.md`](docs/00-feuille-de-route.md) — le plan et ses priorités
- [`docs/01-cours-epics-et-ligne-basse-energie.md`](docs/01-cours-epics-et-ligne-basse-energie.md) — la ligne basse énergie et le modèle EPICS
- [`docs/01b-convention-de-nommage.md`](docs/01b-convention-de-nommage.md) — la règle de nommage et le journal de revue de la base de PV
- [`docs/02-cours-historian-et-logbook.md`](docs/02-cours-historian-et-logbook.md) — archivage et journal de bord
- [`docs/03-profil-boostr.md`](docs/03-profil-boostr.md) — ce qu'une vraie machine nous apprend
- [`docs/04-simulateur-et-ioc.md`](docs/04-simulateur-et-ioc.md) — le simulateur, le soft IOC, et les bugs que les tests ont trouvés
- [`docs/fiches-revision.md`](docs/fiches-revision.md) — 28 questions/réponses
- [`docs/journal.md`](docs/journal.md) — cahier de bord des séances
