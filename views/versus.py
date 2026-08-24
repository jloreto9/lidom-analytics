import io
import os
import urllib.request
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from typing import Dict, Any, List, Tuple
from PIL import Image, ImageDraw, ImageFont

from core.data_loader import LIDOMDataLoader
from core.teams import get_all_teams, get_team_by_id, get_team_by_abbrev
from utils.styles import render_header, render_team_badge


# ── Constantes y Configuración de Métricas Sabermétricas ───────────────────────

RADAR_METRICS_BAT = [
    {"col": "wOBA",  "p_col": "P_wOBA",  "label": "wOBA",   "higher_is_better": True},
    {"col": "wRC+",  "p_col": "P_wRC+",  "label": "wRC+",   "higher_is_better": True},
    {"col": "Hard%", "p_col": "P_Hard%", "label": "Hard%",  "higher_is_better": True},
    {"col": "OBP",   "p_col": "P_OBP",   "label": "OBP",    "higher_is_better": True},
    {"col": "SLG",   "p_col": "P_SLG",   "label": "SLG",    "higher_is_better": True},
    {"col": "ISO",   "p_col": "P_ISO",   "label": "ISO",    "higher_is_better": True},
    {"col": "WPA",   "p_col": "P_WPA",   "label": "WPA",    "higher_is_better": True},
    {"col": "AVG",   "p_col": "P_AVG",   "label": "AVG",    "higher_is_better": True},
]

RADAR_METRICS_PIT = [
    {"col": "ERA",   "p_col": "P_ERA",   "label": "ERA (Inv)",  "higher_is_better": False},
    {"col": "WHIP",  "p_col": "P_WHIP",  "label": "WHIP (Inv)", "higher_is_better": False},
    {"col": "FIP",   "p_col": "P_FIP",   "label": "FIP (Inv)",  "higher_is_better": False},
    {"col": "K/9",   "p_col": "P_K/9",   "label": "K/9",        "higher_is_better": True},
    {"col": "K%",    "p_col": "P_K%",    "label": "K%",         "higher_is_better": True},
    {"col": "WPA",   "p_col": "P_WPA",   "label": "WPA",        "higher_is_better": True},
    {"col": "IP",    "p_col": "P_IP",    "label": "IP",         "higher_is_better": True},
]


def build_polar_radar(p1: pd.Series, p2: pd.Series, metrics: List[Dict[str, Any]]) -> go.Figure:
    """Construye el gráfico de Radar Polar 360° en Dark Navy con alto contraste."""
    labels = [m["label"] for m in metrics]
    p1_vals = [int(p1[m["p_col"]]) for m in metrics]
    p2_vals = [int(p2[m["p_col"]]) for m in metrics]

    # Cerrar el polígono
    labels_closed = labels + [labels[0]]
    p1_vals_closed = p1_vals + [p1_vals[0]]
    p2_vals_closed = p2_vals + [p2_vals[0]]

    # Tooltips enriquecidos
    p1_hover = [f"{m['label']}: <b>{format_slash_val(p1[m['col']])}</b> (Pct: {p1[m['p_col']]})" for m in metrics] + [f"{metrics[0]['label']}: <b>{format_slash_val(p1[metrics[0]['col']])}</b>"]
    p2_hover = [f"{m['label']}: <b>{format_slash_val(p2[m['col']])}</b> (Pct: {p2[m['p_col']]})" for m in metrics] + [f"{metrics[0]['label']}: <b>{format_slash_val(p2[metrics[0]['col']])}</b>"]

    name1 = p1["Name"]
    team1 = p1["Team"]
    name2 = p2["Name"]
    team2 = p2["Team"]

    fig = go.Figure()

    # Traza Jugador 1 (Coral Red)
    fig.add_trace(go.Scatterpolar(
        r=p1_vals_closed,
        theta=labels_closed,
        fill="toself",
        name=f"🔴 {name1} ({team1})",
        line=dict(color="#FF3B56", width=2.5),
        fillcolor="rgba(255, 59, 86, 0.22)",
        marker=dict(size=6, color="#FF3B56"),
        hoverinfo="text",
        text=p1_hover,
    ))

    # Traza Jugador 2 (Electric Sky Blue)
    fig.add_trace(go.Scatterpolar(
        r=p2_vals_closed,
        theta=labels_closed,
        fill="toself",
        name=f"🔵 {name2} ({team2})",
        line=dict(color="#38BDF8", width=2.5),
        fillcolor="rgba(56, 189, 248, 0.22)",
        marker=dict(size=6, color="#38BDF8"),
        hoverinfo="text",
        text=p2_hover,
    ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                tickvals=[20, 40, 60, 80, 100],
                ticktext=["20", "40", "60", "80", "100"],
                tickfont=dict(color="#94A3B8", size=10),
                gridcolor="rgba(255, 255, 255, 0.08)",
                linecolor="rgba(255, 255, 255, 0.1)",
            ),
            angularaxis=dict(
                tickfont=dict(size=12, color="#FFFFFF", family="Outfit, sans-serif"),
                gridcolor="rgba(255, 255, 255, 0.08)",
                linecolor="rgba(255, 255, 255, 0.1)",
            ),
            bgcolor="#070C1A",
        ),
        paper_bgcolor="#0D152B",
        plot_bgcolor="#070C1A",
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.06,
            xanchor="center",
            x=0.5,
            font=dict(color="#FFFFFF", size=13, family="Inter, sans-serif"),
            bgcolor="rgba(7, 12, 26, 0.8)",
            bordercolor="rgba(255, 255, 255, 0.1)",
            borderwidth=1,
        ),
        margin=dict(l=40, r=40, t=50, b=30),
        height=450,
    )
    return fig


