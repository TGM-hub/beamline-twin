"""Modèle de comportement de la ligne basse énergie.

Ce module ne connaît pas EPICS. Il répond à une seule question : « à l'instant t,
avec ces réglages, que vaut chaque grandeur physique de la ligne ? » L'IOC
(`sim/ioc.py`) se contente de publier ce qu'il produit.

Cette séparation est volontaire : on peut tester toute la physique sans réseau,
sans serveur et sans attendre le temps réel.

## Ce qui est simplifié, et assumé

Pas de dynamique de faisceau, pas d'enveloppe, pas de particules. Chaque
élément agit par une **loi de comportement** : une gaussienne autour d'un
optimum, une dérive lente, un bruit. L'effort du projet porte sur
l'infrastructure, pas sur la physique.

Trois effets sont malgré tout modélisés parce qu'ils font l'intérêt du jeu de
données, et qu'un modèle qui ne les voit pas n'apprend rien :

1. **La charge d'espace** : l'optimum de focalisation se déplace avec
   l'intensité. La ligne n'est donc pas un système linéaire, et un réglage
   optimal à faible intensité ne l'est plus à forte intensité.
2. **La sélection A/Q** : le dipôle ne transmet qu'une fenêtre étroite autour
   d'un rapport masse sur charge, et la largeur de cette fenêtre dépend de
   l'ouverture des fentes.
3. **La boucle vide → perte → échauffement → dégazage → vide** : une perte de
   faisceau chauffe la paroi, la paroi dégaze, la pression monte, la
   transmission baisse, donc la perte augmente. Sous-critique au nominal,
   visible dès qu'une fuite s'installe. C'est le scénario de panne dégagé en
   revue (question 2).

## Sur la calibration

Les *rapports* viennent du profil de BOOSTR (`docs/03-profil-boostr.md`) : le
faisceau est presque uniquement du bruit, l'équipement presque uniquement de la
dérive, avec plusieurs ordres de grandeur entre les deux.

Les *valeurs absolues* de bruit faisceau, elles, ne se transposent pas. Le
Booster affiche 48 % de variation d'un cycle à l'autre parce que c'est un
synchrotron pulsé qui sert des destinations différentes à chaque cycle — c'est
de la variation d'exploitation, pas du bruit. Une source ECR en continu est
bien plus stable : quelques pour cent en court terme, avec des dérives lentes
plus amples. On reprend donc la **hiérarchie**, pas les chiffres.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field, replace

# ---------------------------------------------------------------------------
# Constantes du modèle. Regroupées ici pour être lisibles et discutables :
# chacune est un choix, aucune n'est une mesure.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Constantes:
    # --- source ECR
    i_source_max: float = 812.0      # µA extractibles au réglage parfait
    hf_opt: float = 450.0            # W
    hf_largeur: float = 260.0        # W, tolérance avant chute
    gas_opt: float = 1.20            # sccm
    gas_largeur: float = 0.55
    coil_inj_opt: float = 620.0      # A
    coil_ext_opt: float = 580.0      # A
    coil_largeur: float = 190.0
    ht_nominal: float = 40.0         # kV

    # --- transport
    sol1_opt: float = 118.0          # A à intensité nominale
    sol2_opt: float = 131.0
    sol_largeur: float = 26.0
    charge_espace: float = 0.06      # déplacement relatif de l'optimum à +100 % d'intensité
    dip_gain: float = 2.0e-3         # T/A
    # Rigidité magnétique : Bρ ∝ √(A/Q · U), donc A/Q ∝ B²/U. Doubler le champ
    # quadruple le A/Q transmis ; monter la tension d'extraction l'abaisse.
    # Constante calée pour que B = 0,428 T à 40 kV transmette A/Q = 3,2.
    aq_constante: float = 698.7      # A/Q = aq_constante · B² / U
    aq_resolution: float = 0.0016    # largeur relative de la fenêtre A/Q pour 1 mm de fente
    fente_ouverture: float = 3.4     # mm, constante de la coupure géométrique
    pertes_fixes: float = 0.0327     # ce que la géométrie coûte toujours

    # --- vide
    p_base: float = 3.05e-8          # mbar, chambre propre et froide
    p_reference: float = 1.5e-6      # mbar, échelle de la recombinaison
    degazage: float = 0.05           # par °C au-dessus de l'ambiante

    # --- thermique
    t_ambiante: float = 22.0         # °C
    bobine_r_th: float = 8.6e-4      # °C/A², échauffement des bobines
    bobine_tau: float = 300.0        # s
    chambre_par_watt: float = 0.77   # °C/W déposé par le faisceau perdu
    chambre_tau: float = 1800.0      # s

    # --- bruit : la hiérarchie vient de BOOSTR, les valeurs sont raisonnées
    # Le bruit du faisceau est COMMUN à tous les diagnostics : ils regardent le
    # même faisceau. Seul le bruit d'instrument est indépendant. Séparer les
    # deux n'est pas un raffinement : sans ça, la transmission — un rapport de
    # deux intensités — hérite de deux fois le bruit faisceau et devient
    # illisible, alors qu'en réalité le bruit commun s'y annule.
    bruit_faisceau: float = 0.022    # 2,2 % rms, commun, source ECR continue
    bruit_instrument: float = 0.003  # 0,3 % rms, propre à chaque capteur
    bruit_equipement: float = 3.0e-5 # recopie d'alimentation, très stable
    bruit_vide: float = 0.012        # 1,2 %, jauge
    bruit_position: float = 0.05     # mm
    derive_tau: float = 5400.0       # s, ~1 h 30 : échelle de dérive de la source
    derive_amplitude: float = 0.11   # ±11 % lentement


CTE = Constantes()


# ---------------------------------------------------------------------------
# Réglages : tout ce qu'un opérateur peut écrire. Une seule classe, parce que
# c'est exactement la liste des consignes `_SP` de la base de PV.
# ---------------------------------------------------------------------------


@dataclass
class Reglages:
    hf_p: float = 450.0
    gas_q: float = 1.20
    ht_u: float = 40.0
    coil_inj_i: float = 620.0
    coil_ext_i: float = 580.0
    sol1_i: float = 118.0
    sol2_i: float = 131.0
    dip_i: float = 214.0
    ste_ih: float = 0.40
    ste_iv: float = -0.15
    slt_gap: float = 12.0
    slt_pos: float = 0.0
    fc_in: int = 0                   # cage de Faraday insérée
    prof_in: int = 0                 # profileur inséré
    aq_vise: float = 3.20


# ---------------------------------------------------------------------------
# Défauts injectables. Ce sont eux qui produiront la vérité terrain de
# l'étape 3 : on sait exactement quand ils commencent et quand ils cessent.
# ---------------------------------------------------------------------------


@dataclass
class Defauts:
    fuite_vide: float = 0.0          # mbar ajoutés à la chambre VAC-02, montée progressive
    fuite_tau: float = 3600.0        # s pour atteindre le palier
    derive_source: float = 0.0       # dérive imposée en plus de la dérive naturelle
    alim_sol1_morte: bool = False    # l'alimentation ne suit plus la consigne
    vanne_02_fermee: bool = False


def _gauss(x: float, centre: float, largeur: float) -> float:
    """Rendement gaussien : 1 à l'optimum, décroissant de part et d'autre."""
    return math.exp(-0.5 * ((x - centre) / largeur) ** 2)


class Machine:
    """L'état de la ligne, avancé pas à pas.

    L'état latent (dérives, températures, pressions) est ce que le modèle IA
    devra deviner ; les réglages sont ce que l'opérateur impose ; les mesures
    sont ce qui sort sur le bus.
    """

    def __init__(self, reglages: Reglages | None = None, graine: int = 0,
                 cte: Constantes = CTE) -> None:
        self.cte = cte
        self.r = reglages or Reglages()
        self.defauts = Defauts()
        self.alea = random.Random(graine)

        self.t = 0.0                              # s de temps simulé
        self._derive = 0.0                        # dérive lente de la source
        self._fuite = 0.0                         # fuite installée, montée progressive
        self._t_bobines = {"SOL-01": cte.t_ambiante, "SOL-02": cte.t_ambiante,
                           "DIP-01": cte.t_ambiante}
        self._t_chambres = {n: cte.t_ambiante for n in ("VAC-01", "VAC-02", "VAC-03")}
        self._i_sol1_reel = self.r.sol1_i         # ce que l'alimentation fait vraiment
        self._perte_w = 0.0
        self._claquages = 0
        self.espece = "16O5+"
        self.mode = "PRODUCTION"
        self.pas(0.0)                             # amorce un état cohérent

    # -- physique ----------------------------------------------------------

    def _avance_derive(self, dt: float) -> None:
        """Processus d'Ornstein-Uhlenbeck : une marche aléatoire qui revient
        vers zéro. C'est le modèle standard d'une dérive lente bornée — sans le
        rappel, la source finirait par s'éteindre ou exploser."""
        c = self.cte
        if dt <= 0:
            return
        rappel = math.exp(-dt / c.derive_tau)
        sigma = c.derive_amplitude * math.sqrt(1 - rappel ** 2)
        self._derive = self._derive * rappel + self.alea.gauss(0.0, sigma)

    def _intensite_source(self) -> float:
        c, r = self.cte, self.r
        rendement = (_gauss(r.hf_p, c.hf_opt, c.hf_largeur)
                     * _gauss(r.gas_q, c.gas_opt, c.gas_largeur)
                     * _gauss(r.coil_inj_i, c.coil_inj_opt, c.coil_largeur)
                     * _gauss(r.coil_ext_i, c.coil_ext_opt, c.coil_largeur))
        # L'extraction suit la loi de Child-Langmuir en U^(3/2), qu'on réduit
        # ici à une racine : on ne cherche pas la justesse, on cherche qu'une
        # hausse de tension augmente l'intensité de façon non linéaire.
        tension = math.sqrt(max(r.ht_u, 0.0) / c.ht_nominal)
        derive = 1.0 + self._derive + self.defauts.derive_source
        return max(0.0, c.i_source_max * rendement * tension * derive)

    def _pression(self, chambre: str) -> float:
        c = self.cte
        chaud = math.exp(c.degazage * (self._t_chambres[chambre] - c.t_ambiante))
        p = c.p_base * chaud
        if chambre == "VAC-02":
            p += self._fuite
        if self.defauts.vanne_02_fermee and chambre == "VAC-02":
            p *= 8.0                              # plus de pompage : la pression monte
        return p

    def _transmission(self, i_source: float, p_moyen: float) -> float:
        c, r = self.cte, self.r
        # Charge d'espace : l'optimum de focalisation se déplace avec l'intensité.
        glissement = 1.0 + c.charge_espace * (i_source / 812.0 - 1.0)
        t_sol1 = _gauss(self._i_sol1_reel, c.sol1_opt * glissement, c.sol_largeur)
        t_sol2 = _gauss(r.sol2_i, c.sol2_opt * glissement, c.sol_largeur)

        # Le dipôle sélectionne un A/Q. L'écart au A/Q visé coûte, et la
        # fenêtre s'élargit avec l'ouverture des fentes.
        b = c.dip_gain * r.dip_i
        aq_transmis = c.aq_constante * b * b / max(r.ht_u, 1e-6)
        fenetre = max(c.aq_resolution * max(r.slt_gap, 0.5), 1e-4)
        t_aq = _gauss(aq_transmis, r.aq_vise, fenetre * r.aq_vise)

        # Coupure géométrique des fentes : trop fermées, elles rognent aussi
        # l'espèce voulue.
        t_fentes = 1.0 - math.exp(-max(r.slt_gap, 0.0) / c.fente_ouverture)

        # Recombinaison sur le gaz résiduel.
        t_vide = math.exp(-p_moyen / c.p_reference)

        t = t_sol1 * t_sol2 * t_aq * t_fentes * t_vide * (1.0 - c.pertes_fixes)
        if self.r.prof_in:
            t *= 0.93                             # le fil intercepte une part du faisceau
        return max(0.0, min(1.0, t))

    def pas(self, dt: float) -> None:
        """Avance l'état de `dt` secondes."""
        c = self.cte
        self.t += dt
        self._avance_derive(dt)

        # La fuite s'installe progressivement — une fuite instantanée n'existe pas.
        if dt > 0 and self.defauts.fuite_vide > 0:
            k = 1.0 - math.exp(-dt / self.defauts.fuite_tau)
            self._fuite += (self.defauts.fuite_vide - self._fuite) * k
        elif self.defauts.fuite_vide == 0:
            self._fuite *= math.exp(-dt / max(self.defauts.fuite_tau, 1.0))

        # L'alimentation du solénoïde suit sa consigne, sauf si elle est morte.
        cible = self._i_sol1_reel if self.defauts.alim_sol1_morte else self.r.sol1_i
        self._i_sol1_reel += (cible - self._i_sol1_reel) * (1.0 if dt else 1.0)

        # Températures de bobines : premier ordre vers l'équilibre I²R.
        for nom, courant in (("SOL-01", self._i_sol1_reel), ("SOL-02", self.r.sol2_i),
                             ("DIP-01", self.r.dip_i)):
            equilibre = c.t_ambiante + c.bobine_r_th * courant ** 2
            k = 1.0 - math.exp(-dt / c.bobine_tau) if dt else 1.0
            self._t_bobines[nom] += (equilibre - self._t_bobines[nom]) * k

        # Températures de chambre : chauffées par la puissance perdue.
        for nom in self._t_chambres:
            part = {"VAC-01": 0.2, "VAC-02": 0.6, "VAC-03": 0.2}[nom]
            equilibre = c.t_ambiante + c.chambre_par_watt * self._perte_w * part
            k = 1.0 - math.exp(-dt / c.chambre_tau) if dt else 1.0
            self._t_chambres[nom] += (equilibre - self._t_chambres[nom]) * k

        # Boucle : la perte de ce pas alimentera l'échauffement du pas suivant.
        i_src = self._intensite_source()
        p_moyen = sum(self._pression(n) for n in self._t_chambres) / 3
        t_ligne = self._transmission(i_src, p_moyen)
        self._perte_w = i_src * (1.0 - t_ligne) * self.r.ht_u * 1e-3   # µA × kV = mW → W

        # Claquages haute tension : rares, et d'autant plus fréquents que la
        # pression est haute. Un compteur qui n'avance jamais n'apprend rien ;
        # un compteur corrélé au vide donne au modèle un second témoin.
        if dt > 0:
            taux = 4e-6 * (p_moyen / c.p_base) ** 2      # par seconde
            if self.alea.random() < min(taux * dt, 0.5):
                self._claquages += 1

    # -- lecture -----------------------------------------------------------

    def mesures(self) -> dict[str, float | int | str]:
        """Toutes les grandeurs, nommées comme dans `config/pv_map.yaml`."""
        c, r, a = self.cte, self.r, self.alea

        def bruit(valeur: float, relatif: float) -> float:
            return valeur * (1.0 + a.gauss(0.0, relatif))

        pressions = {n: self._pression(n) for n in self._t_chambres}
        p_moyen = sum(pressions.values()) / 3
        # Le faisceau fluctue une fois pour tout le monde : c'est le même
        # faisceau que tous les diagnostics regardent.
        i_src = self._intensite_source() * (1.0 + a.gauss(0.0, c.bruit_faisceau))
        t_ligne = self._transmission(i_src, p_moyen)

        acct1 = bruit(i_src, c.bruit_instrument)
        # La cage de Faraday intercepte : plus rien n'arrive en bout de ligne.
        acct2 = 0.0 if r.fc_in else bruit(i_src * t_ligne, c.bruit_instrument)
        fc = bruit(i_src * t_ligne, c.bruit_instrument) if r.fc_in else 0.0
        perte = max(0.0, acct1 - acct2)
        perte_w = perte * r.ht_u * 1e-3

        b_dip = c.dip_gain * r.dip_i
        aq_transmis = c.aq_constante * b_dip * b_dip / max(r.ht_u, 1e-6)
        desaccord = abs(self._i_sol1_reel - c.sol1_opt) / c.sol_largeur

        m: dict[str, float | int | str] = {
            # --- source
            "LBE:SRC-01:HF_P_RB": bruit(r.hf_p, c.bruit_equipement),
            "LBE:SRC-01:GAS_Q_RB": bruit(r.gas_q, c.bruit_equipement),
            "LBE:SRC-01:HT_U_RB": bruit(r.ht_u, c.bruit_equipement),
            # Le courant debite suit le faisceau extrait ET l'ionisation du gaz
            # residuel : une remontee de vide le fait monter. Second temoin
            # d'une fuite, independant de la transmission.
            "LBE:SRC-01:HT_I": bruit(3.1 * i_src / 812.0
                                     * (1.0 + 0.05 * (p_moyen / c.p_base - 1.0)), 0.02),
            "LBE:COIL-INJ:I_RB": bruit(r.coil_inj_i, c.bruit_equipement),
            "LBE:COIL-EXT:I_RB": bruit(r.coil_ext_i, c.bruit_equipement),
            # --- transport
            "LBE:SOL-01:I_RB": bruit(self._i_sol1_reel, c.bruit_equipement),
            "LBE:SOL-01:B": bruit(2.5e-3 * self._i_sol1_reel, c.bruit_equipement),
            "LBE:SOL-01:T": self._t_bobines["SOL-01"] + a.gauss(0.0, 0.05),
            "LBE:SOL-02:I_RB": bruit(r.sol2_i, c.bruit_equipement),
            "LBE:SOL-02:B": bruit(2.5e-3 * r.sol2_i, c.bruit_equipement),
            "LBE:SOL-02:T": self._t_bobines["SOL-02"] + a.gauss(0.0, 0.05),
            "LBE:DIP-01:I_RB": bruit(r.dip_i, c.bruit_equipement),
            "LBE:DIP-01:B": bruit(b_dip, c.bruit_equipement),
            "LBE:DIP-01:AQ": aq_transmis,
            "LBE:DIP-01:T": self._t_bobines["DIP-01"] + a.gauss(0.0, 0.05),
            "LBE:STE-01:IH_RB": bruit(r.ste_ih, c.bruit_equipement),
            "LBE:STE-01:IV_RB": bruit(r.ste_iv, c.bruit_equipement),
            "LBE:SLT-01:GAP_RB": bruit(r.slt_gap, c.bruit_equipement),
            "LBE:SLT-01:POS_RB": r.slt_pos,
            # --- diagnostics
            "LBE:ACCT-01:ITF": acct1,
            "LBE:ACCT-02:ITF": acct2,
            "LBE:FC-01:ITF": fc,
            "LBE:FC-01:POS_RB": r.fc_in,
            "LBE:BPM-01:X": 0.9 * r.ste_ih + a.gauss(0.0, c.bruit_position),
            "LBE:BPM-01:Y": 0.9 * r.ste_iv + a.gauss(0.0, c.bruit_position),
            "LBE:BPM-01:ITF": bruit(i_src, c.bruit_instrument),
            "LBE:BPM-02:X": 0.5 * r.ste_ih + a.gauss(0.0, c.bruit_position),
            "LBE:BPM-02:Y": 0.5 * r.ste_iv + a.gauss(0.0, c.bruit_position),
            "LBE:BPM-02:ITF": bruit(i_src * t_ligne, c.bruit_instrument),
            "LBE:PROF-01:SIGX": bruit(3.8 * (1 + 0.9 * desaccord), 0.03),
            "LBE:PROF-01:SIGY": bruit(3.6 * (1 + 0.9 * desaccord), 0.03),
            "LBE:PROF-01:POS_RB": r.prof_in,
            # --- grandeurs machine
            "LBE:MACH-01:TRANS": 100.0 * (acct2 / acct1 if acct1 > 1e-6 else 0.0),
            "LBE:MACH-01:LOSS": perte,
            "LBE:MACH-01:LOSS_W": perte_w,
            "LBE:MACH-01:AQ_RB": r.aq_vise,      # écho : personne ne mesure la cible
        }
        for nom, p in pressions.items():
            m[f"LBE:{nom}:P"] = bruit(p, c.bruit_vide)
            m[f"LBE:{nom}:T"] = self._t_chambres[nom] + a.gauss(0.0, 0.03)

        m.update(self._etats(acct1, perte_w))
        m["LBE:SRC-01:SPARK_CNT"] = self._claquages
        m["LBE:MACH-01:SPECIES"] = self.espece
        return m

    def _etats(self, acct1: float, perte_w: float) -> dict[str, str]:
        """Les états discrets. Un verrouillage n'est pas décoratif : il traduit
        une grandeur physique qui a franchi une limite matérielle."""
        c = self.cte
        chaud = {n: self._t_bobines[n] > 70.0 for n in self._t_bobines}
        alim = "DEFAUT" if self.defauts.alim_sol1_morte else "MARCHE"
        return {
            "LBE:SRC-01:STATE": "MARCHE" if self.r.hf_p > 1 else "ARRET",
            "LBE:SOL-01:ITLK": "DEFAUT" if chaud["SOL-01"] else "OK",
            "LBE:SOL-01:STATE": alim,
            "LBE:SOL-02:ITLK": "DEFAUT" if chaud["SOL-02"] else "OK",
            "LBE:SOL-02:STATE": "MARCHE",
            "LBE:DIP-01:ITLK": "DEFAUT" if chaud["DIP-01"] else "OK",
            "LBE:DIP-01:STATE": "MARCHE",
            "LBE:STE-01:STATE": "MARCHE",
            "LBE:SLT-01:STATE": "MARCHE",
            "LBE:VAC-01:VALVE": "OUVERTE",
            "LBE:VAC-01:STATE": "NOMINAL",
            "LBE:VAC-02:VALVE": "FERMEE" if self.defauts.vanne_02_fermee else "OUVERTE",
            "LBE:VAC-02:STATE": "DEFAUT" if self.defauts.vanne_02_fermee else "NOMINAL",
            "LBE:VAC-03:VALVE": "OUVERTE",
            "LBE:VAC-03:STATE": "NOMINAL",
            "LBE:MACH-01:MODE": self.mode,
            "LBE:MACH-01:BEAM": "PRESENT" if acct1 > 20.0 else "ABSENT",
        }

    # -- pilotage ----------------------------------------------------------

    def ecrire(self, consigne: str, valeur: float) -> None:
        """Applique un `caput` sur une consigne, par son nom de PV."""
        champ = _CONSIGNES.get(consigne)
        if champ is None:
            raise KeyError(f"{consigne} n'est pas une consigne pilotable")
        setattr(self.r, champ, valeur)

    def injecter(self, **kwargs) -> None:
        """Installe un défaut : `injecter(fuite_vide=1.7e-7)`."""
        self.defauts = replace(self.defauts, **kwargs)


#: Correspondance consigne EPICS → attribut de `Reglages`. C'est le seul
#: endroit où les deux vocabulaires se rencontrent.
_CONSIGNES: dict[str, str] = {
    "LBE:SRC-01:HF_P_SP": "hf_p",
    "LBE:SRC-01:GAS_Q_SP": "gas_q",
    "LBE:SRC-01:HT_U_SP": "ht_u",
    "LBE:COIL-INJ:I_SP": "coil_inj_i",
    "LBE:COIL-EXT:I_SP": "coil_ext_i",
    "LBE:SOL-01:I_SP": "sol1_i",
    "LBE:SOL-02:I_SP": "sol2_i",
    "LBE:DIP-01:I_SP": "dip_i",
    "LBE:STE-01:IH_SP": "ste_ih",
    "LBE:STE-01:IV_SP": "ste_iv",
    "LBE:SLT-01:GAP_SP": "slt_gap",
    "LBE:SLT-01:POS_SP": "slt_pos",
    "LBE:FC-01:POS_SP": "fc_in",
    "LBE:PROF-01:POS_SP": "prof_in",
    "LBE:MACH-01:AQ_SP": "aq_vise",
}
