"""Le simulateur doit raconter la même machine que la base de PV."""

import pytest

from sim.beamline import Machine, Reglages, _CONSIGNES
from sim.pvmap import expand


@pytest.fixture(scope="module")
def pvs():
    return expand()


@pytest.fixture()
def machine():
    m = Machine(graine=42)
    for _ in range(7200):       # deux heures : les températures se stabilisent
        m.pas(1.0)
    return m


# --- le contrat entre les deux fichiers ------------------------------------

def test_le_simulateur_produit_exactement_les_pv_declarees(pvs, machine):
    attendus = {pv.name for pv in pvs if not pv.is_setpoint}
    produits = set(machine.mesures())
    assert produits == attendus


def test_toutes_les_consignes_sont_pilotables(pvs):
    consignes = {pv.name for pv in pvs if pv.is_setpoint}
    assert set(_CONSIGNES) == consignes


def test_une_consigne_inconnue_est_refusee(machine):
    with pytest.raises(KeyError):
        machine.ecrire("LBE:SRC-01:INVENTE_SP", 1.0)


# --- le point de fonctionnement nominal ------------------------------------

def test_le_nominal_correspond_aux_valeurs_declarees(machine):
    """Le YAML annonce 92 % de transmission, 65 µA de perte, 2,6 W."""
    m = machine.mesures()
    assert 90.0 < m["LBE:MACH-01:TRANS"] < 94.0
    assert 55.0 < m["LBE:MACH-01:LOSS"] < 78.0
    assert 2.2 < m["LBE:MACH-01:LOSS_W"] < 3.1
    assert m["LBE:DIP-01:AQ"] == pytest.approx(3.2, abs=0.02)


def test_le_bruit_faisceau_est_commun_donc_la_transmission_est_calme(machine):
    """Les deux ACCT regardent le même faisceau : le bruit s'annule dans leur
    rapport. Sans ça, la transmission tremblerait trop pour être exploitable."""
    import statistics as st
    trans, intensite = [], []
    for _ in range(400):
        machine.pas(1.0)
        m = machine.mesures()
        trans.append(m["LBE:MACH-01:TRANS"])
        intensite.append(m["LBE:ACCT-01:ITF"])
    bruit_faisceau = st.stdev(intensite) / st.mean(intensite)
    bruit_transmission = st.stdev(trans) / st.mean(trans)
    assert bruit_transmission < bruit_faisceau / 3


# --- la physique fait ce qu'on attend d'elle -------------------------------

def test_desaccorder_un_solenoide_fait_chuter_la_transmission(machine):
    avant = machine.mesures()["LBE:MACH-01:TRANS"]
    machine.ecrire("LBE:SOL-01:I_SP", 118.0 + 40.0)
    machine.pas(1.0)
    assert machine.mesures()["LBE:MACH-01:TRANS"] < avant - 20.0


def test_le_dipole_selectionne_un_rapport_masse_sur_charge(machine):
    """A/Q ∝ B²/U : monter le champ transmet une espèce plus lourde."""
    avant = machine.mesures()["LBE:DIP-01:AQ"]
    machine.ecrire("LBE:DIP-01:I_SP", 214.0 * 1.10)
    machine.pas(1.0)
    apres = machine.mesures()["LBE:DIP-01:AQ"]
    assert apres == pytest.approx(avant * 1.10 ** 2, rel=1e-3)


def test_monter_la_tension_deplace_le_aq_transmis(machine):
    """Couplage entre deux réglages : un modèle devra le découvrir."""
    avant = machine.mesures()["LBE:DIP-01:AQ"]
    machine.ecrire("LBE:SRC-01:HT_U_SP", 44.0)
    machine.pas(1.0)
    assert machine.mesures()["LBE:DIP-01:AQ"] < avant


def test_la_cage_de_faraday_arrete_le_faisceau(machine):
    machine.ecrire("LBE:FC-01:POS_SP", 1)
    machine.pas(1.0)
    m = machine.mesures()
    assert m["LBE:ACCT-02:ITF"] == 0.0
    assert m["LBE:FC-01:ITF"] > 100.0


# --- le scénario de panne de la revue, question 2 --------------------------

def test_le_courant_debite_monte_avec_la_pression(machine):
    """`HT_I` répond au gaz résiduel : c'est un second témoin d'une fuite,
    indépendant de la transmission. C'est aussi pourquoi il est classé
    `faisceau` et non `equipement`."""
    depart = machine.mesures()["LBE:SRC-01:HT_I"]
    machine.injecter(fuite_vide=1.7e-7, fuite_tau=3600)
    for _ in range(6 * 3600):
        machine.pas(1.0)
    assert machine.mesures()["LBE:SRC-01:HT_I"] > depart * 1.05


def test_une_fuite_de_vide_degrade_la_transmission(machine):
    depart = machine.mesures()
    machine.injecter(fuite_vide=1.7e-7, fuite_tau=3600)
    for _ in range(6 * 3600):
        machine.pas(1.0)
    arrivee = machine.mesures()

    assert arrivee["LBE:VAC-02:P"] > 5 * depart["LBE:VAC-02:P"]
    assert arrivee["LBE:MACH-01:TRANS"] < depart["LBE:MACH-01:TRANS"] - 2.0
    assert arrivee["LBE:MACH-01:LOSS"] > depart["LBE:MACH-01:LOSS"] * 1.2