def format_slash_val(val: Any) -> str:
    """Asegura formato sabermétrico sin el 0 inicial para AVG, OBP, SLG, OPS, wOBA, ISO (ej. .315)."""
    if val is None or pd.isna(val):
        return "—"
    try:
        s = str(val).strip()
        f = float(s.replace("%", ""))
        if 0.0 <= f < 1.0:
            return f"{f:.3f}".lstrip("0")
        elif f >= 1.0:
            return f"{f:.3f}" if ("." in s or isinstance(val, float)) else s
        return s
    except Exception:
        return str(val)


def determine_winner(val1: Any, val2: Any, higher_is_better: bool, name1: str, team1: str, name2: str, team2: str) -> str:
    """Calcula el ganador para una fila de la tabla comparativa."""
    try:
        s1 = str(val1).replace("%", "").strip()
        s2 = str(val2).replace("%", "").strip()
        f1 = float(s1)
        f2 = float(s2)
        if abs(f1 - f2) < 1e-4:
            return "⚖️ Igual"
        if higher_is_better:
            return f"🔴 {name1} ({team1})" if f1 > f2 else f"🔵 {name2} ({team2})"
        else:
            return f"🔴 {name1} ({team1})" if f1 < f2 else f"🔵 {name2} ({team2})"
    except Exception:
        return "—"


