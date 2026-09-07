# Fiches de révision — EPICS, ligne basse énergie, archivage

Vingt-huit questions. Réponds **à voix haute ou dans ta tête avant de déplier** — c'est
le fait de chercher qui fixe, pas le fait de lire. Les blocs se déplient au clic sur
GitHub, y compris sur téléphone.

Repère de niveau : si tu réponds juste à 20/28 sans hésiter, tu peux tenir une
conversation d'entretien sur le sujet.

---

## A. La machine

**A1.** Que produit une source ECR, et par quel mécanisme ?
<details><summary>Réponse</summary>

Des **ions multichargés**. Un champ magnétique confine un plasma, une onde HF (14 GHz)
chauffe les électrons à la résonance cyclotron ; les collisions électroniques arrachent
successivement des électrons aux atomes. Plus le confinement est long, plus la charge
atteinte est élevée.
</details>

**A2.** Pourquoi des solénoïdes en basse énergie, et des quadripôles plus loin ?
<details><summary>Réponse</summary>

À basse énergie le faisceau est peu rigide et la charge d'espace est forte. Un solénoïde
focalise dans les deux plans à la fois, ce qui convient à un faisceau rond et divergent.
Un quadripôle focalise dans un plan et défocalise dans l'autre : plus efficace, mais
adapté à des faisceaux plus rigides.
</details>

**A3.** Que sélectionne le dipôle d'analyse, et selon quelle relation ?
<details><summary>Réponse</summary>

Un **rapport A/Q**. Le dipôle ne laisse passer qu'une rigidité magnétique `Bρ = p/q` ;
comme `p ∝ √(A·Q·U)`, on a `Bρ ∝ √(A/Q · U)`. Régler le champ, c'est donc choisir une
espèce dans le mélange sorti de la source.
</details>

**A4.** Différence entre un ACCT et une cage de Faraday ?
<details><summary>Réponse</summary>

L'ACCT (transformateur d'intensité) est **non interceptif** : il mesure par induction et
peut rester en permanence pendant la production. La cage de Faraday **arrête le
faisceau** pour le collecter : réservée au réglage, escamotée en production.
</details>

**A5.** Pourquoi la charge d'espace complique-t-elle un jumeau numérique ?
<details><summary>Réponse</summary>

Le faisceau, chargé, se repousse lui-même — l'effet croît avec l'intensité. La
transmission n'est donc **pas linéaire en intensité** : doubler le courant de source ne
double pas le courant en bout de ligne. Un modèle linéaire est faux d'emblée dans la
zone qui intéresse l'exploitant.
</details>

**A6.** Une remontée de vide, ça fait quoi au faisceau ?
<details><summary>Réponse</summary>

Les ions multichargés se recombinent sur le gaz résiduel en changeant d'état de charge.
Leur A/Q change, le dipôle ne les transmet plus : la transmission chute. Signal lent et
corrélé — bon candidat pour une détection multi-canaux.
</details>

**A7.** Pourquoi surveille-t-on la perte de faisceau plutôt que la seule intensité finale ?
<details><summary>Réponse</summary>

Ce qui n'arrive pas au bout est allé quelque part : la perte chauffe et **active** les
matériaux. C'est un enjeu de sécurité et de radioprotection, pas de rendement. D'où
`LOSS = ACCT-01 − ACCT-02` comme grandeur de premier rang.
</details>

---

## B. EPICS

**B1.** Une PV, c'est quoi exactement ?
<details><summary>Réponse</summary>

Un **canal nommé**, pas un nombre : une valeur **plus** un horodatage source, une unité,
un statut et une sévérité d'alarme. C'est l'unité d'adressage du système de contrôle.
</details>

**B2.** Qu'est-ce qu'un IOC ? Et un soft IOC ?
<details><summary>Réponse</summary>

*Input/Output Controller* : le processus qui sert un lot de PV, généralement au plus
près du matériel. Un **soft IOC** sert des PV sans matériel derrière — un simulateur, un
calcul, une passerelle. Notre jumeau en est un.
</details>

**B3.** Cite quatre types de records et leur usage.
<details><summary>Réponse</summary>

