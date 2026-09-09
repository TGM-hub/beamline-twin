# Jalon 0 — Ce qu'une vraie machine nous apprend

*Analyse de BOOSTR : Booster de Fermilab, 15 Hz, 24 h, 1 295 713 lignes × 43 canaux.
Code : `analysis/boostr_profile.py`. Chiffres reproductibles : `analysis/boostr_profile.csv`.*

Le Booster n'est pas la LBE — un synchrotron rapide contre une ligne basse énergie. On
ne copie donc pas ses valeurs, on lui emprunte ses **rapports** et ses **formes**, qui
eux se transposent. Cinq résultats, et ce que chacun change dans le simulateur.

---

## 1. Deux canaux sur trois ne bougent pas de la journée

**28 canaux sur 43 sont strictement constants sur 24 heures.** Pas « peu variables » :
identiques à eux-mêmes, du premier au dernier échantillon.

C'est la première chose qu'un simulateur naïf rate. Faire vivre 77 canaux produit un jeu
de données qui ne ressemble à aucune machine réelle — et un modèle entraîné là-dessus
découvrira, à son premier contact avec du vrai, que les deux tiers de ses entrées sont
des constantes.

> **Conséquence** : dans le simulateur, une majorité de canaux reste figée. Les
> configurations qu'on ne touche pas d'une campagne à l'autre — bornes, calibrations,
> paramètres de séquence — sont plates par construction.

## 2. Une lecture sur six est une vraie mesure

Sur 18 paires lecture/consigne, **15 lectures recopient exactement leur consigne**, à
100,00 % des échantillons. Il n'y a aucun capteur derrière : la valeur affichée est la
valeur demandée, renvoyée par l'automate.

Seules trois portent une information indépendante — et l'une d'elles, `B:VIPHAS`, a une
corrélation **nulle** avec sa consigne.

| Lecture | Identique à sa consigne | Corrélation | Vraie mesure |
|---|---|---|---|
| `B:VIMAX` | 0,01 % | 0,16 | oui |
| `B:VIMIN` | 0,01 % | 0,51 | oui |
| `B:VIPHAS` | 0,00 % | −0,00 | oui |
| les 15 autres | 100 % | 1,00 | **non** |

C'est le piège d'hier, en pire et sur données réelles : un pipeline qui avale les
43 colonnes croit disposer de 43 signaux. Il en a une dizaine.

> **Conséquence** : notre champ `domain` et notre clé `from:` étaient une bonne idée,
> mais insuffisants. Il faut une troisième catégorie — la lecture qui n'est qu'un écho
> de sa consigne. On l'ajoutera au YAML, et le simulateur en produira quelques-unes
> **exprès**, parce qu'un jeu qui n'en contient pas est trop facile.

## 3. Le bruit ne se règle pas d'un seul curseur

Rapport écart-type du bruit rapide sur écart-type de la dérive lente — la grandeur qui
se transpose d'une machine à l'autre :

| Famille | Canaux | bruit / dérive | bruit / moyenne |
|---|---|---|---|
| Diagnostics de faisceau | `I:IB`, `I:MDAT40`, `I:MXIB` | **145 à 236** | **≈ 48 %** |
| Équipements mesurés | `B:VIMAX`, `B:VIMIN`, `B:GMPS4V`, `B:IMINER` | **1,4 à 5,5** | 10⁻⁵ à 10⁻² |
| Grandeurs lentes et consignes | `B:LINFRQ`, `B_*` | **0,002 à 0,1** | ≈ 0 |

Quatre ordres de grandeur entre l'intensité faisceau et une tension d'aimant. Le
faisceau fluctue de moitié d'un cycle à l'autre ; l'alimentation du dipôle est stable à
trois millionièmes.

Et la structure est aussi différente que l'amplitude : le faisceau est **presque
uniquement du bruit**, l'équipement est **presque uniquement de la dérive**.

> **Conséquence** : trois familles de bruit dans le simulateur, calées sur ces rapports —
> pas un `+ np.random.normal(0, 0.01)` uniforme. C'est cette dissymétrie qui rend la
> détection d'anomalie non triviale : il faut voir 1 % de dérive sur un canal stable et
> ignorer 50 % de fluctuation sur un canal bruyant.

Résultat secondaire, mais qui valide la revue d'hier : **les trois familles mesurées ici
sont exactement nos domaines `faisceau`, `equipement` et `contexte`.** La distinction
qu'on avait posée par raisonnement se lit dans les données d'une autre machine.

## 4. Toutes les consignes qui bougent ne sont pas des interventions

Quatre consignes seulement ont bougé en 24 h. Mais elles ne se ressemblent pas :

| Consigne | Changements / 24 h | Saut médian rapporté à l'étendue |
|---|---|---|
| `B_VIMIN` | **846** | 0,4 % |
| `B_ACMNPG` | 25 | 6 % |
| `B_VIMAX` | 10 | 17 % |
| `B_VINHBT` | 2 | binaire |

`B_VIMIN` n'est pas un opérateur qui touche à un réglage 846 fois par jour : c'est une
**boucle de régulation** qui fait des micro-corrections. Les autres ressemblent à des
gestes humains — rares et amples.

Les deux populations sont séparées de **deux ordres de grandeur sur les deux axes** :
fréquence et amplitude relative. Le filtre est donc implémentable.

> **Conséquence, et elle est directe pour l'étape 2** : la capture automatique de
> logbook ne peut pas créer une entrée à chaque changement de consigne. Elle en
> produirait 846 par jour d'un seul canal, toutes vides de sens, et le journal serait
> inutilisable en une semaine. **Il faut classer le changement avant de le journaliser** :
> régulation ou geste humain. Un seuil sur (fréquence, amplitude relative) suffit.

## 5. BOOSTR ne peut pas tout calibrer — et il faut le dire

L'échantillonnage est **parfaitement régulier** : 67 ms, 100 % des intervalles entre 60
et 75 ms, un seul cycle manqué sur la journée. C'est un enregistrement **synchrone du
cycle machine**, pas un archivage à bande morte.

Donc BOOSTR calibre le bruit, la dérive, la proportion de canaux morts et la forme des
changements de consigne — mais **il ne dit rien de l'irrégularité d'échantillonnage**,
qui est pourtant la propriété la plus déroutante d'une archive EPICS. Celle-là, nous la
produirons par le modèle de bande morte, et elle restera non validée par des données
réelles. Autant l'écrire ici que de laisser croire le contraire.

---

## Note de méthode : une mesure retirée

Une première version estimait le **temps de corrélation de la dérive** par
autocorrélation. Le résultat variait d'un facteur dix selon la fenêtre choisie — 56 s,
132 s, 150 s, 581 s pour le même canal `B:LINFRQ`. La dérive n'est pas stationnaire sur
24 heures et l'estimateur ne tient pas.

La mesure a été **retirée du script** plutôt que publiée avec une réserve. Un chiffre
faux dans un tableau finit toujours par être cité. Le rapport bruit/dérive, lui, est
stable quelle que soit la fenêtre : c'est celui qu'on garde.

---

## Ce qui entre dans le simulateur

1. Une majorité de canaux figés — les configurations ne vivent pas.
2. Quelques lectures qui ne sont que l'écho de leur consigne, marquées comme telles.
3. Trois familles de bruit, calées sur les rapports du tableau 3.
4. Deux populations de changement de consigne : des gestes humains rares et amples, et
   une boucle de régulation bavarde, pour que le filtre de l'étape 2 ait quelque chose à
   filtrer.
5. L'irrégularité d'échantillonnage par bande morte, assumée comme non calibrée.
