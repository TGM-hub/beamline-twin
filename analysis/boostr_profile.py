"""Profil statistique du jeu BOOSTR (Booster de Fermilab, 15 Hz, 24 h).

But : calibrer le simulateur de la LBE sur des ordres de grandeur réels plutôt
que sur l'imagination. Le Booster n'est pas la LBE — synchrotron rapide contre
ligne basse énergie — mais trois questions ne s'inventent pas, et leurs réponses
se transposent :

  1. Quelle est la part de bruit rapide et la part de dérive lente ?
  2. Combien de canaux, dans un vrai jeu, portent réellement de l'information ?
  3. À quoi ressemble un changement de consigne : combien par jour, de quelle
     amplitude, et sont-ils tous d'origine humaine ?

Convention ACNET de Fermilab, qui tombe bien : `B:XXX` est une **lecture**,
`B_XXX` la **consigne** correspondante. C'est leur `_RB` / `_SP`.

Note méthodologique : une première version estimait un temps de corrélation de
la dérive par autocorrélation. Le résultat variait d'un facteur 10 selon la
fenêtre (56 s à 581 s pour le même canal) — la dérive n'est pas stationnaire sur
24 h et l'estimateur ne tient pas. Il a été retiré plutôt que publié. On s'en
tient au **rapport bruit / dérive**, qui lui est robuste.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

SOURCE = Path(__file__).resolve().parent.parent / "data" / "boostr" / "data release.csv"
SORTIE = Path(__file__).resolve().parent / "boostr_profile.csv"

HZ = 15                      # cadence du Booster : une ligne par cycle
LISSAGE_COURT = HZ           # 1 seconde  — sépare le bruit du reste
LISSAGE_LONG = HZ * 60       # 1 minute   — ce qui reste est la dérive


def charger() -> pd.DataFrame:
    df = pd.read_csv(SOURCE, usecols=lambda c: c != "file", parse_dates=["time"])
    return df.set_index("time")


def est_consigne(colonne: str) -> bool:
    """`B_XXX` est une consigne, `B:XXX` et `I:XXX` sont des lectures."""
    return "_" in colonne.split(":")[0]


def profiler(x: pd.Series) -> dict:
    x = x.dropna()
    if x.empty:
        return {}
    bruit = (x - x.rolling(LISSAGE_COURT, center=True, min_periods=1).mean()).std()
    derive = x.rolling(LISSAGE_LONG, center=True, min_periods=1).mean().std()
    sauts = x.diff()
    bouges = sauts[sauts != 0].dropna()
    return {
        "nature": "consigne" if est_consigne(str(x.name)) else "lecture",
        "moyenne": x.mean(),
        "min": x.min(),
        "max": x.max(),
        "bruit": bruit,
        "derive": derive,
        # Le rapport, et non les valeurs absolues : c'est lui qui se transpose
        # d'une machine à l'autre.
        "bruit_sur_derive": bruit / derive if derive else np.nan,
        "bruit_sur_moyenne_pct": 100 * bruit / abs(x.mean()) if x.mean() else np.nan,
        "changements_24h": len(bouges),
        "saut_median": bouges.abs().median() if len(bouges) else np.nan,
        "saut_median_sur_etendue_pct": (
            100 * bouges.abs().median() / (x.max() - x.min())
            if len(bouges) and x.max() > x.min() else np.nan),
    }


def paires(df: pd.DataFrame) -> pd.DataFrame:
    """Une lecture qui recopie sa consigne n'est pas une mesure."""
    lignes = {}
    for lecture in (c for c in df.columns if not est_consigne(c)):
        consigne = lecture.replace(":", "_", 1)
        if consigne in df.columns:
            a, b = df[lecture], df[consigne]
            lignes[lecture] = {
                "consigne": consigne,
                "identiques_pct": 100 * float((a == b).mean()),
                "correlation": a.corr(b),
                "mesure_reelle": bool((a == b).mean() < 0.99),
            }
    return pd.DataFrame(lignes).T


def main() -> int:
    df = charger()
    ecarts = df.index.to_series().diff().dt.total_seconds().dropna()
    print(f"{len(df):,} lignes × {df.shape[1]} canaux, "
          f"du {df.index[0]:%Y-%m-%d %H:%M} au {df.index[-1]:%Y-%m-%d %H:%M}")
    print(f"intervalle : médiane {ecarts.median()*1000:.0f} ms, "
          f"p99 {ecarts.quantile(0.99)*1000:.0f} ms, max {ecarts.max()*1000:.0f} ms — "
          f"{100*ecarts.between(0.06, 0.075).mean():.2f} % réguliers")
    print("→ échantillonnage synchrone du cycle, PAS à bande morte.\n")

    profil = pd.DataFrame({c: profiler(df[c]) for c in df.columns}).T
    profil.index.name = "canal"
    profil.to_csv(SORTIE)

    fige = profil[profil["changements_24h"] == 0]
    print(f"canaux figés sur 24 h : {len(fige)} / {len(profil)} "
          f"({100*len(fige)/len(profil):.0f} %)")
    print("  " + ", ".join(fige.index) + "\n")

    pd.set_option("display.width", 200, "display.max_columns", 20)
    actifs = profil[profil["changements_24h"] > 0]
    print("--- canaux actifs " + "-" * 60)
    print(actifs[["nature", "moyenne", "bruit", "derive", "bruit_sur_derive",
                  "bruit_sur_moyenne_pct", "changements_24h", "saut_median"]]
          .to_string(float_format=lambda v: f"{v:.4g}"))

    print("\n--- lecture contre consigne " + "-" * 50)
    p = paires(df)
    print(p.to_string())
    vraies = p[p["mesure_reelle"]]
    print(f"\n{len(vraies)} / {len(p)} lectures sont de vraies mesures. "
          f"Les {len(p)-len(vraies)} autres recopient leur consigne.")
    print(f"\nprofil complet écrit dans {SORTIE.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
