"""Motor de Run Expectancy (RE24 Tango), Win Expectancy (WE) y Win Probability Added (WPA) para LIDOM."""

import math
from typing import Dict, Any, Tuple, Optional

# Matriz RE24 Estándar de Tango (Outs: 0, 1, 2 x 8 estados de corredores en base)
# Estados: 0=Empty, 1=1st, 2=2nd, 3=3rd, 4=1st&2nd, 5=1st&3rd, 6=2nd&3rd, 7=Bases Loaded
RE24_MATRIX = {
    0: [0.481, 0.859, 1.100, 1.350, 1.437, 1.784, 1.964, 2.292],
    1: [0.254, 0.509, 0.664, 0.950, 0.884, 1.130, 1.376, 1.541],
    2: [0.098, 0.214, 0.305, 0.353, 0.429, 0.478, 0.570, 0.752],
}


def get_base_state_index(first: bool = False, second: bool = False, third: bool = False) -> int:
    """Retorna el índice del estado de base (0 a 7)."""
    return (1 if first else 0) | ((1 if second else 0) << 1) | ((1 if third else 0) << 2)


def get_run_expectancy(outs: int, base_index: int) -> float:
    """Retorna las carreras esperadas para el inning actual dado outs y estado de base."""
    outs_clamped = min(max(outs, 0), 2)
    base_clamped = min(max(base_index, 0), 7)
    return RE24_MATRIX[outs_clamped][base_clamped]


def calculate_win_expectancy(
    inning: int,
    is_bottom: bool,
    outs: int,
    base_state_index: int,
    score_diff: int,  # home_score - away_score
) -> float:
    """
    Calcula la probabilidad de victoria (Win Expectancy) del equipo LOCAL (Home Team)
    en base al inning, mitad de inning, outs, corredores y diferencia de carreras.
    """
    # Si el juego ya terminó en extra innings o walk-off
    if inning >= 9 and is_bottom and score_diff > 0:
        return 1.000
    if inning >= 9 and not is_bottom and outs >= 3:
        if score_diff > 0:
            return 1.000
        elif score_diff < 0:
            return 0.000

    # Inning 9 o extra innings
    effective_inning = min(inning, 12)
    # Entradas restantes
    innings_remaining = max(9.0 - (effective_inning - 1.0) - (0.5 if is_bottom else 0.0), 0.5)

    # Carreras esperadas del equipo bateando en este medio inning
    re_curr = get_run_expectancy(outs, base_state_index)

    # Ventaja de carreras esperada para el equipo local
    if is_bottom:
        # Batea Home
        expected_diff = score_diff + re_curr - (innings_remaining - 0.5) * 0.05
    else:
        # Batea Away
        expected_diff = score_diff - re_curr + (innings_remaining - 0.5) * 0.05

    # Varianza acumulada restante
    variance = math.sqrt(innings_remaining * 1.55 + 0.4)
    # Función sigmoide / logística ajustada
    z = expected_diff / variance
    we_home = 1.0 / (1.0 + math.exp(-0.85 * z))

    return min(max(we_home, 0.001), 0.999)


def calculate_leverage_index(
    inning: int,
    is_bottom: bool,
    outs: int,
    base_state_index: int,
    score_diff: int,
) -> float:
    """
    Calcula el Leverage Index (LI) del estado actual.
    Un LI de 1.0 es el promedio de la liga.
    LI > 1.5 indica situación de alta tensión (Clutch).
    LI < 0.7 indica baja tensión (Blowout / Garbagetime).
    """
    we_curr = calculate_win_expectancy(inning, is_bottom, outs, base_state_index, score_diff)
    # Simular un hit (avance de base y carreras) vs un out
    we_out = calculate_win_expectancy(inning, is_bottom, min(outs + 1, 2), max(base_state_index - 1, 0), score_diff)
    we_hit = calculate_win_expectancy(inning, is_bottom, outs, min(base_state_index + 1, 7), score_diff + (1 if is_bottom else -1))

    swing = abs(we_hit - we_out)
    # Swing promedio en el juego ~ 0.09
    li = swing / 0.09
    return round(min(max(li, 0.05), 5.0), 2)


def compute_play_wpa(
    inning: int,
    is_bottom: bool,
    outs_before: int,
    base_state_before: int,
    score_diff_before: int,
    outs_after: int,
    base_state_after: int,
    score_diff_after: int,
    game_ended: bool = False,
) -> Dict[str, Any]:
    """
    Calcula el WPA para una jugada individual.
    Retorna delta para Home, Batter y Pitcher.
    """
    we_before = calculate_win_expectancy(
        inning, is_bottom, outs_before, base_state_before, score_diff_before
    )

    if game_ended:
        we_after = 1.0 if score_diff_after > 0 else 0.0
    else:
        we_after = calculate_win_expectancy(
            inning if outs_after < 3 else inning + (1 if is_bottom else 0),
            not is_bottom if outs_after >= 3 else is_bottom,
            0 if outs_after >= 3 else outs_after,
            0 if outs_after >= 3 else base_state_after,
            score_diff_after,
        )

    delta_home = we_after - we_before
    delta_batting_team = delta_home if is_bottom else -delta_home

    li = calculate_leverage_index(
        inning, is_bottom, outs_before, base_state_before, score_diff_before
    )

    return {
        "we_before": round(we_before, 4),
        "we_after": round(we_after, 4),
        "delta_home": round(delta_home, 4),
        "wpa_batter": round(delta_batting_team, 4),
        "wpa_pitcher": round(-delta_batting_team, 4),
        "leverage_index": li,
    }