`ai` mesure analogique en entrée · `ao` consigne analogique en sortie · `bi`/`bo`
binaire · `mbbi`/`mbbo` multi-états (jusqu'à 16) · `calc` valeur dérivée ·
`waveform` tableau (profil, forme d'onde).
</details>

**B4.** À quoi servent `.HIHI`, `.HSV`, `.SEVR` ?
<details><summary>Réponse</summary>

`.HIHI` est un **seuil**. `.HHSV` (et `.HSV` pour `.HIGH`) est la **sévérité** attribuée
au dépassement : `MINOR` ou `MAJOR`. `.SEVR` est la sévérité **courante** du record —
`NO_ALARM`, `MINOR`, `MAJOR` ou `INVALID`. Les seuils sont la configuration, `.SEVR` est
l'état.
</details>

**B5.** Différence entre `.MDEL` et `.ADEL` ?
<details><summary>Réponse</summary>

Deux bandes mortes indépendantes : `.MDEL` gouverne les notifications aux **clients**
(IHM, souscriptions), `.ADEL` gouverne ce qui part à l'**archivage**. On archive
généralement plus grossièrement qu'on n'affiche.
</details>

**B6.** Que signifie `.SCAN = I/O Intr` ?
<details><summary>Réponse</summary>

Le record est traité **sur interruption du matériel**, pas à intervalle fixe. C'est le
mode « événementiel » ; les autres valeurs (`.1 second`, `1 second`…) sont périodiques,
et `Passive` signifie « seulement quand quelqu'un le demande ».
</details>

**B7.** CA et PVA : deux mots sur chacun.
<details><summary>Réponse</summary>

**Channel Access**, EPICS 3 : découverte par diffusion UDP, transport TCP, types
scalaires simples. **PV Access**, EPICS 7 : structures typées (`NTScalar`, `NTTable`),
meilleur débit, transport de structures complètes. SPIRAL2 et l'essentiel du parc
tournent encore en CA.
</details>

**B8.** Que fait `camonitor`, et en quoi diffère-t-il d'une boucle de `caget` ?
<details><summary>Réponse</summary>

Il ouvre une **souscription** : le serveur pousse à chaque changement dépassant `.MDEL`.
Une boucle de `caget` interroge à intervalle fixe : elle rate les transitoires entre deux
appels, elle charge inutilement le réseau quand rien ne bouge, et elle date les points à
l'heure du client. EPICS est un système à souscription — s'en servir en mode
interrogation, c'est le prendre à rebours.
</details>

**B9.** Pourquoi `_SP` et `_RB` ne sont-ils pas interchangeables ?
<details><summary>Réponse</summary>

`_SP` est une **décision humaine** (ce qu'on a demandé), `_RB` est un **état de la
machine** (ce qu'elle fait). Leur écart est en soi un diagnostic. Un modèle entraîné sur
les consignes apprend le comportement des opérateurs, pas celui de la machine — c'est le
piège n°1 du ML sur données d'accélérateur.
</details>

**B10.** Pourquoi une consigne ne porte-t-elle pas de seuil d'alarme ?
<details><summary>Réponse</summary>

Parce qu'une consigne peut être mauvaise mais n'est jamais « en défaut » : elle exprime
une intention. On surveille la machine, pas l'opérateur. Les bornes de pilotage
(`.DRVL`/`.DRVH`) limitent ce qu'on peut demander ; c'est autre chose qu'une alarme.
</details>

**B11.** Sans jointure ni schéma relationnel entre 80 000 canaux, qu'est-ce qui tient
lieu de structure ?
<details><summary>Réponse</summary>

**La convention de nommage.** C'est le seul schéma. D'où le fait qu'elle se décide une
fois, qu'elle se dérive d'une base de configuration plutôt que de se taper à la main, et
qu'on ne renomme pas — une PV renommée casse en silence des IHM, des scripts et des
archives.
</details>

---

## C. La donnée et l'archivage

**C1.** Pourquoi la donnée d'accélérateur n'est-elle pas tabulaire ?
<details><summary>Réponse</summary>

N canaux échantillonnés indépendamment, chacun avec son propre horodatage, aucun index
commun. Toute « ligne » de dataset est une **reconstruction** — et le choix de la
méthode d'alignement est une décision de modélisation, pas une étape de nettoyage.
</details>

**C2.** Un canal n'a émis aucun point depuis dix minutes. Que faut-il en conclure ?
<details><summary>Réponse</summary>

En principe : **rien n'a bougé** au-delà de la bande morte. L'absence de point est une
information, pas un trou. Donc `forward-fill` et non `dropna()`. Mais il faut vérifier la
**sévérité** : un canal en `INVALID` ou déconnecté n'émet rien non plus, et là reporter
la dernière valeur est un mensonge.
</details>

**C3.** Format long ou format large pour stocker ?
<details><summary>Réponse</summary>

**Long** : `(channel_id, ts, value, severity, status)`. Le format large demanderait une
colonne par canal — 80 000 colonnes, remplies à 1 %, et une migration à chaque
équipement ajouté. Le format large est celui du *dataset*, produit à la demande, jamais
celui du stockage.
</details>

**C4.** Quel index sur la table des échantillons, et pourquoi ?
<details><summary>Réponse</summary>

`(channel_id, ts DESC)`. Toutes les requêtes du métier sont « ce canal, entre telle et
telle date », et le `DESC` sert le cas le plus fréquent : les points les plus récents.
</details>

**C5.** Que fait `locf()`, et quand ment-il ?
<details><summary>Réponse</summary>

*Last observation carried forward* : reporte la dernière valeur connue sur les intervalles
sans point. Sémantique correcte pour une mesure à bande morte. **Faux** dès que
l'absence vient d'une panne, d'une déconnexion ou d'un `INVALID` — la différence se lit
dans la sévérité, jamais dans la valeur.
</details>

**C6.** Horodatage source ou horodatage d'ingestion : lequel stocke-t-on ?
<details><summary>Réponse</summary>

**Celui de la source**, apposé par l'IOC au moment de la mesure. Celui de l'ingestion
porte la latence du réseau, du collecteur et de la base. On peut garder les deux — leur
écart est un excellent indicateur de santé de la chaîne — mais l'analyse se fait sur
l'horodatage source.
</details>

**C7.** Régler une bande morte d'archivage, c'est un choix technique ?
<details><summary>Réponse</summary>

Non : un **arbitrage d'exploitation** entre volume stocké et finesse de détection. Trop
large, on efface la dérive lente qu'on voulait voir. Trop étroite, on stocke du bruit.
Seul l'exploitant peut trancher — c'est typiquement ce qu'on va chercher en réunion, pas
dans la doc.
</details>

**C8.** La transmission passe de 92 % à 78 % en dix minutes. Anomalie ?
<details><summary>Réponse</summary>

**Impossible à dire avec le seul historian.** Si un opérateur a désaccordé un solénoïde,
c'est normal ; si rien n'a été touché, c'est une anomalie. La consigne `_SP` dit *ce qui*
a changé, jamais *pourquoi*. C'est la raison d'être du logbook — et la raison pour
laquelle un modèle sans étiquettes d'intervention sera débranché en une semaine.
</details>

**C9.** Pourquoi la capture automatique d'entrées de journal est-elle décisive ?
<details><summary>Réponse</summary>

Parce qu'un logbook qui repose sur la discipline humaine est vide au bout d'un mois. Le
collecteur voit déjà passer les `_SP` : il crée l'entrée pré-remplie (date, canal,
ancienne et nouvelle valeur, catégorie *réglage*), l'opérateur n'ajoute que le
commentaire. **On documente pour eux, on leur laisse le pourquoi.**
</details>

**C10.** Pourquoi des étiquettes à vocabulaire contrôlé plutôt qu'un champ libre ?
<details><summary>Réponse</summary>

Un champ libre n'est pas exploitable par un programme : il faudrait du NLP pour
retrouver ce qu'un humain aurait pu cocher. Une liste fermée donne des **étiquettes de
ML directement utilisables**, et c'est la première brique du volet FAIR de l'annonce.
</details>

**C11.** Quel endpoint de l'API marque la frontière entre exploitation et ML ?
<details><summary>Réponse</summary>

`/dataset` : N canaux alignés sur une grille régulière, avec les étiquettes du logbook.
En amont, du système de contrôle ; en aval, du modèle. Le fait de savoir tracer cette
ligne est ce qu'on demande à un ingénieur support logiciel IA.
</details>

---

## D. Les trois phrases à savoir dire

<details><summary>Sur la donnée</summary>

« La donnée d'un accélérateur n'est pas une table : ce sont des canaux nommés,
échantillonnés à la variation, chacun avec son horodatage et sa sévérité. Toute ligne
de dataset est une reconstruction, et le choix de la reconstruction fait partie du
modèle. »
</details>

<details><summary>Sur le logbook</summary>

« Sans journal des interventions, un modèle ne peut pas distinguer une dérive machine
d'un réglage volontaire — il alarme sur le travail des opérateurs et il finit
débranché. Et un logbook ne se remplit que s'il se remplit tout seul. »
</details>

<details><summary>Sur la mise en production</summary>

« Le modèle n'est pas un service à côté du système de contrôle : c'est un équipement de
la ligne. Il lit des PV et il en écrit — au même titre que le calcul de transmission. Ce
qui le rend exploitable, ce n'est pas son score, c'est le fait qu'un opérateur puisse
lire sa sortie dans le synoptique. »
</details>
