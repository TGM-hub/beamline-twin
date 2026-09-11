# Étape 1b — La convention de nommage des PV

*À lire avant de relire `config/pv_map.yaml`. ~10 min.*

---

## Pourquoi ce document existe

Chez eux, il y a **80 000 PV** et **aucune jointure**. Pas de clé étrangère, pas de
schéma relationnel entre canaux : seulement des noms. Quand un opérateur cherche la
température de la bobine du dipôle à 3 h du matin, il ne fait pas une requête — il
**devine le nom**. Et il doit tomber juste du premier coup.

C'est pour ça que la convention de nommage est la décision la plus structurante du
projet. Elle est aussi la plus difficile à corriger après coup : une PV renommée, ce
sont des IHM, des scripts, des archives et des configurations qui cassent en silence.
Dans un vrai système de contrôle, **on ne renomme pas**. On vit avec.

## La règle

```
<LIGNE> : <ÉQUIPEMENT>-<INSTANCE> : <SIGNAL>[_SP|_RB]

LBE     :      SOL      -01      :   I    _RB
 │              │        │           │     │
 │              │        │           │     └── nature : consigne ou mesure
 │              │        │           └──────── grandeur physique, elle seule
 │              │        └──────────────────── instance (voir ci-dessous)
 │              └───────────────────────────── type d'équipement, 3 à 4 lettres
 └──────────────────────────────────────────── segment de machine
```

**L'instance est un numéro à deux chiffres quand les exemplaires se distinguent par
leur position le long de la ligne** — `SOL-01` puis `SOL-02`, le numéro dit l'ordre.
**Elle est un mnémonique court quand la distinction est fonctionnelle et non
positionnelle** : les deux bobines de la source ECR sont `COIL-INJ` et `COIL-EXT`,
côté injection et côté extraction. Les numéroter `01` et `02` obligerait à mémoriser
une correspondance arbitraire ; c'est le genre de dette qu'un opérateur paie à 3 h du
matin.

Trois segments, jamais plus, jamais moins. Un nom se lit de gauche à droite comme on
descend dans la machine : *où* → *quoi* → *quelle grandeur*.

### Les six décisions prises, et pourquoi

**1. Les noms ne sont pas écrits à la main.** `config/pv_map.yaml` décrit des
**équipements** et leurs **signaux** ; `sim/pvmap.py` en dérive les noms. Personne ne
peut inventer un nom hors règle, parce qu'il n'y a pas d'endroit où le taper. C'est
exactement le rôle de leur base PostgreSQL de configuration : on décrit le matériel, le
nommage en découle.

**2. `_SP` et `_RB` sont générés ensemble ou pas du tout.** Une nature `pair` produit
toujours les deux. Un test le vérifie. Conséquence : il est structurellement impossible
d'avoir une consigne sans sa mesure, donc impossible de perdre la trace de l'écart
entre ce qui a été demandé et ce que la machine a fait.

**3. Une consigne ne porte jamais de seuil d'alarme.** Le code l'impose (`alarm={}` si
le suffixe est `_SP`). Une consigne est une **décision humaine** : elle peut être
mauvaise, elle n'est jamais « en alarme ». C'est la machine qu'on surveille, pas
l'opérateur. Corollaire, à retenir pour l'étape 3 : `_SP` et `_RB` ne se traitent pas de
la même façon dans un modèle — l'un est une entrée exogène, l'autre une observation.

**4. L'instance est toujours là**, même quand l'équipement est unique (`DIP-01`,
`MACH-01`). Le jour où une deuxième source arrive, rien ne bouge. Un nom sans instance
est une dette qu'on paie deux ans plus tard.

