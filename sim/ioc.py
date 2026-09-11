"""Soft IOC : le simulateur publié sur Channel Access.

Trois responsabilités, et rien d'autre :

1. **Construire la base de records** à partir de `config/pv_map.yaml`. Aucun nom
   n'est écrit ici — le fichier de configuration reste la source unique.
2. **Faire tourner la machine** et republier ses mesures à cadence fixe.
3. **Accepter les `caput`** sur les quinze consignes et les transmettre au
   modèle.

C'est un vrai serveur Channel Access : `caget`, `camonitor` et Phoebus s'y
connectent sans savoir qu'il n'y a pas de matériel derrière.

## La bande morte, et pourquoi elle compte

Chaque canal a une bande morte — le champ `.MDEL` d'EPICS. En deçà de cette
variation, le serveur **ne notifie pas** ses abonnés. C'est ce qui produit
l'échantillonnage irrégulier caractéristique d'une archive d'accélérateur : un
canal stable se tait pendant des minutes, puis crache dix points quand
quelqu'un touche un réglage.

caproto accepte bien un argument `value_atol` sur ses records, mais ne s'en
sert pas pour filtrer les notifications — vérifié en comptant les monitors :
tous les canaux émettaient à chaque pas, y compris ceux qui ne bougeaient pas.
La bande morte est donc appliquée ici, dans la boucle de publication : on
n'écrit dans le record que si la valeur a assez bougé depuis la dernière
publication. C'est la sémantique exacte de `.MDEL`, et elle a l'avantage
d'être lisible.

C'est aussi la seule propriété du jeu de données que BOOSTR n'a pas pu
calibrer — il est enregistré en synchrone du cycle, sans bande morte. Assumé.

## Les PV de simulation

Les défauts s'injectent par des PV préfixées `SIM:`, distinctes de la ligne. Un
opérateur n'a pas de bouton « fuite de vide » : ce préfixe rappelle qu'on est
dans un jumeau. Il rend aussi la démo faisable sans toucher au code.

    caput SIM:FUITE_VIDE 1.7e-7      installe une fuite sur VAC-02
    caput SIM:VITESSE 200            fait passer six heures en deux minutes
    caput SIM:ALIM_SOL1 1            l'alimentation du solénoïde décroche
"""

from __future__ import annotations

import argparse
import asyncio
import time
from typing import NamedTuple

from caproto import ChannelDouble, ChannelEnum, ChannelInteger, ChannelString
from caproto.asyncio.server import Context, start_server

from sim.beamline import Machine
from sim.pvmap import PV, expand

PERIODE = 0.1        # s entre deux republications — 10 Hz, comme le `.SCAN`
                     # déclaré dans les valeurs par défaut du YAML.


