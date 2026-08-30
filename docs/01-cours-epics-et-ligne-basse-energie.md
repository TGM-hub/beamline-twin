# Étape 1 — Cours : la ligne basse énergie et le modèle EPICS

*Séance 1. Lecture ~15 min. À lire avant d'écrire une ligne de code.*

---

## 1. Point de situation

Le dépôt est vide. On part de zéro. Aujourd'hui on installe le socle : comprendre
la forme réelle de la donnée d'un accélérateur, puis écrire le simulateur qui la
produit et l'IOC EPICS qui la publie. Tout le reste — historian, modèle, IHM —
se branchera dessus.

---

## 2. Le morceau de machine qu'on va jumeler

On ne modélise pas SPIRAL2 en entier. On prend **le premier segment**, celui qui est
le plus simple à comprendre et le plus riche en signaux : la **ligne basse énergie
(LBE)**, entre la source d'ions et l'entrée du RFQ.

```
   [Source ECR]──[Extraction HT]──[SOL-01]──[Dipôle 90°]──[SOL-02]──[Fentes]──[Cage de Faraday]
        │              │             │           │            │        │            │
      HF, gaz      U (kV)         I (A)      B (T) / I (A)   I (A)   ouverture   I (µA)
                       └── ACCT-01 (intensité) ──┘        └── BPM-01 (x, y) ──┘
                                    └── jauges de vide (mbar) ──┘
```

**Ce qui se passe physiquement, au minimum crédible :**

- **La source ECR** (*Electron Cyclotron Resonance*) confine un plasma dans un champ
  magnétique et le chauffe avec une onde HF (14 GHz). Les collisions électroniques
  arrachent des électrons aux atomes : on obtient des **ions multichargés**. Trois
  réglages dominent : la puissance HF, le débit de gaz, les courants des bobines.
  Une source ECR est un objet instable — elle dérive sur des heures, elle a des
  « sauts de mode ». C'est exactement ce qu'un modèle de détection d'anomalie
  doit apprendre à distinguer d'une vraie panne.

- **L'extraction** applique une haute tension `U` (quelques dizaines de kV). L'ion
  gagne l'énergie `E = q·U`. À la sortie, on n'a pas *un* faisceau mais un **mélange**
  d'espèces (différents A et différents Q).

- **Le dipôle d'analyse** courbe les trajectoires. Un aimant de champ `B` et de rayon
  `ρ` ne laisse passer qu'une seule **rigidité magnétique** `Bρ = p/q`. Comme
  `p ∝ √(A·U·Q)`, on a `Bρ ∝ √(A/Q · U)` : **régler le dipôle, c'est choisir un
  rapport A/Q**. Tout le reste va dans les fentes. C'est le geste central de la LBE.

- **Les solénoïdes** refocalisent. À basse énergie on utilise des solénoïdes plutôt
  que des quadripôles : le faisceau est peu rigide et la **charge d'espace** (le
  faisceau, chargé, se repousse lui-même) est forte. Conséquence importante pour un
  jumeau : **la transmission n'est pas linéaire en intensité**. Doubler le courant de
  source ne double pas le courant en bout de ligne.

- **Les diagnostics.** `ACCT` (transformateur de courant) mesure l'intensité **sans
  intercepter** le faisceau — il peut donc rester en permanence. La **cage de Faraday**
  est interceptive : elle arrête le faisceau, on ne s'en sert qu'au réglage. Le `BPM`
  donne la **position** (x, y) du barycentre. La **transmission** = rapport de deux
  ACCT ; la différence, c'est de la **perte de faisceau**, donc de l'activation et de
  l'échauffement : c'est ce qui déclenche les sécurités.

- **Le vide** : 10⁻⁷–10⁻⁸ mbar. Une remontée de vide, et les ions multichargés se
  recombinent sur le gaz résiduel → la transmission chute. Un signal lent, corrélé,
  parfait pour un modèle multi-canaux.

**Ce qu'on assume de simplifier :** pas de dynamique faisceau, pas d'enveloppe, pas de
particules. On écrit des lois de comportement paramétrées (gaussiennes autour d'un
optimum, dérives lentes, bruit). L'effort du projet va dans l'infrastructure, pas dans
la physique — et on l'écrit noir sur blanc dans le README, parce qu'un jury préfère une
simplification assumée à une prétention non tenue.

---

## 3. EPICS : le bon modèle mental

EPICS n'est pas une base de données ni un broker de messages. C'est un **espace de noms
distribué de canaux**. Il faut se défaire du réflexe « table ».

