# Jalon 0 — Le simulateur et le soft IOC

*`sim/beamline.py`, `sim/ioc.py`, `tests/test_beamline.py`. 28 tests.*

---

## L'architecture : une frontière, deux fichiers

`beamline.py` **ne connaît pas EPICS**. Il répond à une seule question : « à
l'instant t, avec ces réglages, que vaut chaque grandeur ? » `ioc.py` ne
connaît pas la physique : il construit les records depuis
`config/pv_map.yaml`, publie ce que le modèle produit, et transmet les `caput`.

Ce n'est pas de l'élégance gratuite. Neuf heures de machine se simulent en trois
secondes sans serveur ni réseau — c'est ce qui rend les tests de l'étape 3
supportables. Et le jour où le modèle devra tourner contre un vrai IOC, seul
`ioc.py` disparaît.

```
config/pv_map.yaml ──► sim/pvmap.py ──► sim/ioc.py ──► Channel Access
   (les noms)            (la règle)      (le serveur)
                                              ▲
                            sim/beamline.py ──┘
                              (la physique)
```

## Ce que le modèle fait, et ce qu'il ne fait pas

Pas de dynamique de faisceau, pas d'enveloppe, pas de particules : chaque
élément agit par une loi de comportement — gaussienne autour d'un optimum,
dérive lente, bruit. **Trois effets** sont malgré tout modélisés, parce qu'un
jeu de données qui ne les contient pas n'apprend rien à personne :

1. **La charge d'espace.** L'optimum de focalisation se déplace avec
   l'intensité. La ligne n'est donc pas linéaire, et un réglage optimal à
   faible intensité ne l'est plus à forte intensité.
2. **La sélection A/Q.** `Bρ ∝ √(A/Q · U)`, donc `A/Q ∝ B²/U`. Conséquence
   gratuite : monter la tension d'extraction déplace le A/Q transmis et oblige
   à retoucher le dipôle. Un couplage entre deux réglages, que le modèle de
   l'étape 3 pourra découvrir.
3. **La boucle vide → perte → échauffement → dégazage → vide.** Sous-critique
   au nominal, visible dès qu'une fuite s'installe.

## Le point de fonctionnement

```
ACCT-01   795 µA   bruit 2,64 %
TRANS    91,99 %   bruit 0,42 %
LOSS      65,1 µA
LOSS_W     2,60 W
```

Ce sont exactement les valeurs déclarées dans `pv_map.yaml`. Le fichier de
configuration et le simulateur racontent la même machine, et un test le vérifie.

## Le bruit du faisceau est commun, pas indépendant

Première version : un bruit tiré séparément sur chaque diagnostic. La
transmission, rapport de deux intensités, héritait alors de deux fois le bruit
faisceau — 3 % de tremblement, dans lequel une fuite devient invisible.

C'est faux. Les deux ACCT regardent **le même faisceau** : quand il fluctue,
ils fluctuent ensemble et le bruit **s'annule dans le rapport**. Seul le bruit
d'instrument est indépendant. Le modèle sépare donc 2,2 % de bruit faisceau
commun et 0,3 % de bruit capteur. La transmission retombe à 0,42 %.

> À retenir : une grandeur dérivée peut être bien plus stable que ses
> composantes, si leur bruit est corrélé. C'est pour ça qu'on surveille la
> transmission plutôt que les deux intensités séparément.

## Le scénario de démonstration

Fuite installée sur `VAC-02`, montée en une heure et demie :

| heure | `VAC-02:P` | `VAC-02:T` | `TRANS` | `LOSS` | claquages |
|---|---|---|---|---|---|
| 1 | 1,15e-07 | 23,21 | 91,22 % | 70,9 µA | 0 |
| 3 | 1,81e-07 | 23,48 | 90,08 % | 76,8 µA | 2 |
| 5 | 1,96e-07 | 23,81 | 88,92 % | 100,5 µA | 2 |
| 9 | 2,02e-07 | 23,90 | 88,50 % | 103,8 µA | 3 |

Pendant ce temps `SOL-01:I_RB` vaut 118,00, `DIP-01:B` vaut 0,428 et
`HT_U_RB` vaut 39,999 — **rigoureusement immobiles**. La distinction
équipement / faisceau dégagée en revue est dans le code, et un test l'impose.

Et la transmission s'arrête à 88,5 % alors que le seuil `LOW` est à 85 :
**l'alarme opérateur ne se déclenche pas.** C'est la fenêtre dans laquelle le
modèle doit parler. Un test interdit à ce scénario de franchir le seuil, pour
que la démonstration garde son sens même si on retouche la physique.

## La bande morte, et l'irrégularité qu'elle produit

Un canal ne notifie ses abonnés que si sa valeur a assez bougé depuis la
dernière fois — le champ `.MDEL` d'EPICS. C'est de là que vient
l'échantillonnage irrégulier d'une archive d'accélérateur.

Notifications reçues par un client en 30 secondes, pendant qu'une fuite
s'installe, alors que le serveur avance à 10 Hz :

| canal | notifications | comportement |
|---|---|---|
| `LBE:MACH-01:TRANS` | 249 | bavard : bruit de 0,4 % contre une bande morte de 0,1 point |
| `LBE:VAC-02:P` | 29 | muet au repos, parle dès que la pression monte |
| `LBE:SOL-01:I_RB` | 1 | annonce sa valeur, puis se tait |

### Une bande morte absolue n'a pas de sens sur un canal logarithmique

