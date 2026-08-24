"""Módulo de cálculo de Splits Situacionales para LIDOM (Clutch, RISP, Bases Llenas, Por Inning)."""

from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np


def is_risp(base_index: int) -> bool:
    """Retorna True si hay corredor en 2da o 3ra base (índices 2, 3, 4, 5, 6, 7)."""
    # bit 1 = 2da base, bit 2 = 3ra base
    return (base_index & 2 != 0) or (base_index & 4 != 0)


def is_bases_loaded(base_index: int) -> bool:
    """Retorna True si las bases están llenas (índice 7 = 111b)."""
    return base_index == 7


def calculate_sabermetric_slash(df_plays: pd.DataFrame) -> Dict[str, Any]:
    """Calcula la línea sabermétrica (PA, AB, H, 2B, 3B, HR, BB, SO, AVG, OBP, SLG, OPS, wOBA) de un conjunto de jugadas."""
    if df_plays.empty:
        return {
            "PA": 0, "AB": 0, "H": 0, "2B": 0, "3B": 0, "HR": 0,
            "BB": 0, "SO": 0, "AVG": ".000", "OBP": ".000", "SLG": ".000", "OPS": ".000",
            "wOBA": ".000", "Hard_pct": "0.0%",
        }

    events = df_plays["event"].str.lower().fillna("") if "event" in df_plays else pd.Series([""] * len(df_plays))
    
    hits_1b = events.str.contains("single|sencillo").sum()
    hits_2b = events.str.contains("double|doble").sum()
    hits_3b = events.str.contains("triple").sum()
    hits_hr = events.str.contains("home_run|home run|jonrón").sum()
    total_hits = hits_1b + hits_2b + hits_3b + hits_hr

    walks = events.str.contains("walk|base_on_balls|bb|boleto").sum()
    hbp = events.str.contains("hit_by_pitch|hbp|golpeado").sum()
    strikeouts = events.str.contains("strikeout|ponche|so").sum()
    sac_flies = events.str.contains("sac_fly|sf").sum()

    total_pa = len(df_plays)
    at_bats = max(1, total_pa - walks - hbp - sac_flies)

    avg = total_hits / at_bats
    obp_denom = max(1, at_bats + walks + hbp + sac_flies)
    obp = (total_hits + walks + hbp) / obp_denom
    total_bases = hits_1b + (2 * hits_2b) + (3 * hits_3b) + (4 * hits_hr)
    slg = total_bases / at_bats
    ops = obp + slg

    # Constantes LIDOM aproximadas de wOBA
    woba = ((0.69 * walks) + (0.72 * hbp) + (0.88 * hits_1b) + (1.24 * hits_2b) + (1.56 * hits_3b) + (2.02 * hits_hr)) / obp_denom

    hard_count = 0
    if "hardness" in df_plays:
        hard_count = (df_plays["hardness"] == "Hard").sum()
    hard_pct = (hard_count / total_pa * 100) if total_pa > 0 else 0.0

    return {
        "PA": total_pa,
        "AB": at_bats,
        "H": total_hits,
        "2B": hits_2b,
        "3B": hits_3b,
        "HR": hits_hr,
        "BB": walks,
        "SO": strikeouts,
        "AVG": f"{avg:.3f}".lstrip("0") if avg < 1.0 else f"{avg:.3f}",
        "OBP": f"{obp:.3f}".lstrip("0") if obp < 1.0 else f"{obp:.3f}",
        "SLG": f"{slg:.3f}".lstrip("0") if slg < 1.0 else f"{slg:.3f}",
        "OPS": f"{ops:.3f}".lstrip("0") if ops < 1.0 else f"{ops:.3f}",
        "wOBA": f"{woba:.3f}".lstrip("0") if woba < 1.0 else f"{woba:.3f}",
        "Hard_pct": f"{hard_pct:.1f}%",
    }


def get_situational_splits(df_plays: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    """
    Genera un diccionario completo con los diferentes splits:
    - General
    - RISP (Posición Anotadora)
    - Bases Llenas
    - Situaciones Clutch (LEI >= 1.5 o Inning 7+ diff <= 2)
    - Inning 1-3 (Temprano)
    - Inning 4-6 (Medio)
    - Inning 7+ (Finales)
    """
    if df_plays.empty:
        return {}

    splits = {}
    splits["General"] = calculate_sabermetric_slash(df_plays)

    # RISP
    if "base_state" in df_plays:
        risp_mask = df_plays["base_state"].apply(is_risp)
        splits["RISP (Posición Anotadora)"] = calculate_sabermetric_slash(df_plays[risp_mask])

        # Bases Llenas
        loaded_mask = df_plays["base_state"].apply(is_bases_loaded)
        splits["Bases Llenas"] = calculate_sabermetric_slash(df_plays[loaded_mask])
    else:
        splits["RISP (Posición Anotadora)"] = calculate_sabermetric_slash(df_plays)
        splits["Bases Llenas"] = calculate_sabermetric_slash(df_plays)

    # Clutch (LEI >= 1.5)
    if "leverage_index" in df_plays:
        clutch_mask = df_plays["leverage_index"] >= 1.5
        splits["Clutch (Alto Apalancamiento LI≥1.5)"] = calculate_sabermetric_slash(df_plays[clutch_mask])
    elif "inning" in df_plays and "score_diff" in df_plays:
        clutch_mask = (df_plays["inning"] >= 7) & (df_plays["score_diff"].abs() <= 2)
        splits["Clutch (Inning 7+ Diferencia ≤2)"] = calculate_sabermetric_slash(df_plays[clutch_mask])
    else:
        splits["Clutch"] = calculate_sabermetric_slash(df_plays)

    # Por Inning
    if "inning" in df_plays:
        splits["Innings 1-3 (Temprano)"] = calculate_sabermetric_slash(df_plays[df_plays["inning"] <= 3])
        splits["Innings 4-6 (Medio)"] = calculate_sabermetric_slash(df_plays[(df_plays["inning"] >= 4) & (df_plays["inning"] <= 6)])
        splits["Innings 7+ (Tardío)"] = calculate_sabermetric_slash(df_plays[df_plays["inning"] >= 7])

    return splits