class Consigne(ChannelDouble):
    """Un record `ao` : ce qu'un client écrit part dans le modèle."""

    def __init__(self, *, machine: Machine, nom: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._machine = machine
        self._nom = nom

    async def verify_value(self, data):
        valeur = data[0] if isinstance(data, (list, tuple)) else data
        self._machine.ecrire(self._nom, float(valeur))
        return data


class Commande(ChannelDouble):
    """Une PV `SIM:` : elle pilote le simulateur, pas la machine."""

    def __init__(self, *, applique, **kwargs) -> None:
        super().__init__(**kwargs)
        self._applique = applique

    async def verify_value(self, data):
        valeur = data[0] if isinstance(data, (list, tuple)) else data
        self._applique(float(valeur))
        return data


#: Au-delà de ce rapport entre borne haute et borne basse, un canal est
#: considéré comme logarithmique : sa bande morte devient relative.
DECADES_LOG = 1000.0


class BandeMorte(NamedTuple):
    """Le seuil de notification d'un canal — le `.MDEL` d'EPICS.

    Deux composantes, parce qu'une seule ne suffit pas. Le `.MDEL` d'EPICS est
    absolu, ce qui convient à un courant d'aimant qui vit entre 0 et 300 A.
    Sur une jauge à vide, qui couvre sept décades, un seuil absolu est un
    piège : 0,1 % de l'étendue déclarée vaut 10⁻⁶ mbar, soit **plus large que
    toute la vie du signal**, qui se joue entre 3·10⁻⁸ et 2·10⁻⁷. Le canal
    devient alors structurellement muet — il annonce sa valeur une fois au
    démarrage puis ne dit plus jamais rien, même pendant une fuite.

    C'est exactement l'erreur qu'on a faite, et elle est passée inaperçue
    parce que quatre canaux voisins étaient légitimement silencieux.

    D'où les deux composantes : sur un canal logarithmique, ce qui compte
    n'est pas « combien de mbar de variation » mais « combien de pour cent ».
    L'Archiver Appliance propose la même chose pour la même raison.

    Ordre de grandeur utile : une bande morte se pose autour de **quatre fois
    le bruit du canal**. En dessous, on archive du bruit ; au-dessus, on perd
    le signal. Pour la jauge, dont le bruit est de 1,2 %, cela donne 5 % — et
    mesuré sur le simulateur, 2 notifications au repos contre 19 pendant une
    fuite. À 3 % on tombe à 19 contre 34 : le canal bavarde sans rien dire.
    """

    absolue: float = 0.0
    relative: float = 0.0

    def seuil(self, valeur: float) -> float:
        return max(self.absolue, self.relative * abs(valeur))


def _bande_morte(pv: PV, fraction: float, fraction_log: float) -> BandeMorte:
    """Choisit la bande morte d'un canal.

    Une valeur déclarée dans le YAML l'emporte toujours. Sinon : relative si le
    canal couvre plus de trois décades, absolue autrement.

    Régler finement ces seuils est une décision d'exploitation, pas un
    paramètre technique — elle se prend avec ceux qui exploitent la machine.
    On pose un défaut défendable et on le documente.
    """
    if pv.mdel is not None or pv.mdel_rel is not None:
        return BandeMorte(pv.mdel or 0.0, pv.mdel_rel or 0.0)
    if pv.lo is None or pv.hi is None or pv.hi <= pv.lo:
        return BandeMorte()
    if pv.lo > 0 and pv.hi / pv.lo > DECADES_LOG:
        return BandeMorte(relative=fraction_log)
    return BandeMorte(absolue=(pv.hi - pv.lo) * fraction)


def doit_publier(valeur, ancienne, bande: BandeMorte) -> bool:
    """Faut-il notifier les abonnés ? Isolé pour être testable sans serveur."""
    if ancienne is None or not isinstance(valeur, (int, float)):
        return True
    return abs(valeur - ancienne) >= bande.seuil(valeur)


def construire(pvs: list[PV], machine: Machine) -> dict:
    """La base de records, dérivée entièrement du YAML."""
    pvdb: dict = {}
    for pv in pvs:
        a = pv.alarm
        # `.DRVL` / `.DRVH` — les limites de pilotage — ne s'appliquent qu'aux
        # SORTIES : elles bornent ce qu'un opérateur a le droit de demander.
        # Les poser sur une entrée serait une faute : caproto refuserait alors
        # d'écrire une mesure hors gamme, et le serveur masquerait précisément
        # l'anomalie qu'on cherche à voir. Une entrée accepte tout et signale
        # le dépassement par sa sévérité.
        pilotage = dict(lower_ctrl_limit=pv.lo, upper_ctrl_limit=pv.hi)
        commun = dict(
            value=pv.value,
            units=pv.egu or None,
            precision=pv.prec,
            lower_disp_limit=pv.lo, upper_disp_limit=pv.hi,
            # Les seuils du YAML deviennent les limites du record : c'est le
            # serveur qui calcule la sévérité, pas nous.
            lower_alarm_limit=a.get("lolo"), lower_warning_limit=a.get("low"),
            upper_warning_limit=a.get("high"), upper_alarm_limit=a.get("hihi"),
        )
        commun = {k: v for k, v in commun.items() if v is not None}

        if pv.role == "setpoint":
            pvdb[pv.name] = Consigne(machine=machine, nom=pv.name,
                                     **commun, **pilotage)
        elif pv.role == "state":
            pvdb[pv.name] = ChannelEnum(value=pv.states[0],
                                        enum_strings=list(pv.states))
        elif pv.role == "counter":
            pvdb[pv.name] = ChannelInteger(value=int(pv.value), units=pv.egu or None)
        elif pv.role == "context":
            pvdb[pv.name] = ChannelString(value=str(pv.value))
        else:
            pvdb[pv.name] = ChannelDouble(**commun)
    return pvdb


def ajouter_commandes(pvdb: dict, machine: Machine, etat: dict) -> None:
    """Les leviers du jumeau, sous un préfixe qui dit ce qu'ils sont."""

    def vitesse(v: float) -> None:
        etat["vitesse"] = max(0.0, v)

    pvdb["SIM:VITESSE"] = Commande(
        applique=vitesse, value=etat["vitesse"], units="x", precision=1,
        lower_ctrl_limit=0.0, upper_ctrl_limit=10000.0)
    pvdb["SIM:FUITE_VIDE"] = Commande(
        applique=lambda v: machine.injecter(fuite_vide=v),
        value=0.0, units="mbar", precision=3)
    pvdb["SIM:DERIVE_SOURCE"] = Commande(
        applique=lambda v: machine.injecter(derive_source=v),
        value=0.0, units="", precision=3,
        lower_ctrl_limit=-0.9, upper_ctrl_limit=0.9)
    pvdb["SIM:ALIM_SOL1"] = Commande(
        applique=lambda v: machine.injecter(alim_sol1_morte=bool(v)),
        value=0.0, units="", precision=0)
    pvdb["SIM:VANNE_02"] = Commande(
        applique=lambda v: machine.injecter(vanne_02_fermee=bool(v)),
        value=0.0, units="", precision=0)
    pvdb["SIM:TEMPS"] = ChannelDouble(value=0.0, units="s", precision=1)
    pvdb["SIM:ERREURS"] = ChannelInteger(value=0, units="")


async def tourner(pvdb: dict, machine: Machine, etat: dict,
                  bandes: dict[str, float]) -> None:
    """Avance la machine et republie. Le cœur du soft IOC."""
    publie: dict[str, float] = {}
    while True:
        debut = time.monotonic()
        machine.pas(PERIODE * etat["vitesse"])

        horodatage = time.time()
        for nom, valeur in machine.mesures().items():
            canal = pvdb.get(nom)
            if canal is None:
                continue
            # Bande morte : sous ce seuil, on ne dit rien. C'est de là que
            # vient l'irrégularité d'échantillonnage de l'archive.
            bande = bandes.get(nom)
            if bande is not None:
                if not doit_publier(valeur, publie.get(nom), bande):
                    continue
                publie[nom] = valeur
            try:
                await canal.write(valeur, timestamp=horodatage)
            except Exception as erreur:            # noqa: BLE001
                # Un IOC ne s'arrête pas parce qu'un record a reçu une valeur
                # imprévue : il continue de servir les autres et rend le
                # problème visible. Un serveur qui meurt en silence est pire
                # qu'un canal faux.
                etat["erreurs"] += 1
                if etat["erreurs"] <= 5:
                    print(f"[{nom}] écriture refusée : {erreur}")
        await pvdb["SIM:TEMPS"].write(machine.t, timestamp=horodatage)
        await pvdb["SIM:ERREURS"].write(etat["erreurs"], timestamp=horodatage)

        reste = PERIODE - (time.monotonic() - debut)
        await asyncio.sleep(max(reste, 0.0))


async def principal(fraction: float, fraction_log: float,
                    vitesse: float, graine: int) -> None:
    machine = Machine(graine=graine)
    etat = {"vitesse": vitesse, "erreurs": 0}
    pvs = expand()
    pvdb = construire(pvs, machine)
    bandes = {pv.name: _bande_morte(pv, fraction, fraction_log) for pv in pvs}
    logarithmiques = [n for n, b in bandes.items() if b.relative]
    ajouter_commandes(pvdb, machine, etat)

    print(f"{len(pvs)} PV de la ligne + {len(pvdb) - len(pvs)} PV de simulation")
    print(f"bande morte : {100*fraction:.2f} % de l'étendue, ou "
          f"{100*fraction_log:.1f} % de la valeur sur les {len(logarithmiques)} "
          "canaux logarithmiques")
    print(f"vitesse : ×{vitesse:g}\n")
    print("  caget LBE:MACH-01:TRANS")
    print("  camonitor LBE:ACCT-01:ITF LBE:MACH-01:TRANS LBE:VAC-02:P")
    print("  caput SIM:FUITE_VIDE 1.7e-7\n")

    await asyncio.gather(
        start_server(pvdb, log_pv_names=False),
        tourner(pvdb, machine, etat, bandes),
    )


def main() -> int:
    p = argparse.ArgumentParser(description="Soft IOC de la ligne basse énergie")
    p.add_argument("--bande-morte", type=float, default=0.001,
                   help="fraction de l'étendue en deçà de laquelle on ne "
                        "notifie pas (défaut : 0,1 %%)")
    p.add_argument("--bande-morte-log", type=float, default=0.05,
                   help="bande morte relative des canaux couvrant plus de "
                        "trois décades (défaut : 5 %%, soit environ quatre "
                        "fois le bruit d'une jauge à vide)")
    p.add_argument("--vitesse", type=float, default=1.0,
                   help="facteur d'accélération du temps simulé")
    p.add_argument("--graine", type=int, default=0)
    args = p.parse_args()
    try:
        asyncio.run(principal(args.bande_morte, args.bande_morte_log,
                              args.vitesse, args.graine))
    except KeyboardInterrupt:
        print("\narrêt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
