"""Chargement de la base de PV déclarative.

Le fichier ``config/pv_map.yaml`` décrit des *équipements* et leurs *signaux*.
Les noms de PV n'y figurent pas : ils sont dérivés ici, par une règle unique.
C'est le même principe que la base de configuration d'un vrai système de
contrôle — on décrit le matériel, le nommage en découle.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_MAP = Path(__file__).resolve().parent.parent / "config" / "pv_map.yaml"

#: Suffixes engendrés par chaque nature de signal.
KIND_SUFFIXES: dict[str, tuple[str, ...]] = {
    "pair": ("_SP", "_RB"),
    "ro": ("",),
    "state": ("",),
    "counter": ("",),
    "text": ("",),
}

#: De quoi un canal parle. Décidé en revue (question 2) : un incident faisceau
#: ne se propage que dans `faisceau` et `derive` ; un canal `equipement` ne
#: bouge que si quelqu'un ou un défaut agit sur le matériel. La causalité est
#: donc connue d'avance, et à sens unique.
DOMAINS = frozenset({"equipement", "procede", "faisceau", "derive", "contexte"})

#: Sur quoi un seuil se justifie. Décidé en revue (question 4) : un seuil de
#: protection découle de ce que le matériel supporte — il est fixe et sa place
#: est dans cette base. Un seuil d'exploitation découle de ce que la campagne
#: du jour attend — il n'est ici qu'une valeur par défaut.
ALARM_KINDS = frozenset({"protection", "exploitation"})

#: Type de record EPICS retenu pour chaque nature de signal.
KIND_RECORDS: dict[str, dict[str, str]] = {
    "pair": {"_SP": "ao", "_RB": "ai"},
    "ro": {"": "ai"},
    "state": {"": "mbbi"},
    "counter": {"": "longin"},
    "text": {"": "stringin"},
}


@dataclass(frozen=True)
class PV:
    """Une variable de procédé, telle qu'elle sera servie par l'IOC."""

    name: str
    device: str
    device_type: str
    signal: str
    role: str  # setpoint | readback | state | counter
    record: str
    egu: str = ""
    prec: int = 3
    value: Any = 0.0
    lo: float | None = None
    hi: float | None = None
    states: tuple[str, ...] = ()
    domain: str = ""
    derived_from: tuple[str, ...] = ()
    alarm: dict[str, Any] = field(default_factory=dict)
    desc_fr: str = ""
    desc_en: str = ""

    @property
    def is_setpoint(self) -> bool:
        return self.role == "setpoint"

    @property
    def is_independent(self) -> bool:
        """Un canal dérivé n'est pas un témoin : il répète ce que disent
        les canaux dont il est calculé."""
        return self.domain != "derive"


def _role(kind: str, suffix: str) -> str:
    if kind == "pair":
        return "setpoint" if suffix == "_SP" else "readback"
    return {"ro": "readback", "state": "state",
            "counter": "counter", "text": "context"}[kind]


def load(path: str | Path = DEFAULT_MAP) -> dict[str, Any]:
    """Lit le YAML brut, sans interprétation."""
    with open(path, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def expand(spec: dict[str, Any] | None = None) -> list[PV]:
    """Déplie les équipements en liste de PV.

    La règle de nommage, et elle seule :
    ``<LIGNE>:<ÉQUIPEMENT>:<SIGNAL><SUFFIXE>``
    """
    spec = spec if spec is not None else load()
    line = spec["line"]
    defaults = spec.get("defaults", {})
    pvs: list[PV] = []

    for device in spec["devices"]:
        for signal in device["signals"]:
            kind = signal["kind"]
            if kind not in KIND_SUFFIXES:
                raise ValueError(f"nature de signal inconnue : {kind!r}")
            for suffix in KIND_SUFFIXES[kind]:
                pvs.append(
                    PV(
                        name=f"{line}:{device['id']}:{signal['sig']}{suffix}",
                        device=device["id"],
                        device_type=device["type"],
                        signal=signal["sig"],
                        role=_role(kind, suffix),
                        record=KIND_RECORDS[kind][suffix],
                        egu=signal.get("egu", ""),
                        prec=signal.get("prec", defaults.get("prec", 3)),
                        value=signal.get("value", 0),
                        lo=signal.get("lo"),
                        hi=signal.get("hi"),
                        states=tuple(signal.get("states", ())),
                        domain=signal.get("domain", device.get("domain", "")),
                        derived_from=tuple(signal.get("from", ())),
                        # Une consigne ne porte pas d'alarme : c'est une
                        # décision humaine, pas un état de la machine.
                        alarm={} if suffix == "_SP" else signal.get("alarm", {}),
                        desc_fr=signal.get("desc_fr", ""),
                        desc_en=signal.get("desc_en", ""),
                    )
                )
    return pvs


def check(pvs: list[PV]) -> list[str]:
    """Contrôles de cohérence. Retourne la liste des anomalies trouvées."""
    problems: list[str] = []

    seen: set[str] = set()
    for pv in pvs:
        if pv.name in seen:
            problems.append(f"nom de PV en double : {pv.name}")
        seen.add(pv.name)

    for pv in pvs:
        if pv.role in ("setpoint", "readback") and pv.record in ("ai", "ao"):
            if not pv.egu and pv.signal not in ("POS", "AQ"):
                problems.append(f"{pv.name} : unité manquante")
        if not pv.desc_fr or not pv.desc_en:
            problems.append(f"{pv.name} : description bilingue incomplète")
        if pv.role == "state" and not pv.states:
            problems.append(f"{pv.name} : aucun état déclaré")
        if pv.domain not in DOMAINS:
            problems.append(f"{pv.name} : domaine absent ou inconnu ({pv.domain!r})")
        if pv.domain == "derive" and not pv.derived_from:
            problems.append(f"{pv.name} : canal dérivé sans `from:`")
        if pv.domain != "derive" and pv.derived_from:
            problems.append(f"{pv.name} : `from:` sur un canal non dérivé")
        if pv.alarm and pv.alarm.get("kind") not in ALARM_KINDS:
            problems.append(f"{pv.name} : seuil sans justification "
                            "(`kind: protection` ou `exploitation`)")

        a = pv.alarm
        if a:
            order = [a.get(k) for k in ("lolo", "low", "high", "hihi")]
            present = [v for v in order if v is not None]
            if present != sorted(present):
                problems.append(f"{pv.name} : seuils d'alarme non ordonnés")
            if pv.lo is not None and any(v < pv.lo for v in present):
                problems.append(f"{pv.name} : seuil sous la borne basse")
            if pv.hi is not None and any(v > pv.hi for v in present):
                problems.append(f"{pv.name} : seuil au-dessus de la borne haute")

    names = {pv.name for pv in pvs}
    for pv in pvs:
        for source in pv.derived_from:
            if source not in names:
                problems.append(f"{pv.name} : dérivé de {source}, qui n'existe pas")

    # Toute consigne doit avoir sa mesure en vis-à-vis.
    for pv in pvs:
        if pv.is_setpoint and pv.name.replace("_SP", "_RB") not in names:
            problems.append(f"{pv.name} : pas de mesure `_RB` correspondante")

    return problems


def main() -> int:
    pvs = expand()
    width = max(len(pv.name) for pv in pvs)
    for pv in pvs:
        flag = "!" if pv.alarm else " "
        print(f"{flag} {pv.name:<{width}}  {pv.record:<7} {pv.domain:<11} "
              f"{pv.egu:<5} {pv.desc_fr}")

    problems = check(pvs)
    roles = {r: sum(1 for pv in pvs if pv.role == r) for r in
             ("setpoint", "readback", "state", "counter", "context")}
    print(f"\n{len(pvs)} PV sur {len({pv.device for pv in pvs})} équipements — "
          + ", ".join(f"{n} {r}" for r, n in roles.items()))
    kinds = {k: sum(1 for pv in pvs if pv.alarm.get("kind") == k)
             for k in sorted(ALARM_KINDS)}
    print(f"{sum(1 for pv in pvs if pv.alarm)} PV portent des seuils d'alarme — "
          + ", ".join(f"{n} {k}" for k, n in kinds.items()))
    domains = {d: sum(1 for pv in pvs if pv.domain == d) for d in sorted(DOMAINS)}
    print("domaines — " + ", ".join(f"{n} {d}" for d, n in domains.items()))
    print(f"{sum(1 for pv in pvs if not pv.is_independent)} canaux dérivés : "
          "à ne jamais compter comme témoins indépendants")

    if problems:
        print(f"\n{len(problems)} anomalie(s) :")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("Base cohérente.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
