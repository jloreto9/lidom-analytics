"""Calibración determinística de dureza de contacto (Batted Ball Hardness - BIS) para LIDOM."""

from typing import Dict, Any, Tuple, Optional


def classify_batted_ball_hardness(
    launch_speed: Optional[float] = None,
    trajectory: Optional[str] = None,
    event_type: Optional[str] = None,
    description: Optional[str] = None,
) -> Tuple[str, float]:
    """
    Clasifica la dureza del contacto en 'Hard' (Fuerte), 'Medium' (Media), 'Soft' (Suave)
    y retorna (categoria, velocidad_estimada_mph).
    """
    # 1. Si tenemos velocidad de salida medida (Statcast/Trackman)
    if launch_speed is not None and launch_speed > 0:
        if launch_speed >= 95.0:
            return "Hard", float(launch_speed)
        elif launch_speed >= 80.0:
            return "Medium", float(launch_speed)
        else:
            return "Soft", float(launch_speed)

    # 2. Si no hay velocidad medida, aplicar modelo determinístico sabermétrico BIS
    event_lower = (event_type or "").lower()
    desc_lower = (description or "").lower()
    traj_lower = (trajectory or "").lower()

    # Home runs y triples son casi exclusivamente Hard
    if "home_run" in event_lower or "jonrón" in desc_lower or "home run" in desc_lower:
        return "Hard", 102.5
    if "triple" in event_lower:
        return "Hard", 98.0
    if "double" in event_lower or "doble" in desc_lower:
        return "Hard", 96.0

    # Líneas y batazos profundos
    if "line_drive" in traj_lower or "linea" in desc_lower or "línea" in desc_lower:
        if "out" in event_lower or "force_out" in event_lower:
            return "Hard", 92.0
        return "Hard", 95.5

    # Elevados (Fly balls)
    if "fly_ball" in traj_lower or "elevado" in desc_lower or "fly" in desc_lower:
        if "single" in event_lower or "hit" in desc_lower:
            return "Medium", 86.0
        return "Medium", 84.0

    # Rodados (Ground balls)
    if "ground_ball" in traj_lower or "rodado" in desc_lower or "rolling" in desc_lower:
        if "single" in event_lower:
            return "Medium", 88.0
        if "double_play" in event_lower:
            return "Hard", 91.0
        return "Medium", 82.0

    # Popups / Infield fly / Toques
    if "popup" in traj_lower or "pop_up" in traj_lower or "infield_fly" in event_lower:
        return "Soft", 72.0
    if "bunt" in traj_lower or "toque" in desc_lower:
        return "Soft", 65.0

    # Default fallback
    if "single" in event_lower or "sencillo" in desc_lower:
        return "Medium", 87.0

    return "Medium", 83.0


def calculate_contact_profile(batted_balls: list) -> Dict[str, float]:
    """Calcula la distribución porcentual Hard%, Medium%, Soft% de una lista de jugadas."""
    if not batted_balls:
        return {"hard_pct": 0.0, "medium_pct": 0.0, "soft_pct": 0.0, "total": 0}

    counts = {"Hard": 0, "Medium": 0, "Soft": 0}
    for ball in batted_balls:
        h, _ = classify_batted_ball_hardness(
            launch_speed=ball.get("launch_speed"),
            trajectory=ball.get("trajectory"),
            event_type=ball.get("event"),
            description=ball.get("description"),
        )
        counts[h] = counts.get(h, 0) + 1

    total = len(batted_balls)
    return {
        "hard_pct": round((counts["Hard"] / total) * 100, 1),
        "medium_pct": round((counts["Medium"] / total) * 100, 1),
        "soft_pct": round((counts["Soft"] / total) * 100, 1),
        "total": total,
    }