def test_la_fuite_chauffe_la_chambre_qui_degaze(machine):
    """La boucle : perte → échauffement → dégazage → perte."""
    depart = machine.mesures()["LBE:VAC-02:T"]
    machine.injecter(fuite_vide=1.7e-7, fuite_tau=3600)
    for _ in range(6 * 3600):
        machine.pas(1.0)
    # +0,7 °C pour 1,5 W de perte supplémentaire : l'effet est petit, mais il
    # est réel et c'est lui qui referme la boucle sur la pression.
    assert machine.mesures()["LBE:VAC-02:T"] > depart + 0.5


def test_les_canaux_d_equipement_ignorent_l_incident(machine, pvs):
    """Revue Q2 : un incident faisceau ne se propage que dans les canaux de
    faisceau, de procédé et dérivés. Le champ d'un aimant suit son
    alimentation, pas le faisceau qui le traverse."""
    equipement = [pv.name for pv in pvs
                  if pv.domain == "equipement" and not pv.is_setpoint
                  and pv.record == "ai"]
    def moyennes() -> dict[str, float]:
        """On compare des moyennes, pas des échantillons : un écart d'un seul
        point ne dit rien face au bruit de mesure."""
        cumul = {nom: 0.0 for nom in equipement}
        for _ in range(30):
            machine.pas(1.0)
            m = machine.mesures()
            for nom in equipement:
                cumul[nom] += m[nom] / 30
        return cumul

    depart = moyennes()
    machine.injecter(fuite_vide=1.7e-7, fuite_tau=3600)
    for _ in range(6 * 3600):
        machine.pas(1.0)
    arrivee = moyennes()
    for nom in equipement:
        ecart = abs(arrivee[nom] - depart[nom]) / max(abs(depart[nom]), 1e-9)
        assert ecart < 0.002, f"{nom} a bougé de {100*ecart:.3f} % pendant une fuite"


def test_la_transmission_reste_au_dessus_du_seuil_operateur(machine):
    """Le scénario de démo : la fuite doit être détectable par un modèle
    AVANT que l'alarme LOW de TRANS (85 %) ne se déclenche. Sinon le modèle
    n'apporte rien."""
    machine.injecter(fuite_vide=1.7e-7, fuite_tau=3600)
    for _ in range(6 * 3600):
        machine.pas(1.0)
    assert machine.mesures()["LBE:MACH-01:TRANS"] > 85.0


# --- la bande morte : le bug du 11 septembre ------------------------------

def test_une_jauge_a_vide_recoit_une_bande_morte_relative(pvs):
    """Une bande morte absolue sur un canal logarithmique le rend muet.

    `VAC-02:P` est déclarée de 1e-10 à 1e-3 mbar. Une bande morte à 0,1 % de
    l'étendue vaut 1e-6 — plus large que toute la vie du signal, qui se joue
    entre 3e-8 et 2e-7. Le canal n'émettait plus jamais, même pendant une
    fuite, et ça n'a été vu qu'en s'en servant pour de vrai.
    """
    from sim.ioc import _bande_morte

    par_nom = {pv.name: pv for pv in pvs}
    vide = _bande_morte(par_nom["LBE:VAC-02:P"], 0.001, 0.05)
    assert vide.relative > 0 and vide.absolue == 0
    assert vide.seuil(3.05e-8) < 2e-9      # bien en deçà de la fuite à détecter

    courant = _bande_morte(par_nom["LBE:SOL-01:I_RB"], 0.001, 0.05)
    assert courant.absolue > 0 and courant.relative == 0


def test_la_jauge_parle_pendant_une_fuite_et_se_tait_au_repos(machine, pvs):
    """Le test qui interdit au bug de revenir : on rejoue la décision de
    publication de l'IOC, sans serveur."""
    from sim.ioc import _bande_morte, doit_publier

    par_nom = {pv.name: pv for pv in pvs}
    bande = _bande_morte(par_nom["LBE:VAC-02:P"], 0.001, 0.05)

    def notifications(pas: int) -> int:
        publie, compte = None, 0
        for _ in range(pas):
            machine.pas(10.0)
            valeur = machine.mesures()["LBE:VAC-02:P"]
            if doit_publier(valeur, publie, bande):
                publie, compte = valeur, compte + 1
        return compte

    au_repos = notifications(200)
    machine.injecter(fuite_vide=1.7e-7, fuite_tau=3600)
    pendant = notifications(200)

    # Mesuré : 2 notifications au repos, 19 pendant la fuite. On teste le
    # contraste, pas les valeurs exactes, qui dépendent du tirage aléatoire.
    assert pendant >= 5 * max(au_repos, 1), (
        f"la jauge doit parler franchement pendant une fuite "
        f"({pendant} notifications) et se taire au repos ({au_repos})")
    assert pendant >= 8, "une fuite doit produire des notifications, pas le silence"


def test_un_canal_stable_reste_silencieux(machine, pvs):
    """L'autre moitié du contrat : la bande morte doit vraiment se taire."""
    from sim.ioc import _bande_morte, doit_publier

    par_nom = {pv.name: pv for pv in pvs}
    compte = {}
    for nom in ("LBE:SOL-01:I_RB", "LBE:DIP-01:B", "LBE:SRC-01:HT_U_RB"):
        bande = _bande_morte(par_nom[nom], 0.001, 0.05)
        publie, n = None, 0
        for _ in range(200):
            machine.pas(1.0)
            valeur = machine.mesures()[nom]
            if doit_publier(valeur, publie, bande):
                publie, n = valeur, n + 1
        compte[nom] = n
    assert all(n <= 2 for n in compte.values()), compte