**4bis. Un sous-équipement devient un équipement.** La source ECR contient deux
bobines, chacune avec son alimentation, sa consigne et son défaut. Les faire tenir dans
le champ `SIGNAL` donnait `LBE:SRC-01:COIL_EXT_I_RB` — quatre concepts empilés dans un
segment censé n'en porter qu'un. Elles sont donc des équipements de plein droit :
`LBE:COIL-INJ:I_RB`. La règle des trois segments tient, au prix d'un lien
source↔bobines qui vit dans le YAML et non dans le nom. C'est un arbitrage : la
lisibilité du nom contre l'expressivité de la hiérarchie. Le GANIL a tranché dans
l'autre sens — leurs noms sont plus longs et portent bâtiment et sous-système — parce
qu'à 80 000 canaux et 3 000 équipements, la hiérarchie ne tient plus dans un fichier
qu'on lit d'un bloc.

**5. Les grandeurs calculées sont des PV comme les autres.** `LBE:MACH-01:TRANS` et
`:LOSS` ne correspondent à aucun matériel — elles sont produites par l'IOC à partir des
deux ACCT. C'est volontaire et c'est **le point d'ancrage de l'étape 4** : quand le
modèle IA écrira `LBE:MACH-01:ANOM` et `:HEALTH`, il ne fera rien de plus exotique que
ce que fait déjà le calcul de transmission. **Le modèle devient un équipement de la
ligne, pas un service à côté.**

**6. Chaque PV porte une description en français *et* en anglais.** Un test échoue si
l'une des deux manque. La documentation bilingue est une exigence de l'annonce ; la
construire au fil de l'eau coûte dix secondes par PV, la rattraper à la fin coûte un
week-end.

### Un piège rencontré en écrivant le fichier

La première version nommait le A/Q visé `AQ_SET`, qui devenait `LBE:MACH-01:AQ_SET_SP`.
Deux fois le même sens dans un nom : `SET` et `_SP`. Le suffixe **est** la nature du
signal, le radical ne doit porter que la grandeur physique. Corrigé en `AQ`, donc
`LBE:MACH-01:AQ_SP`. Ce genre de redondance passe inaperçu à l'unité et devient
insupportable à 80 000.

## L'état de la base

```
77 PV sur 18 équipements — 15 consignes, 43 mesures, 17 états, 1 compteur, 1 contexte
20 PV portent des seuils d'alarme — 11 protection, 9 exploitation
domaines — 51 equipement, 11 faisceau, 6 procede, 5 derive, 4 contexte
```

Pour la voir en entier, sans rien installer d'autre que `pyyaml` :

```bash
python -m sim.pvmap        # liste, statistiques et contrôles de cohérence
pytest tests -q            # 6 tests figent le contrat
```

---

## Ce que j'attends de ta relecture

Ne relis pas le YAML comme du code : relis-le comme un **opérateur** qui doit s'en
servir, et comme un **modélisateur** qui devra l'exploiter. Sept questions, dans
l'ordre :

1. **Le test de l'opérateur.** Prends trois PV au hasard. Sais-tu dire ce qu'elles
   mesurent sans lire la description ? Si non, le nom est mauvais, pas ta mémoire.

2. **Le test de la panne.** Le vide remonte lentement sur `VAC-02` pendant six heures.
   Quelles PV bougent, dans quel ordre ? Est-ce que la base permet de raconter cette
   histoire, ou est-ce qu'il manque un canal ?

3. **Ce qui manque pour l'étape 3.** Un modèle de détection d'anomalie doit distinguer
   « la machine dérive » de « quelqu'un a changé un réglage ». Avec ces 69 PV, est-ce
   possible ? Qu'est-ce qui manque encore — et faut-il que ce soit une PV, ou est-ce le
   rôle du logbook de l'étape 2 ?

4. **Les seuils.** 17 PV surveillées sur 69. Est-ce trop, pas assez ? En regardant
   `MACH-01:TRANS` (`LOW` à 85 %, `LOLO` à 70 %) : est-ce que ces valeurs racontent une
   machine plausible, ou est-ce que je les ai posées au hasard ? *(Indice : je les ai
   posées au hasard. C'est à toi de décider ce qu'elles doivent valoir — et c'est
   exactement le genre de chiffre qu'on va chercher auprès d'un exploitant.)*

