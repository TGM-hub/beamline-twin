# Étape 2 — Cours : archiver la donnée, et savoir ce qui s'est passé

*Lecture ~15 min. À lire avant la séance de code de l'étape 2.*

---

## 1. Point de situation

L'étape 1 produit un flux : 69 canaux qui poussent leurs valeurs en continu. Ce flux
n'est **stocké nulle part**. Coupez l'IOC, tout est perdu. Sans archive il n'y a pas de
jeu d'entraînement, donc pas d'étape 3 ; et sans journal des interventions il n'y a pas
d'étiquettes, donc pas de modèle exploitable.

C'est aussi, mot pour mot, ce que le GANIL écrit de son propre système : **pas de
logbook ni d'historian intégrés**. On ne devine pas leur besoin, ils l'ont publié. La
première puce de l'annonce — « structurer les logbooks et archives EPICS » — sort de là.

---

## 2. Comment on archive un système EPICS

### Le collecteur est un abonné, pas un ramasseur

Réflexe de data engineer : une tâche périodique qui interroge la source toutes les
N secondes. **C'est faux ici.** On ouvre une souscription (`camonitor`) et le serveur
pousse à chaque changement significatif. Trois conséquences :

- On ne connaît pas la fréquence à l'avance. Un canal peut ne rien émettre pendant
  vingt minutes, puis vingt points en trois secondes.
- On reçoit l'horodatage **de la source** — celui que l'IOC a apposé au moment de la
  mesure — et pas celui de l'insertion en base. Les deux diffèrent, parfois de
  beaucoup. **On stocke celui de la source.**
- Chaque échantillon arrive avec sa **sévérité** et son **statut**. Une valeur en
  `INVALID` n'est pas une valeur : c'est l'absence de mesure. Un modèle qui la traite
  comme un nombre apprend n'importe quoi.

### La bande morte, ou pourquoi il n'y a pas un point par seconde

Le champ `.ADEL` d'un record fixe la variation minimale au-delà de laquelle
l'échantillon part à l'archivage. C'est une **compression décidée à la source**, avant
tout réseau et toute base. Bien réglée, elle divise le volume par cent sans perdre
d'information utile ; mal réglée, elle efface précisément la dérive lente qu'on
cherchait à détecter.

> À retenir pour l'entretien : régler les bandes mortes est un arbitrage entre volume
> de stockage et finesse de détection. Ce n'est pas un paramètre technique, c'est une
> décision d'exploitation — et personne ne peut la prendre à la place de l'exploitant.

### Ce qui existe déjà dans le monde EPICS

| Outil | Ce que c'est |
|---|---|
| **Channel Archiver** | l'historique, encore croisé, fichiers propriétaires |
| **EPICS Archiver Appliance** | le standard actuel (SLAC) : étagement automatique court/moyen/long terme |
| **Archiver de Phoebus / CS-Studio** | intégré à l'IHM, souvent adossé à une base time-series |

On n'en déploie aucun : on écrit le nôtre, en Python, ~200 lignes. Pas pour faire mieux
— pour **comprendre** ce qu'ils font. Savoir dire en entretien « j'ai écrit un
collecteur, donc je sais ce que l'Archiver Appliance résout » vaut mieux que « j'ai
installé l'Archiver Appliance ».

---

## 3. Le schéma de données : la vraie question de l'étape

Tentation naturelle : une colonne par canal, une ligne par instant.

```
ts | LBE:SRC-01:HF_P_RB | LBE:SOL-01:I_RB | LBE:VAC-01:P | ...
```

**Impossible.** 80 000 canaux, donc 80 000 colonnes ; et comme les horodatages ne
coïncident jamais, la table serait à 99 % vide. Ce format est celui du *dataset*, pas
celui du *stockage*.

Le stockage se fait en **format long** :

```
channel                      -- une ligne par canal, les métadonnées
  id, name, egu, prec, device, signal, role, hihi, high, low, lolo, desc_fr, desc_en

sample                       -- une ligne par échantillon reçu
  channel_id, ts, value, severity, status
```

Trois propriétés qui en découlent :

1. **Ajouter un canal n'est pas une migration.** C'est une ligne dans `channel`. Sur
   une machine qui évolue en permanence, c'est décisif.
2. **L'index est `(channel_id, ts DESC)`.** Toutes les requêtes du métier sont de la
   forme « ce canal, entre telle et telle date ».
3. **La table `channel` est peuplée depuis `config/pv_map.yaml`.** Une seule source de
   vérité pour le nommage, les unités et les seuils — celle qu'on a écrite à l'étape 1.

### Pourquoi TimescaleDB plutôt que PostgreSQL nu

Ils sont déjà sur PostgreSQL (~60 tables de configuration). TimescaleDB en est une
extension, donc pas de base supplémentaire à administrer. Ce qu'elle apporte, et qui
compte vraiment ici :

- **hypertables** : partitionnement temporel automatique ;
- **compression colonne** : facteur 10 à 20 sur des séries lentes ;
- **`time_bucket()`** : le rééchantillonnage régulier ;
- **`locf()`** — *last observation carried forward* : reporter la dernière valeur
  connue. C'est **exactement** la sémantique correcte pour une donnée à bande morte, et
  c'est l'opérateur qui transforme le format long en dataset ;
- **politiques de rétention** : garder la seconde un mois, la minute cinq ans.

### Le moment où le data analyst reprend la main

