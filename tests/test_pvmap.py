"""La base de PV est un contrat : ces tests le figent."""

import pytest

from sim.pvmap import check, expand


@pytest.fixture(scope="module")
def pvs():
    return expand()


def test_la_base_est_coherente(pvs):
    assert check(pvs) == []


def test_les_noms_suivent_la_convention(pvs):
    for pv in pvs:
        parts = pv.name.split(":")
        assert len(parts) == 3, f"{pv.name} n'a pas trois segments"
        ligne, equipement, _signal = parts
        assert ligne == "LBE"
        assert "-" in equipement, f"{equipement} n'a pas de numéro d'instance"


def test_chaque_consigne_a_sa_mesure(pvs):
    noms = {pv.name for pv in pvs}
    consignes = [pv for pv in pvs if pv.is_setpoint]
    assert consignes, "aucune consigne dans la base"
    for pv in consignes:
        assert pv.name.replace("_SP", "_RB") in noms


def test_aucune_alarme_sur_une_consigne(pvs):
    """Une consigne est une décision humaine, pas un état de la machine."""
    for pv in pvs:
        if pv.is_setpoint:
            assert pv.alarm == {}


def test_les_grandeurs_critiques_sont_surveillees(pvs):
    """Transmission, perte, vide et position doivent porter des seuils."""
    surveillees = {pv.name for pv in pvs if pv.alarm}
    for nom in (
        "LBE:MACH-01:TRANS",
        "LBE:MACH-01:LOSS",
        "LBE:VAC-01:P",
        "LBE:BPM-01:X",
        "LBE:ACCT-01:ITF",
    ):
        assert nom in surveillees, f"{nom} devrait porter des seuils d'alarme"


def test_la_taille_de_la_base_est_stable(pvs):
    """Garde-fou : un ajout non intentionnel doit se voir en revue."""
    assert len(pvs) == 75