5. **Les états.** `MACH-01:MODE` vaut `ARRET`, `REGLAGE` ou `PRODUCTION`. Est-ce
   suffisant pour étiqueter des données d'entraînement ? Que fait-on d'un réglage
   interrompu à la moitié ?

6. **Ce qui est en trop.** Y a-t-il des PV que tu ne saurais pas justifier en entretien ?
   Une base minimale et défendable vaut mieux qu'une base large et floue.

7. **La règle elle-même.** Trois segments, est-ce que ça tient ? Chez eux les noms sont
   plus longs et portent le bâtiment et le sous-système. On simplifie sciemment — sais-tu
   dire pourquoi, et sous quelle contrainte ça casserait ?

Laisse tes réponses en **commentaires de la pull request**, ligne par ligne quand ça
s'y prête. Une remarque par question suffit — ce qui compte, c'est d'avoir une opinion
argumentée sur chacune. C'est cette conversation-là qu'on aura à l'entretien.


---

## Journal de la revue

### Question 1 — le test de l'opérateur — 8 septembre 2026

Trois PV soumises à froid, sans accès au YAML.

| PV | Lue comme | Verdict |
|---|---|---|
| `LBE:SRC-01:COIL_EXT_I_RB` | « isolation, ou montage d'essai » | **nom défectueux — corrigé** |
| `LBE:DIP-01:AQ` | non reconnue | nom conservé |
| `LBE:MACH-01:LOSS` | « une alarme importante » | nom validé |

**`COIL_EXT`** : `EXT` se lit *externe* autant qu'*extraction*, et le champ `SIGNAL`
empilait sous-équipement, instance, grandeur et nature. Corrigé en `LBE:COIL-EXT:I_RB`
(décision 4bis ci-dessus).

**`AQ`** : le nom est conservé. La lecture a échoué par méconnaissance du domaine, pas
par défaut de nommage — un opérateur d'accélérateur raisonne en A/Q en permanence. Un
nom se juge par rapport à son utilisateur ; confondre « je ne comprends pas » et « c'est
mal nommé » ferait renommer la moitié de la base au profit de personne.

**`LOSS`** : bonne réponse à la question des 3 h du matin, pour la bonne raison — la
perte de faisceau est un enjeu de radioprotection (échauffement, activation), pas de
rendement. Nuance de vocabulaire relevée au passage : `LOSS` est une mesure qui *porte*
des seuils, pas une alarme. L'alarme est un état du record (`.SEVR`), il n'existe pas de
PV d'alarme à côté des mesures.

### Question 2 — le test de la panne — 8 septembre 2026

Scénario soumis : montée lente de `VAC-02:P` sur six heures, sans intervention.

**Ce que la revue a établi.** Bougent : `VAC-02:P`, puis `ACCT-02:ITF`, `MACH-01:TRANS`
et `MACH-01:LOSS`. Ne bougent pas : `ACCT-01:ITF` (en amont de la perte),
`BPM-02:X` et `PROF-01:SIGX` (le faisceau transmis reste centré, il est seulement moins
nombreux), et surtout `SRC-01:HT_I`, `DIP-01:B`, `SOL-01:I_RB`.

**Distinction dégagée, et qui vaut pour tout le projet :**

> **Canaux d'équipement** contre **canaux de faisceau.** Un incident faisceau ne se
> propage que dans les seconds. Un canal d'équipement — le champ d'un aimant, le courant
> d'une alimentation — ne bouge que si quelqu'un ou un défaut agit sur l'équipement.
> Le champ d'un dipôle suit son alimentation, pas le faisceau qui le traverse.

Conséquence pour l'étape 3 : la causalité est **à sens unique et connue d'avance**. Une
corrélation entre `SOL-01:I_RB` et `MACH-01:TRANS` ne peut aller que du solénoïde vers
la transmission. C'est une contrainte structurelle offerte par la topologie de la
machine, que peu de jeux de données industriels fournissent.