Première version : une bande morte valant 0,1 % de l'étendue déclarée, pour
tous les canaux. Correct pour un courant d'aimant qui vit entre 0 et 300 A.
**Faux pour une jauge à vide.** Déclarée de 10⁻¹⁰ à 10⁻³ mbar, elle héritait
d'un seuil de 10⁻⁶ — plus large que toute la vie du signal, qui se joue entre
3·10⁻⁸ et 2·10⁻⁷. Le canal était **structurellement muet** : une valeur au
démarrage, puis plus rien, même en pleine fuite.

Le défaut a survécu à une première vérification parce que le tableau de
comptage montrait « `VAC-02:P` → 1 notification » au milieu de quatre canaux
légitimement silencieux. Un canal mort et un canal calme se ressemblent. Il a
fallu s'en servir pour de vrai, avec une fuite en cours, pour voir que la
jauge resservait une valeur périmée d'une minute.

Correction : la bande morte est **relative à la valeur** dès qu'un canal
couvre plus de trois décades, absolue sinon, et surchargeable canal par canal
dans le YAML (`mdel`, `mdel_rel`). Trois canaux sur 77 sont concernés — les
trois jauges.

### Où poser le seuil

Règle utile : **environ quatre fois le bruit du canal**. En dessous, on archive
du bruit ; au-dessus, on perd le signal. Mesuré sur le simulateur, pour la
jauge dont le bruit est de 1,2 % :

| bande morte | au repos | pendant une fuite | contraste |
|---|---|---|---|
| 3 % | 19 | 34 | ×1,8 — bavarde sans rien dire |
| **5 %** | **2** | **19** | **×9,5** |
| 8 % | 1 | 13 | ×13, mais on suit mal la montée |

5 % retenu par défaut. Ce réglage reste une **décision d'exploitation**, pas un
paramètre technique : sur une vraie machine il se prend avec ceux qui
l'exploitent. On pose un défaut défendable, on le mesure, et on le documente.

C'est aussi la seule propriété du jeu de données que BOOSTR ne pouvait pas
calibrer — il est enregistré en synchrone du cycle, sans bande morte.

## Quatre bugs trouvés en testant, et ce qu'ils enseignent

**`A/Q = k/B` au lieu de `k·B²/U`.** Le premier test affichait 17,5 au lieu de
3,2. La version fausse n'avait pas le couplage tension–dipôle ; la bonne l'a.

**Les limites de pilotage posées sur des entrées.** `.DRVL`/`.DRVH` bornent ce
qu'un opérateur a le droit de **demander** — elles n'ont rien à faire sur une
mesure. Posées sur une entrée, caproto refusait d'écrire une valeur hors gamme
et **l'IOC mourait**. Autrement dit : le serveur masquait exactement l'anomalie
qu'on cherchait à voir. Une entrée accepte tout et signale par sa sévérité.

**`value_atol` de caproto est inerte.** L'argument existe sur les records mais
ne filtre rien : vérifié en comptant les monitors, tous les canaux émettaient à
chaque pas. La bande morte est donc implémentée dans la boucle de publication.
Un argument accepté n'est pas un argument appliqué — il fallait compter pour le
savoir.

**La bande morte absolue sur un canal logarithmique**, décrite plus haut. Le
seul des quatre qui ait échappé aux tests automatiques et qu'il ait fallu
trouver en se servant du système. Un test le couvre désormais : la jauge doit
émettre au moins cinq fois plus pendant une fuite qu'au repos.

Un cinquième défaut a été corrigé sans être un bug de code : `LBE:SRC-01:HT_I`
était classé `equipement`, et un test l'a vu bouger pendant une fuite. C'est
normal — le courant débité par l'alimentation HT dépend du faisceau extrait et
de l'ionisation du gaz résiduel. Reclassé `faisceau`, et il devient un **second
témoin** d'une fuite, indépendant de la transmission.

## Faire tourner

**Terminal 1 — le serveur.** Il doit rester ouvert : c'est lui la machine.

```bash
pip install -r requirements.txt
pytest tests -q                   # 28 tests
python -m sim.ioc --vitesse 300   # six heures de machine en une minute
```

**Terminal 2 — le client.**

```bash
python -m caproto.commandline.get     LBE:MACH-01:TRANS
python -m caproto.commandline.monitor LBE:ACCT-01:ITF LBE:MACH-01:TRANS LBE:VAC-02:P

python -m caproto.commandline.put LBE:SOL-01:I_SP 150   # la transmission tombe à 42 %
python -m caproto.commandline.put LBE:SOL-01:I_SP 118   # et remonte à 92 %

python -m caproto.commandline.put SIM:FUITE_VIDE 1.7e-7 # installe la fuite
python -m caproto.commandline.put SIM:ALIM_SOL1 1       # l'alimentation décroche
```

> **`caget`, `caput` et `camonitor` ne sont pas disponibles ici.** Ce sont les
> exécutables d'EPICS base, qu'il faut compiler et que le projet n'installe pas.
> caproto fournit les mêmes clients en Python pur, invoqués comme ci-dessus.
> Ils parlent le même protocole et se connectent aussi bien à un IOC réel : la
> différence est l'emballage, pas la fonction.
>
> caproto pose aussi des raccourcis `caproto-get`, `caproto-put` et
> `caproto-monitor` dans le dossier `Scripts` de l'installation Python. Ils sont
> plus courts à taper, mais ne marchent que si ce dossier est dans le `PATH` —
> ce qui n'est pas le cas par défaut sous Windows. La forme `python -m` marche
> toujours.

Les défauts s'injectent par des PV préfixées `SIM:`, distinctes de la ligne :
un opérateur n'a pas de bouton « fuite de vide ». Le préfixe rappelle qu'on est
dans un jumeau, et rend la démonstration faisable sans toucher au code.