### La PV

Une **PV** (*Process Variable*, variable de procédé) est un **canal nommé**. Ce n'est
pas un nombre : c'est un nombre **plus** un horodatage, une unité, une sévérité
d'alarme et un état.

```
LBE:SOL-01:I_RB   =  118.42   A   2026-08-30 09:14:22.318   NO_ALARM / NO_STATUS
```

SPIRAL2 en compte **~80 000**, pour ~3 000 équipements. Aucune n'est jointe à une
autre : il n'y a pas de clé étrangère, il n'y a que des noms. **La convention de
nommage *est* le schéma.** La nôtre :

```
<LIGNE> : <ÉQUIPEMENT>-<NUMÉRO> : <SIGNAL>
  LBE   :      SOL     -   01   :   I_RB
```

Suffixes qu'on s'impose, et qui comptent plus qu'on ne croit :

| Suffixe | Sens |
|---|---|
| `:I_SP` | *setpoint* — la **consigne** demandée par l'opérateur |
| `:I_RB` | *readback* — la **mesure** réelle renvoyée par l'équipement |
| `:STATE` | état discret (`OFF`, `ON`, `FAULT`) |
| `:ITF` | intensité mesurée (µA) |
| `:X`, `:Y` | position (mm) |

> **Le piège n°1 en ML sur données d'accélérateur** : confondre `_SP` et `_RB`.
> La consigne est une décision humaine, la mesure est un état de la machine. Un
> modèle entraîné sur les consignes apprend le comportement des opérateurs, pas
> celui de la machine. On y reviendra à l'étape 3.

### L'IOC et les records

Un **IOC** (*Input/Output Controller*) est le processus qui sert un lot de PV. Chez
eux, il tourne sur un châssis proche du matériel. Chez nous, ce sera un processus
Python : un **soft IOC** — même protocole, pas de matériel derrière.

Dans un IOC, chaque PV est portée par un **record**, une petite machine à états
typée. Les types qu'on croisera : `ai` (analogique en entrée), `ao` (analogique en
sortie), `bi`/`bo` (binaire), `mbbi`/`mbbo` (multi-états), `calc`, `waveform`.

Un record a des **champs**, adressés `PV.CHAMP`. Les essentiels :

| Champ | Rôle |
|---|---|
| `.VAL` | la valeur (implicite si on ne précise rien) |
| `.EGU` | l'unité (*engineering units*) |
| `.HIHI` `.HIGH` `.LOW` `.LOLO` | les quatre seuils d'alarme |
| `.HHSV` `.HSV` `.LSV` `.LLSV` | la sévérité associée à chaque seuil |
| `.SEVR` | sévérité courante : `NO_ALARM`, `MINOR`, `MAJOR`, `INVALID` |
| `.STAT` | cause de l'alarme (`HIHI`, `READ`, `TIMEOUT`…) |
| `.SCAN` | quand le record est traité : `.1 second`, `1 second`, `I/O Intr`, `Passive` |
| `.MDEL` | *monitor deadband* — variation minimale pour notifier les clients |
| `.ADEL` | *archive deadband* — variation minimale pour archiver |

**Retenir `.MDEL` et `.ADEL`.** Ce sont eux qui expliquent pourquoi la donnée
d'accélérateur n'est pas une série régulière : un canal stable n'émet rien pendant
des minutes, puis dix points en deux secondes quand quelqu'un touche un réglage.

### Les protocoles

- **Channel Access (CA)** — historique, EPICS 3. Découverte par diffusion UDP
  (port 5064), transport TCP. C'est ce qu'on utilisera.
- **PV Access (PVA)** — EPICS 7. Structures typées (`NTScalar`, `NTTable`), meilleur
  débit. À mentionner, pas indispensable ici.

Les verbes du métier, à connaître par cœur :

```
caget    LBE:ACCT-01:ITF        # lire une fois
caput    LBE:SOL-01:I_SP 120    # écrire une consigne
camonitor LBE:ACCT-01:ITF       # s'abonner : le serveur pousse à chaque changement
cainfo   LBE:ACCT-01:ITF        # métadonnées du canal
```

`camonitor` est le point important : **EPICS est un système à souscription, pas à
interrogation**. On ne sonde pas la machine, on s'abonne et elle pousse. Le collecteur
de l'étape 2 sera un abonné, pas un scheduler.

---

## 4. Pourquoi cette donnée casse les habitudes de data analyst

Quatre conséquences directes, à garder en tête jusqu'à l'étape 4 :