**Piège relevé :** `ACCT-02:ITF`, `TRANS` et `LOSS` ne se succèdent pas — c'est le même
événement, les deux dernières étant calculées à partir de la première. Un modèle
multi-canaux y verra trois confirmations indépendantes là où il n'y a qu'un seul témoin.
Les canaux dérivés devront être marqués comme tels avant tout entraînement.

**Manques identifiés, et suites données :**

| Manque | Décision |
|---|---|
| Comparer les trois jauges pour localiser (local ou pompage) | déjà possible, `VAC-01/02/03` existent |
| Écarter une dérive du débit de gaz | déjà possible, `SRC-01:GAS_Q_RB` existe |
| Position des vannes de secteur | **ajouté** — `LBE:VAC-0N:VALVE` |
| Séparer une fuite d'un dégazage | **ajouté** — `LBE:VAC-0N:T`, température de chambre |
| Savoir si quelqu'un a ouvert quelque chose il y a six heures | aucune PV ne le dira — c'est l'objet de l'étape 2 |

La base passe de 69 à **75 PV**. Le scénario de la fuite est désormais racontable de
bout en bout : donc simulable à l'étape 1, et détectable à l'étape 3.

**À noter :** l'idée d'une *pression attendue* à comparer à la pression observée, sortie
de la revue, n'est pas un canal de mesure mais une **sortie de modèle**. Elle sera
publiée à l'étape 4 sous `LBE:VAC-02:P_PRED`, à côté de la mesure. C'est le motif
directeur du projet — le modèle publie ses sorties comme n'importe quel équipement.

### Question 3 — les étiquettes — 8 septembre 2026

Question posée : à quoi sert le logbook, si les quinze `_SP` disent déjà quand quelqu'un
est intervenu ?

**Deux points dégagés en revue, à garder pour l'entretien.**