```sql
SELECT time_bucket('1 second', ts) AS t,
       locf(avg(value)) AS valeur
FROM   sample
WHERE  channel_id = :id AND ts BETWEEN :debut AND :fin
GROUP  BY t ORDER BY t;
```

Ces trois lignes contiennent toute la difficulté de l'étape 3. `time_bucket` choisit une
résolution — trop fine, on invente des points ; trop grossière, on efface le transitoire
qu'on voulait détecter. `locf` décide que « pas de nouveau point » veut dire « rien n'a
bougé », ce qui est vrai pour une mesure à bande morte et **faux** pour un canal tombé
en panne. La différence se lit dans la sévérité, pas dans la valeur.

---

## 4. Le logbook : là où se trouvent les étiquettes

Un historian répond à « quelle valeur avait ce canal mardi à 3 h ». Il ne répond pas à
« pourquoi ». Or c'est ce « pourquoi » qui fait la différence entre une anomalie et une
intervention.

Cas concret, le même que l'exercice 3 de la revue de PV : la transmission chute de 92 %
à 78 % en dix minutes.

- Si un opérateur a désaccordé `SOL-01` pour optimiser autre chose : **comportement
  normal**, et un modèle qui alarme est un modèle qu'on débranchera au bout d'une
  semaine.
- Si rien n'a été touché : **anomalie**, et c'est précisément ce qu'on veut détecter.

L'historian seul ne distingue pas les deux cas — sauf à considérer que le changement de
`_SP` en est la trace. Ce qui est vrai, et insuffisant : la consigne dit *ce qui a
changé*, jamais *pourquoi*.

### Ce qu'une entrée de journal doit porter

```
logbook_entry
  id, ts_debut, ts_fin, auteur, categorie, texte,
  pv_concernees[], etiquettes[], id_entree_parente
```

- **`categorie`** : réglage, intervention, incident, observation, essai.
- **`pv_concernees`** : le lien vers l'historian. Sans lui, le journal est une prose
  qu'aucun programme ne lit.
- **`etiquettes`** : le vocabulaire contrôlé. Champ libre = données inexploitables ;
  liste fermée = étiquettes de ML directement utilisables. C'est le premier contact
  avec la partie FAIR de l'annonce, à l'étape 6.
- **`ts_fin`** : une intervention a une **durée**. Une entrée ponctuelle ne permet pas
  d'exclure une fenêtre d'entraînement.

### La capture automatique, le morceau qui impressionne

Le collecteur voit déjà passer tous les `_SP`. Quand une consigne bouge de plus de X %,
il crée **tout seul** une entrée pré-remplie : horodatage, canal, ancienne et nouvelle
valeur, catégorie `réglage`. L'opérateur n'a plus qu'à ajouter le *pourquoi* — ou rien,
et l'entrée reste exploitable.

> C'est l'idée à savoir défendre : **on ne demande pas aux opérateurs de documenter, on
> documente pour eux et on leur laisse le commentaire.** Un logbook qui repose sur la
> discipline humaine est vide au bout d'un mois. Le seul qui se remplit est celui qui
> se remplit tout seul.

---

## 5. L'API

Ils exposent deux services REST en **JAX-RS**, spécifiés en **OpenAPI 3.x**. On fait la
même chose en **FastAPI**, qui produit l'OpenAPI automatiquement — le contrat d'interface
est identique, seule l'implémentation diffère. C'est un argument à faire en entretien :
on parle la même langue d'interface, pas la même pile.

Le minimum utile :

```
GET  /channels                          liste et métadonnées
GET  /channels/{name}/samples           série brute, période donnée
GET  /channels/{name}/resampled         time_bucket + locf, prête pour le ML
GET  /logbook                           entrées, filtrables par date, canal, étiquette
POST /logbook                           créer une entrée
GET  /dataset                           N canaux alignés sur une grille, avec étiquettes
```

`/dataset` est l'endpoint qui compte : il est la frontière entre l'exploitation et le
ML. Tout ce qui est en amont est du système de contrôle, tout ce qui est en aval est du
modèle. C'est le genre de découpage qu'un jury regarde.

---

## 6. Ce qu'on codera à l'étape 2

1. `db/schema.sql` — `channel`, `sample` (hypertable), `logbook_entry`.
2. `collector/` — abonné Channel Access → insertion par lots, avec la sévérité.
3. `collector/autolog.py` — détection des changements de consigne, entrées auto.
4. `api/` — FastAPI, les six routes, OpenAPI généré.
5. `docker-compose.yml` — TimescaleDB + collecteur + API. **Premier vrai usage de
   Docker du projet**, et il est justifié : trois services qui doivent démarrer ensemble.
6. Un script de génération : 72 h de fonctionnement simulé, avec deux incidents et
   quatre réglages, pour avoir de quoi entraîner à l'étape 3.

---

## 7. Lexique FR / EN

| Français | English |
|---|---|
| archiveur, historien de données | archiver, historian |
| échantillon | sample |
| souscription, abonnement | subscription, monitor |
| bande morte d'archivage | archive deadband (`.ADEL`) |
| horodatage source / d'ingestion | source / ingestion timestamp |
| format long / format large | long (narrow) / wide format |
| rééchantillonnage | resampling |
| report de la dernière valeur | last observation carried forward (LOCF) |
| politique de rétention | retention policy |
| cahier de quart, journal de bord | logbook, e-log |
| entrée de journal | logbook entry |
| vocabulaire contrôlé | controlled vocabulary |
| étiquette | tag, label |
| jeu de données étiqueté | labelled dataset |