1. **Pas de table, pas d'index commun.** N canaux, N horodatages différents. Toute
   « ligne » de dataset est une **reconstruction** de votre part. Le choix de la
   méthode d'alignement (dernière valeur connue, fenêtre, rééchantillonnage) est une
   décision de modélisation, pas un détail de préparation.
2. **Échantillonnage piloté par l'événement.** L'absence de point n'est pas une donnée
   manquante : c'est l'information « rien n'a bougé ». Un `dropna()` détruit cette
   information ; un `forward-fill` est ici la sémantique correcte.
3. **Les seuils existent déjà.** La machine a ses propres alarmes. Un modèle qui
   réapprend `.HIHI` est inutile. La valeur ajoutée est ailleurs : voir venir la dérive
   **avant** le seuil, ou détecter une **combinaison** anormale de canaux tous dans
   leurs limites.
4. **Il y a un humain dans la boucle.** Un changement de consigne n'est pas une
   anomalie, c'est une intervention. Sans logbook, impossible de faire la différence —
   d'où l'étape 2, et d'où la première puce de leur annonce.

---

## 5. Lexique FR / EN

| Français | English | Note |
|---|---|---|
| variable de procédé | process variable (PV) | le canal nommé |
| consigne | setpoint | `_SP` |
| mesure, recopie | readback | `_RB` |
| ligne de faisceau | beamline | |
| ligne basse énergie | low energy beam line (LEBT) | LBE chez SPIRAL2 |
| source d'ions | ion source | ECR ici |
| aimant de courbure, dipôle | dipole, bending magnet | |
| solénoïde | solenoid | focalisation basse énergie |
| quadripôle | quadrupole | focalisation haute énergie |
| rigidité magnétique | magnetic rigidity | `Bρ` |
| charge d'espace | space charge | |
| transmission | transmission | rapport de deux intensités |
| perte de faisceau | beam loss | |
| cage de Faraday | Faraday cup | interceptif |
| transformateur d'intensité | current transformer (ACCT / DCCT) | non interceptif |
| profileur | profile monitor | |
| fentes | slits | |
| jauge à vide | vacuum gauge | |
| bande morte | deadband | `.MDEL` / `.ADEL` |
| seuil d'alarme | alarm limit | `.HIHI` etc. |
| sévérité | severity | `.SEVR` |
| horodatage | timestamp | |
| réglage (de machine) | machine tuning | |
| cahier de quart, journal de bord | logbook | ce qui leur manque |
| archiveur | archiver / historian | ce qui leur manque aussi |
| synoptique | synoptic view | leur IHM Flutter + SVG |

---

## 6. Ce qu'on code juste après

1. `sim/beamline.py` — le modèle de comportement : source qui dérive, transmission
   gaussienne autour des optima, effet du vide, bruit. Pur Python, testable, sans
   EPICS.
2. `config/pv_map.yaml` — la liste déclarative des ~70 PV : nom, unité, type, seuils,
   description. **Le nommage se décide ici, une fois pour toutes.**
3. `sim/ioc.py` — le soft IOC (`caproto`) qui expose ces PV, accepte les `caput` sur
   les consignes et republie les mesures à 10 Hz.
4. `tests/` — la transmission chute quand on désaccorde un solénoïde, l'alarme passe
   en `MAJOR` au-delà de `.HIHI`, un `caput` sur `_SP` bouge bien `_RB`.
5. Vérification : `camonitor` sur trois canaux pendant qu'on désaccorde la ligne à la
   main. Si on voit la transmission tomber en direct, l'étape 1 est finie.

### Choix technique retenu

**`caproto`**, bibliothèque Python pure, plutôt qu'EPICS base dans Docker :
`pip install caproto` et ça tourne sous Windows sans compilation. C'est un **vrai
serveur Channel Access** — `caget`, `camonitor` et Phoebus s'y connectent sans savoir
la différence. Docker reviendra à l'étape 4, là où il est vraiment justifié
(l'historian, le service d'inférence, la CI).
Chaîne validée en amont de la séance : soft IOC caproto + client CA, aller-retour OK.

---

## 7. Pour aller plus loin (optionnel)

- *EPICS Process Database Concepts* — la référence sur les records et leurs champs.
- Actes ICALEPCS du GANIL sur le système de contrôle SPIRAL2 (base PostgreSQL ~60
  tables, IHM Flutter + SVG, web services JAX-RS/OpenAPI, absence de logbook et
  d'historian intégrés).
- Documentation `caproto` : *Writing an IOC with pvproperty*.