*Un changement de consigne sans effet est un résultat.* Le même « rien ne s'est passé »
recouvre trois situations distinctes : le réglage était dans une zone plate (le
paramètre n'a pas d'influence à cet endroit), l'actionneur a suivi mais pas le faisceau
(`_RB` bouge, `TRANS` non → défaut en aval), ou l'actionneur n'a pas suivi (`_SP` bouge,
`_RB` non → panne d'alimentation).

*Une consigne est une intervention, pas une observation.* C'est de l'expérimentation.
Une fuite de vide et un désaccord de solénoïde produisent la même chute de transmission
dans des données observationnelles ; seul le fait que quelqu'un ait **bougé** le
solénoïde permet d'attribuer l'effet. Les `_SP` fournissent donc des milliers de petites
expériences déjà faites et déjà horodatées — un actif rare pour un jeu de données
industriel.

**Ce que les `_SP` ne diront jamais.** Ouvrir une vanne, changer une bouteille de gaz,
étuver une chambre : des actes physiques sans consigne. Remplacer une alimentation ou
recalibrer une sonde : consignes identiques avant et après, machine différente. Décider
de **ne rien faire** pendant une dérive : une décision invisible. Et l'instant où
l'opérateur juge le réglage terminé et accepté — cette frontière définit ce que
« nominal » veut dire à l'entraînement, et aucune PV ne la porte.

Une consigne dit **quoi**, jamais **pourquoi**, jamais **si le résultat a été accepté**.
D'où `ts_debut`/`ts_fin` dans le schéma du logbook — une intervention a une durée
qu'aucune transition ne donne — et d'où la capture automatique, qui transforme chaque
changement de consigne en expérience exploitable sans rien demander à personne.

**Ajouts décidés :**

- **`LBE:MACH-01:SPECIES`** — l'espèce ionique produite. `AQ_SP` à 3,2 peut correspondre
  à plusieurs ions ; changer d'espèce change tout le comportement de la ligne sans
  qu'aucune consigne ne bouge. Sans ce canal, aucune campagne n'est comparable à une
  autre. La base passe à **76 PV**.
- **Le champ `domain`** sur chaque signal, avec `from:` pour les canaux dérivés. Trois
  tests l'imposent. Répartition : 51 `equipement`, 11 `faisceau`, 6 `procede`,
  4 `derive`, 4 `contexte`.

Ce dernier chiffre mérite d'être regardé en face : **onze canaux de faisceau seulement**.
C'est sur eux, et sur les six canaux de procédé, que porte toute la détection d'anomalie.
Les cinquante et un canaux d'équipement sont des entrées, pas des observations —
les confondre reviendrait à demander au modèle de prédire ce que les opérateurs vont
faire.

### Question 4 — les seuils — 8 septembre 2026

Les seuils de la première version étaient posés au jugé. La revue en a tiré deux
défauts, dont l'un invalide franchement la conception.

**Défaut 1 — un seuil absolu sur une différence est aveugle.** `LOSS = ACCT-01 −
ACCT-02` portait `HIGH` à 150 µA et `HIHI` à 300 µA. Si la source faiblit à 200 µA, la
ligne peut perdre **100 % du faisceau** sans qu'aucune alarme ne parte : la perte vaut
200 µA, sous le seuil. Le seuil devenait faux aussi dès qu'on touchait à la tension
d'extraction.

**Défaut 2 — deux alarmes pour un seul événement.** `TRANS` et `LOSS` sont dérivées des
deux mêmes ACCT. Au nominal, `TRANS` passait MINOR à 122 µA de perte quand `LOSS`
attendait 150 ; MAJOR à 244 µA quand `LOSS` attendait 300. Quatre déclenchements
décalés pour une seule cause. C'est ainsi qu'on apprend aux opérateurs à ignorer les
alarmes.

**La correction n'est pas de les aligner** — les deux canaux ne répondent pas à la même
question, et c'est la distinction structurante de cette revue :

> **Seuil de protection** : découle de ce que le **matériel** supporte. Fixe, physique,
> défendable devant n'importe qui. Sa place est dans la base de PV.
>
> **Seuil d'exploitation** : découle de ce que la **campagne du jour** attend. 85 % de
> transmission peut être excellent pour un utilisateur et inacceptable pour le suivant.
> Le coder en dur dans la configuration matérielle, c'est faire passer une décision du
> jour pour une propriété de l'équipement.

**Décisions appliquées :**

- Champ **`alarm.kind`** (`protection` | `exploitation`) obligatoire, imposé par un test.
  Répartition : 11 protection, 9 exploitation.
- `LOSS` **perd son alarme** et redevient une mesure brute.
- **`LBE:MACH-01:LOSS_W`** ajoutée, dérivée de `LOSS` et de `SRC-01:HT_U_RB` : la
  puissance déposée, en watts, avec `HIGH` à 6 W et `HIHI` à 12 W. C'est la seule
  grandeur que la paroi comprenne, et le seuil reste juste quand la tension change.
- Les seuils `exploitation` restent dans le YAML comme **valeurs par défaut**,
  surchargeables par campagne à l'étape 2 — à côté des entrées de logbook, pas dans la
  configuration matérielle.

La base passe à **77 PV**.

**Erreur corrigée en séance.** Il avait été dit que la perte de faisceau « active les
matériaux » sur la LBE. C'est faux : l'activation suppose des réactions nucléaires, donc
des énergies de l'ordre du MeV par nucléon. Ici un ¹⁶O⁵⁺ extrait à 40 kV emporte 200 keV
au total, soit 12,5 keV/u — deux ordres de grandeur trop bas. La puissance faisceau vaut
`P = I × U = 812 µA × 40 kV ≈ 32 W`. Ce que la perte produit à cette énergie, c'est de
l'échauffement local, de la pulvérisation, et du **dégazage** : la paroi chauffée relâche
du gaz, la pression monte, la transmission baisse, donc la perte augmente. Une boucle qui
s'auto-entretient, et qui relie `VAC:P`, `VAC:T` et `LOSS_W`. À simuler telle quelle à
l'étape 1.

Règle générale à retenir : sur un accélérateur, la question n'est jamais « combien de
courant » mais « combien de watts, et à quelle énergie ». L'activation est le problème
des lignes situées après le linac.