def build_h2h_table(p1: pd.Series, p2: pd.Series, is_batter: bool) -> pd.DataFrame:
    """Genera la tabla comparativa detallada 360° con métricas categorizadas."""
    name1 = p1["Name"]
    team1 = p1["Team"]
    name2 = p2["Name"]
    team2 = p2["Team"]

    rows = []

    if is_batter:
        # Métricas Sabermétricas
        saber_stats = [
            ("wOBA", "wOBA (Weighted On-Base)", True),
            ("wRC+", "wRC+ (Runs Created Plus)", True),
            ("WPA", "WPA (Win Probability Added)", True),
            ("Hard%", "Hard Contact % (BIS)", True),
            ("ISO", "ISO (Isolated Power)", True),
            ("BB%", "BB% (Boleto %)", True),
            ("K%", "K% (Ponche %)", False),
        ]
        for key, lbl, hib in saber_stats:
            v1, v2 = p1[key], p2[key]
            w = determine_winner(v1, v2, hib, name1, team1, name2, team2)
            v1_str = format_slash_val(v1) if key in ["wOBA", "ISO"] else str(v1)
            v2_str = format_slash_val(v2) if key in ["wOBA", "ISO"] else str(v2)
            rows.append({"Categoría": "⚡ Sabermetría & Valor", "Métrica": lbl, f"{name1} ({team1})": v1_str, f"{name2} ({team2})": v2_str, "Ventaja / Ganador": w})

        # Métricas Tradicionales de Rate
        rate_stats = [
            ("AVG", "AVG (Promedio)", True),
            ("OBP", "OBP (Embasado)", True),
            ("SLG", "SLG (Slugging)", True),
            ("OPS", "OPS (OBP + SLG)", True),
        ]
        for key, lbl, hib in rate_stats:
            v1, v2 = p1[key], p2[key]
            w = determine_winner(v1, v2, hib, name1, team1, name2, team2)
            rows.append({"Categoría": "📊 Estadísticas de Rate", "Métrica": lbl, f"{name1} ({team1})": format_slash_val(v1), f"{name2} ({team2})": format_slash_val(v2), "Ventaja / Ganador": w})

        # Estadísticas de Conteo
        count_stats = [
            ("G", "Juegos (G)", True),
            ("AB", "Turnos al Bate (AB)", True),
            ("H", "Hits (H)", True),
            ("2B", "Dobles (2B)", True),
            ("3B", "Triples (3B)", True),
            ("HR", "Jonrones (HR)", True),
            ("RBI", "Carreras Impulsadas (RBI)", True),
            ("R", "Carreras Anotadas (R)", True),
            ("BB", "Bases por Bolas (BB)", True),
            ("SO", "Ponches (SO)", False),
            ("SB", "Bases Robadas (SB)", True),
        ]
        for key, lbl, hib in count_stats:
            v1, v2 = p1[key], p2[key]
            w = determine_winner(v1, v2, hib, name1, team1, name2, team2)
            rows.append({"Categoría": "🔢 Estadísticas de Volumen", "Métrica": lbl, f"{name1} ({team1})": str(v1), f"{name2} ({team2})": str(v2), "Ventaja / Ganador": w})

    else:
        # Métricas de Pitcheo
        saber_stats = [
            ("FIP", "FIP (Fielding Indep. Pitching)", False),
            ("WHIP", "WHIP (Walks+Hits/IP)", False),
            ("K/9", "K/9 (Ponches por 9 IP)", True),
            ("BB/9", "BB/9 (Boletos por 9 IP)", False),
            ("K%", "K% (Tasa de Ponche)", True),
            ("WPA", "WPA (Win Probability Added)", True),
        ]
        for key, lbl, hib in saber_stats:
            v1, v2 = p1[key], p2[key]
            w = determine_winner(v1, v2, hib, name1, team1, name2, team2)
            rows.append({"Categoría": "⚡ Sabermetría & Dominio", "Métrica": lbl, f"{name1} ({team1})": str(v1), f"{name2} ({team2})": str(v2), "Ventaja / Ganador": w})

        rate_stats = [
            ("ERA", "ERA (Efectividad)", False),
        ]
        for key, lbl, hib in rate_stats:
            v1, v2 = p1[key], p2[key]
            w = determine_winner(v1, v2, hib, name1, team1, name2, team2)
            rows.append({"Categoría": "📊 Estadísticas de Rate", "Métrica": lbl, f"{name1} ({team1})": str(v1), f"{name2} ({team2})": str(v2), "Ventaja / Ganador": w})

        count_stats = [
            ("G", "Juegos Lanzados (G)", True),
            ("GS", "Juegos Iniciados (GS)", True),
            ("IP", "Entradas Lanzadas (IP)", True),
            ("SO", "Ponches (SO)", True),
            ("W", "Victorias (W)", True),
            ("L", "Derrotas (L)", False),
            ("SV", "Juegos Salvados (SV)", True),
            ("H", "Hits Permitidos (H)", False),
            ("ER", "Carreras Limpias (ER)", False),
        ]
        for key, lbl, hib in count_stats:
            v1, v2 = p1[key], p2[key]
            w = determine_winner(v1, v2, hib, name1, team1, name2, team2)
            rows.append({"Categoría": "🔢 Estadísticas de Volumen", "Métrica": lbl, f"{name1} ({team1})": str(v1), f"{name2} ({team2})": str(v2), "Ventaja / Ganador": w})

    return pd.DataFrame(rows)


# ── Renderizado de Tarjeta Gráfica Matchup (PNG) ───────────────────────────────

def _fetch_circular_image(url: str, size: Tuple[int, int] = (64, 64), border_color: Tuple[int, int, int] = (255, 59, 86)) -> Image.Image | None:
    """Descarga y recorta en formato circular el headshot oficial del jugador con borde coloreado."""
    if not url:
        return None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            data = resp.read()
        raw_img = Image.open(io.BytesIO(data)).convert("RGBA")
        raw_img = raw_img.resize(size, Image.Resampling.LANCZOS)

        mask = Image.new("L", size, 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0) + size, fill=255)

        circ = Image.new("RGBA", size, (0, 0, 0, 0))
        circ.paste(raw_img, (0, 0), mask=mask)

        # Dibujar borde decorativo
        border_draw = ImageDraw.Draw(circ)
        border_draw.ellipse((0, 0, size[0] - 1, size[1] - 1), outline=border_color + (255,), width=3)
        return circ
    except Exception:
        return None


def _fetch_team_logo(url: str, size: Tuple[int, int] = (26, 26)) -> Image.Image | None:
    """Descarga y redimensiona el logo oficial de la franquicia."""
    if not url:
        return None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            data = resp.read()
        raw_img = Image.open(io.BytesIO(data)).convert("RGBA")
        return raw_img.resize(size, Image.Resampling.LANCZOS)
    except Exception:
        return None


