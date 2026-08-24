"""Analítica de Bullpen y Relevistas (IR, IRS, IRS%, Palanca de Entrada) para LIDOM."""

from typing import Dict, Any, List, Optional
import pandas as pd


def compute_reliever_metrics(pitcher_logs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calcula métricas avanzadas de un relevista:
    - G: Juegos relevados
    - IP: Entradas lanzadas
    - IR: Corredores heredados (Inherited Runners)
    - IRS: Corredores heredados que anotaron (Inherited Runners Scored)
    - IRS_pct: % de corredores heredados anotados
    - gmLI: Leverage Index promedio al momento de entrar
    - WPA: Win Probability Added total
    - ERA / WHIP
    """
    if not pitcher_logs:
        return {
            "G": 0, "IP": 0.0, "IR": 0, "IRS": 0, "IRS_pct": "0.0%",
            "gmLI": 1.00, "WPA": 0.00, "ERA": "0.00", "WHIP": "0.00", "SO": 0, "BB": 0,
        }

    df = pd.DataFrame(pitcher_logs)
    g = len(df)
    ip_total = df["ip"].sum() if "ip" in df else 0.0
    ir_total = int(df["inherited_runners"].sum()) if "inherited_runners" in df else 0
    irs_total = int(df["inherited_runners_scored"].sum()) if "inherited_runners_scored" in df else 0

    irs_pct = (irs_total / ir_total * 100) if ir_total > 0 else 0.0
    gmli_avg = df["entry_leverage"].mean() if "entry_leverage" in df else 1.00
    wpa_sum = df["wpa"].sum() if "wpa" in df else 0.0
    er_sum = df["er"].sum() if "er" in df else 0
    hits_sum = df["h"].sum() if "h" in df else 0
    bb_sum = df["bb"].sum() if "bb" in df else 0
    so_sum = df["so"].sum() if "so" in df else 0

    era = (er_sum * 9.0 / ip_total) if ip_total > 0 else 0.0
    whip = ((hits_sum + bb_sum) / ip_total) if ip_total > 0 else 0.0

    return {
        "G": g,
        "IP": round(ip_total, 1),
        "IR": ir_total,
        "IRS": irs_total,
        "IRS_pct": f"{irs_pct:.1f}%",
        "gmLI": round(gmli_avg, 2),
        "WPA": round(wpa_sum, 3),
        "ERA": f"{era:.2f}",
        "WHIP": f"{whip:.2f}",
        "SO": so_sum,
        "BB": bb_sum,
    }


def aggregate_team_bullpen(all_pitchers: List[Dict[str, Any]]) -> pd.DataFrame:
    """Agrega y rankea a todos los relevistas de un equipo."""
    rows = []
    for p in all_pitchers:
        metrics = compute_reliever_metrics(p.get("logs", []))
        rows.append({
            "Pitcher": p.get("name", "Unknown"),
            "Role": p.get("role", "RP"),
            "G": metrics["G"],
            "IP": metrics["IP"],
            "ERA": metrics["ERA"],
            "WHIP": metrics["WHIP"],
            "IR": metrics["IR"],
            "IRS": metrics["IRS"],
            "IRS%": metrics["IRS_pct"],
            "gmLI": metrics["gmLI"],
            "WPA": metrics["WPA"],
            "SO": metrics["SO"],
            "BB": metrics["BB"],
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(by=["WPA", "IP"], ascending=[False, False])
    return df