def _load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    """Carga fuentes multiplataforma con fallback seguro."""
    suffix = "-Bold" if bold else ""
    paths = [
        f"/usr/share/fonts/truetype/dejavu/DejaVuSans{suffix}.ttf",
        f"/usr/share/fonts/truetype/liberation/LiberationSans{'-Bold' if bold else '-Regular'}.ttf",
        f"C:/Windows/Fonts/{'arialbd' if bold else 'arial'}.ttf",
        f"C:/Windows/Fonts/{'segoeuib' if bold else 'segoeui'}.ttf",
    ]
    for p in paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def build_matchup_image(p1: pd.Series, p2: pd.Series, is_batter: bool, df_h2h: pd.DataFrame, season: int) -> bytes:
    """Genera una tarjeta PNG descargable de alta definición con diseño Dark Navy Glass."""
    name1, team1 = p1["Name"], p1["Team"]
    name2, team2 = p2["Name"], p2["Team"]

    COL1, COL2, COL3 = 230, 180, 230
    W = COL1 + COL2 + COL3
    ROW_H, HDR_H, FOOT_H = 28, 100, 76

    # Filtrar solo métricas clave para la tarjeta gráfica (max 18 filas)
    df_rows = df_h2h[df_h2h["Categoría"].isin(["⚡ Sabermetría & Valor", "⚡ Sabermetría & Dominio", "📊 Estadísticas de Rate", "🔢 Estadísticas de Volumen"])].copy()
    if len(df_rows) > 18:
        df_rows = df_rows.iloc[:18]

    n = len(df_rows)
    H = HDR_H + n * ROW_H + FOOT_H

    BG_DARK   = (7, 11, 25)
    CARD_BG   = (13, 21, 43)
    ALT_BG    = (10, 16, 34)
    BORDER_C  = (30, 41, 69)
    RED_CLR   = (255, 59, 86)
    BLUE_CLR  = (56, 189, 248)
    WHITE     = (255, 255, 255)
    GRAY_TEXT = (148, 163, 184)
    GOLD_CLR  = (241, 225, 62)

    fb = _load_font(12, bold=True)
    fn = _load_font(11)
    fs = _load_font(9)
    f_large = _load_font(14, bold=True)
    f_title = _load_font(13, bold=True)

    img = Image.new("RGBA", (W, H), BG_DARK + (255,))
    draw = ImageDraw.Draw(img)

    def _tc(cx, cy, text, font, color):
        try:
            bb = draw.textbbox((0, 0), str(text), font=font)
            tw, th = bb[2] - bb[0], bb[3] - bb[1]
        except AttributeError:
            tw, th = draw.textsize(str(text), font=font)
        draw.text((cx - tw // 2, cy - th // 2), str(text), font=font, fill=color)

    # 1. Header Cards
    # Header Left (Player 1)
    draw.rectangle([0, 0, COL1 - 1, HDR_H - 1], fill=(26, 15, 30))
    draw.rectangle([0, 0, 4, HDR_H - 1], fill=RED_CLR)

    # Header Center (VS Badge)
    draw.rectangle([COL1, 0, COL1 + COL2 - 1, HDR_H - 1], fill=(13, 21, 43))

    # Header Right (Player 2)
    draw.rectangle([COL1 + COL2, 0, W - 1, HDR_H - 1], fill=(10, 25, 45))
    draw.rectangle([W - 5, 0, W - 1, HDR_H - 1], fill=BLUE_CLR)

    # Pegar Headshots y Logos
    hs1 = _fetch_circular_image(p1.get("Headshot"), size=(64, 64), border_color=RED_CLR)
    if hs1:
        img.paste(hs1, (14, (HDR_H - 64) // 2), mask=hs1)
        _tc(COL1 // 2 + 25, 32, name1, f_title, WHITE)
        _tc(COL1 // 2 + 25, 52, f"{p1.get('Team_Name', team1)} · {p1.get('Pos', 'P')} #{p1.get('Jersey', '')}", fs, (255, 180, 190))
    else:
        _tc(COL1 // 2, 32, name1, f_title, WHITE)
        _tc(COL1 // 2, 52, f"{p1.get('Team_Name', team1)} · {p1.get('Pos', 'P')} #{p1.get('Jersey', '')}", fs, (255, 180, 190))

    tlogo1 = _fetch_team_logo(p1.get("Team_Logo"), size=(24, 24))
    if tlogo1:
        img.paste(tlogo1, (COL1 - 32, 10), mask=tlogo1)

    # Center VS & Season
    _tc(COL1 + COL2 // 2, 32, "LIDOM 360", f_large, GOLD_CLR)
    _tc(COL1 + COL2 // 2, 52, "MATCHUP VERSUS", fs, GRAY_TEXT)
    _tc(COL1 + COL2 // 2, 70, f"Temporada {season}-{season+1}", fs, (180, 200, 220))

    hs2 = _fetch_circular_image(p2.get("Headshot"), size=(64, 64), border_color=BLUE_CLR)
    if hs2:
        img.paste(hs2, (COL1 + COL2 + 14, (HDR_H - 64) // 2), mask=hs2)
        _tc(COL1 + COL2 + COL3 // 2 + 25, 32, name2, f_title, WHITE)
        _tc(COL1 + COL2 + COL3 // 2 + 25, 52, f"{p2.get('Team_Name', team2)} · {p2.get('Pos', 'P')} #{p2.get('Jersey', '')}", fs, (180, 220, 255))
    else:
        _tc(COL1 + COL2 + COL3 // 2, 32, name2, f_title, WHITE)
        _tc(COL1 + COL2 + COL3 // 2, 52, f"{p2.get('Team_Name', team2)} · {p2.get('Pos', 'P')} #{p2.get('Jersey', '')}", fs, (180, 220, 255))

    tlogo2 = _fetch_team_logo(p2.get("Team_Logo"), size=(24, 24))
    if tlogo2:
        img.paste(tlogo2, (W - 32, 10), mask=tlogo2)

    # Header Divider Line
    draw.line([(0, HDR_H), (W, HDR_H)], fill=BORDER_C, width=1)

    # 2. Filas de Comparación
    p1_col_name = f"{name1} ({team1})"
    p2_col_name = f"{name2} ({team2})"

    y = HDR_H
    for idx, (_, row) in enumerate(df_rows.iterrows()):
        row_bg = CARD_BG if idx % 2 == 0 else ALT_BG
        draw.rectangle([0, y, W - 1, y + ROW_H - 1], fill=row_bg)

        stat_label = str(row["Métrica"]).split("(")[0].strip()
        v1_str = str(row.get(p1_col_name, "—"))
        v2_str = str(row.get(p2_col_name, "—"))
        if stat_label in ["AVG", "OBP", "SLG", "OPS", "wOBA", "ISO"]:
            v1_str = format_slash_val(v1_str)
            v2_str = format_slash_val(v2_str)
        winner_str = str(row.get("Ventaja / Ganador", ""))

        is_p1_win = f"🔴 {name1}" in winner_str or f"({team1})" in winner_str
        is_p2_win = f"🔵 {name2}" in winner_str or f"({team2})" in winner_str

        # Color de los números
        c1 = RED_CLR if is_p1_win else WHITE
        c2 = BLUE_CLR if is_p2_win else WHITE
        f1 = fb if is_p1_win else fn
        f2 = fb if is_p2_win else fn

        # Dibujar valores
        _tc(COL1 // 2, y + ROW_H // 2, v1_str, f1, c1)
        _tc(COL1 + COL2 // 2, y + ROW_H // 2, stat_label, fb, (220, 225, 235))
        _tc(COL1 + COL2 + COL3 // 2, y + ROW_H // 2, v2_str, f2, c2)

        # Línea divisoria sutil
        draw.line([(0, y + ROW_H), (W, y + ROW_H)], fill=BORDER_C, width=1)
        y += ROW_H

    # 3. Footer Branding & Fuentes de Datos
    draw.rectangle([0, y, W - 1, H - 1], fill=(7, 11, 25))
    draw.line([(0, y), (W, y)], fill=BORDER_C, width=1)
    _tc(W // 2, y + 16, "LIDOM 360 — Plataforma Sabermétrica & Analítica Integral", fb, GOLD_CLR)
    _tc(W // 2, y + 36, "Fuentes: MLB Stats API (ID 131) · Tom Tango (RE24 / WPA) · Baseball Info Solutions (BIS)", fs, (148, 163, 184))
    _tc(W // 2, y + 56, "Desarrollado por Jorge Leonardo Loreto · AI Data Scientist & Baseball Sabermetrician", fs, (100, 116, 139))

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def render_versus_view(season: int = 2024) -> None:
    """Renderiza el módulo Matchup 360 (Comparador Cara a Cara de Jugadores de LIDOM)."""
    render_header(
        title="Matchup 360 — Comparador Head-to-Head",
        subtitle="Analítica avanzada, Radar Polar multidimensional y tabla sabermétrica comparativa entre peloteros de LIDOM",
        badge_text="VERSUS 360",
        season=season,
    )

    loader = LIDOMDataLoader()

    # 1. Filtro de Rol
    col_role, col_info = st.columns([1, 2])
    with col_role:
        role = st.radio(
            "Selecciona Categoría de Comparación:",
            ["🏏 Bateadores (Hitters)", "🎯 Lanzadores (Pitchers)"],
            horizontal=True,
        )
    with col_info:
        st.markdown("""
        <div style="background: rgba(13, 21, 43, 0.6); border: 1px solid rgba(255,255,255,0.06); border-radius: 10px; padding: 10px 16px; font-size: 0.85rem; color: #94A3B8;">
            💡 <b>Matchup Sabermétrico:</b> Selecciona dos jugadores de cualquier equipo de LIDOM para contrastar su percentil relativo, perfil ofensivo/pitcheo y valor de impacto ($WPA$).
        </div>
        """, unsafe_allow_html=True)

    is_batter = "Bateadores" in role
    pool_role = "Bateadores" if is_batter else "Lanzadores"
    df_players = loader.get_versus_player_pool(season=season, role=pool_role)

    if df_players.empty:
        st.warning(f"No hay registros disponibles para {role} en la temporada seleccionada.")
        return

    player_names = df_players["Name"].tolist()

    # Defaults representativos
    default_p1 = "Emilio Bonifacio" if (is_batter and "Emilio Bonifacio" in player_names) else player_names[0]
    default_p2 = "Junior Lake" if (is_batter and "Junior Lake" in player_names and len(player_names) > 1) else (player_names[1] if len(player_names) > 1 else player_names[0])
    if not is_batter:
        default_p1 = "César Valdez" if "César Valdez" in player_names else player_names[0]
        default_p2 = "Enny Romero" if ("Enny Romero" in player_names and len(player_names) > 1) else (player_names[1] if len(player_names) > 1 else player_names[0])

    idx_p1 = player_names.index(default_p1) if default_p1 in player_names else 0
    idx_p2 = player_names.index(default_p2) if default_p2 in player_names else (1 if len(player_names) > 1 else 0)

    # 2. Selectores de Jugadores
    col_sel1, col_sel2 = st.columns(2)
    with col_sel1:
        st.markdown("#### 🔴 Pelotero A")
        selected_name1 = st.selectbox("Buscar Jugador A:", player_names, index=idx_p1, key="sel_player_1")
    with col_sel2:
        st.markdown("#### 🔵 Pelotero B")
        selected_name2 = st.selectbox("Buscar Jugador B:", player_names, index=idx_p2, key="sel_player_2")

    p1 = df_players[df_players["Name"] == selected_name1].iloc[0]
    p2 = df_players[df_players["Name"] == selected_name2].iloc[0]

    # 3. Hero Matchup Banner (Headshots y Perfiles)
    st.markdown("---")
    col_card1, col_vs, col_card2 = st.columns([5, 2, 5])

    with col_card1:
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, rgba(255, 59, 86, 0.15) 0%, rgba(13, 21, 43, 0.8) 100%); border: 2px solid #FF3B56; border-radius: 14px; padding: 18px; display: flex; align-items: center; gap: 18px; box-shadow: 0 4px 20px rgba(0,0,0,0.4);">
            <img src="{p1['Headshot']}" style="width: 85px; height: 85px; border-radius: 50%; object-fit: cover; border: 2px solid #FF3B56; background: #070B19;">
            <div>
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                    <img src="{p1['Team_Logo']}" style="width: 20px; height: 20px; object-fit: contain;">
                    <span style="font-size: 0.8rem; font-weight: 700; color: #FF3B56; text-transform: uppercase;">{p1['Team_Name']}</span>
                    <span style="background: rgba(255,255,255,0.08); padding: 2px 8px; border-radius: 6px; font-size: 0.75rem; font-weight: 700;">{p1['Pos']} #{p1['Jersey']}</span>
                </div>
                <h2 style="margin: 0; font-size: 1.5rem; color: #FFFFFF;">{p1['Name']}</h2>
                <div style="margin-top: 6px; color: #CBD5E1; font-size: 0.85rem;">
                    {"<b>wOBA:</b> " + format_slash_val(p1['wOBA']) + " &nbsp;|&nbsp; <b>wRC+:</b> " + str(p1['wRC+']) + " &nbsp;|&nbsp; <b>WPA:</b> " + str(p1['WPA']) if is_batter else "<b>ERA:</b> " + str(p1['ERA']) + " &nbsp;|&nbsp; <b>WHIP:</b> " + str(p1['WHIP']) + " &nbsp;|&nbsp; <b>WPA:</b> " + str(p1['WPA'])}
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col_vs:
        st.markdown("""
        <div style="text-align: center; padding-top: 25px;">
            <span style="font-family: 'Outfit', sans-serif; font-size: 2.2rem; font-weight: 900; background: linear-gradient(135deg, #FF3B56 0%, #38BDF8 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">VS</span>
            <div style="font-size: 0.75rem; color: #64748B; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em;">MATCHUP 360</div>
        </div>
        """, unsafe_allow_html=True)

    with col_card2:
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, rgba(56, 189, 248, 0.15) 0%, rgba(13, 21, 43, 0.8) 100%); border: 2px solid #38BDF8; border-radius: 14px; padding: 18px; display: flex; align-items: center; gap: 18px; box-shadow: 0 4px 20px rgba(0,0,0,0.4);">
            <img src="{p2['Headshot']}" style="width: 85px; height: 85px; border-radius: 50%; object-fit: cover; border: 2px solid #38BDF8; background: #070B19;">
            <div>
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                    <img src="{p2['Team_Logo']}" style="width: 20px; height: 20px; object-fit: contain;">
                    <span style="font-size: 0.8rem; font-weight: 700; color: #38BDF8; text-transform: uppercase;">{p2['Team_Name']}</span>
                    <span style="background: rgba(255,255,255,0.08); padding: 2px 8px; border-radius: 6px; font-size: 0.75rem; font-weight: 700;">{p2['Pos']} #{p2['Jersey']}</span>
                </div>
                <h2 style="margin: 0; font-size: 1.5rem; color: #FFFFFF;">{p2['Name']}</h2>
                <div style="margin-top: 6px; color: #CBD5E1; font-size: 0.85rem;">
                    {"<b>wOBA:</b> " + format_slash_val(p2['wOBA']) + " &nbsp;|&nbsp; <b>wRC+:</b> " + str(p2['wRC+']) + " &nbsp;|&nbsp; <b>WPA:</b> " + str(p2['WPA']) if is_batter else "<b>ERA:</b> " + str(p2['ERA']) + " &nbsp;|&nbsp; <b>WHIP:</b> " + str(p2['WHIP']) + " &nbsp;|&nbsp; <b>WPA:</b> " + str(p2['WPA'])}
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # 4. Sección Visual: Radar Polar 360° + KPIs Comparativos
    col_radar, col_metrics = st.columns([7, 5])

    radar_metrics = RADAR_METRICS_BAT if is_batter else RADAR_METRICS_PIT

    with col_radar:
        st.markdown("### 🕸️ Perfil Multidimensional (Radar Polar 360°)")
        st.caption("Percentiles relativos normalizados de 0 a 100 frente a todos los jugadores de la liga.")
        fig_radar = build_polar_radar(p1, p2, radar_metrics)
        st.plotly_chart(fig_radar, use_container_width=True)

    with col_metrics:
        st.markdown("### ⚡ Diferenciales de Impacto")
        st.caption("Métricas determinantes de producción y valor sabermétrico:")

        if is_batter:
            diff_woba = round(float(p1["wOBA"]) - float(p2["wOBA"]), 3)
            diff_wrc = int(p1["wRC+"]) - int(p2["wRC+"])
            diff_wpa = round(float(p1["WPA"]) - float(p2["WPA"]), 2)

            st.metric(
                label=f"Diferencial wOBA ({p1['Name']} vs {p2['Name']})",
                value=f"{format_slash_val(p1['wOBA'])} vs {format_slash_val(p2['wOBA'])}",
                delta=f"{diff_woba:+.3f}".lstrip("0") if 0 < abs(diff_woba) < 1.0 else f"{diff_woba:+.3f}",
            )
            st.metric(
                label=f"Diferencial wRC+ (Aporte Ofensivo %)",
                value=f"{p1['wRC+']} vs {p2['wRC+']}",
                delta=f"{diff_wrc:+d} pts",
            )
            st.metric(
                label=f"Diferencial WPA (Victorias Aportadas)",
                value=f"{p1['WPA']} vs {p2['WPA']}",
                delta=f"{diff_wpa:+.2f} WPA",
            )
        else:
            diff_era = round(float(p1["ERA"]) - float(p2["ERA"]), 2)
            diff_fip = round(float(p1["FIP"]) - float(p2["FIP"]), 2)
            diff_wpa = round(float(p1["WPA"]) - float(p2["WPA"]), 2)

            st.metric(
                label=f"Diferencial ERA ({p1['Name']} vs {p2['Name']})",
                value=f"{p1['ERA']} vs {p2['ERA']}",
                delta=f"{-diff_era:+.2f} ERA (Menor es mejor)",
            )
            st.metric(
                label=f"Diferencial FIP (Pitcheo Independiente)",
                value=f"{p1['FIP']} vs {p2['FIP']}",
                delta=f"{-diff_fip:+.2f} FIP",
            )
            st.metric(
                label=f"Diferencial WPA (Victorias Protegidas)",
                value=f"{p1['WPA']} vs {p2['WPA']}",
                delta=f"{diff_wpa:+.2f} WPA",
            )

    # 5. Tabla Comparativa Completa 360°
    st.markdown("---")
    st.markdown("### 📋 Desglose Comparativo Head-to-Head 360°")
    df_h2h = build_h2h_table(p1, p2, is_batter=is_batter)

    tab_all, tab_saber, tab_rate, tab_count = st.tabs([
        "🔍 Todo el Registro",
        "⚡ Sabermetría & Valor",
        "📊 Estadísticas de Rate",
        "🔢 Volumen & Conteo"
    ])

    with tab_all:
        st.dataframe(df_h2h, use_container_width=True, hide_index=True)
    with tab_saber:
        st.dataframe(df_h2h[df_h2h["Categoría"].str.contains("Sabermetría")], use_container_width=True, hide_index=True)
    with tab_rate:
        st.dataframe(df_h2h[df_h2h["Categoría"].str.contains("Rate")], use_container_width=True, hide_index=True)
    with tab_count:
        st.dataframe(df_h2h[df_h2h["Categoría"].str.contains("Volumen")], use_container_width=True, hide_index=True)

    # 6. Veredicto Sabermétrico Final
    st.markdown("---")
    st.markdown("### ⚖️ Veredicto Sabermétrico")
    
    if is_batter:
        wrc1, wrc2 = int(p1["wRC+"]), int(p2["wRC+"])
        wpa1, wpa2 = float(p1["WPA"]), float(p2["WPA"])
        hard1, hard2 = float(p1["Hard%"]), float(p2["Hard%"])

        if wrc1 > wrc2 and wpa1 > wpa2:
            verdict_leader = f"🔴 **{p1['Name']} ({p1['Team']})** lidera el matchup de forma contundente, superando a su contraparte tanto en eficiencia ajustada al parque (**{wrc1} wRC+** vs {wrc2}) como en apalancamiento en victorias (**{wpa1:+.2f} WPA** vs {wpa2:+.2f})."
        elif wrc2 > wrc1 and wpa2 > wpa1:
            verdict_leader = f"🔵 **{p2['Name']} ({p2['Team']})** se impone en el duelo ofensivo, registrando mayor producción global ajustada (**{wrc2} wRC+** vs {wrc1}) y un superior impacto directo en triunfos (**{wpa2:+.2f} WPA** vs {wpa1:+.2f})."
        else:
            lead_name = p1['Name'] if wrc1 >= wrc2 else p2['Name']
            verdict_leader = f"⚔️ **Matchup altamente balanceado**: Mientras un bateador destaca en frecuencia y calidad de contacto (**{max(hard1, hard2)}% Hard Hit**), el otro aporta en momentos críticos de juego con apalancamiento situacional."

        st.markdown(f"""
        <div style="background: rgba(13, 21, 43, 0.85); border-left: 4px solid #38BDF8; border-radius: 12px; padding: 18px 22px; font-size: 0.95rem; color: #E2E8F0;">
            {verdict_leader}
        </div>
        """, unsafe_allow_html=True)
    else:
        fip1, fip2 = float(p1["FIP"]), float(p2["FIP"])
        wpa1, wpa2 = float(p1["WPA"]), float(p2["WPA"])
        k91, k92 = float(p1["K/9"]), float(p2["K/9"])

        if fip1 < fip2 and wpa1 > wpa2:
            verdict_pit = f"🔴 **{p1['Name']} ({p1['Team']})** muestra un dominio superior en la lomita con mejor FIP independiente de la defensa (**{fip1:.2f}** vs {fip2:.2f}) y mayor capacidad para preservar ventajas (**{wpa1:+.2f} WPA**)."
        elif fip2 < fip1 and wpa2 > wpa1:
            verdict_pit = f"🔵 **{p2['Name']} ({p2['Team']})** exhibe una ventaja marcada en pitcheo independiente (**{fip2:.2f} FIP** vs {fip1:.2f}) y un aporte de apalancamiento superior (**{wpa2:+.2f} WPA**)."
        else:
            verdict_pit = f"⚔️ **Duelo de pitcheo parejo**: Uno exhibe mayor tasa de ponches (**{max(k91, k92):.1f} K/9**), mientras que el otro mantiene a raya las carreras limpias y el tráfico en las almohadillas."

        st.markdown(f"""
        <div style="background: rgba(13, 21, 43, 0.85); border-left: 4px solid #38BDF8; border-radius: 12px; padding: 18px 22px; font-size: 0.95rem; color: #E2E8F0;">
            {verdict_pit}
        </div>
        """, unsafe_allow_html=True)

    # 7. Descarga de Tarjeta Matchup PNG
    st.markdown("---")
    st.markdown("### 📥 Exportar Tarjeta Gráfica Matchup 360 (PNG)")
    st.caption("Genera y descarga una tarjeta gráfica con fotos oficiales, escudos, métricas clave y diseño Dark Navy Glass lista para compartir:")

    with st.spinner("Generando tarjeta gráfica Matchup 360..."):
        card_png_bytes = build_matchup_image(p1, p2, is_batter=is_batter, df_h2h=df_h2h, season=season)

    col_btn, col_preview = st.columns([1, 1])
    with col_btn:
        safe_p1 = "".join(c for c in str(p1['Name']) if c.isalnum() or c in (' ', '_')).replace(' ', '_')
        safe_p2 = "".join(c for c in str(p2['Name']) if c.isalnum() or c in (' ', '_')).replace(' ', '_')
        st.download_button(
            label=f"📥 Descargar Tarjeta Matchup ({p1['Name']} vs {p2['Name']})",
            data=card_png_bytes,
            file_name=f"LIDOM360_Matchup_{safe_p1}_vs_{safe_p2}_{season}.png",
            mime="image/png",
            use_container_width=True,
        )
    with col_preview:
        with st.expander("🖼️ Vista Previa de la Tarjeta Gráfica"):
            st.image(card_png_bytes, use_container_width=True, caption=f"Tarjeta Matchup: {p1['Name']} vs {p2['Name']} · LIDOM {season}")
