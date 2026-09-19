# core/pitching_card.py
"""
pitching_card.py
----------------
Generador de resúmenes gráficos de pitcheo (Pitching Summary) para LIDOM 360
utilizando el framework y diseño original de Thomas Nestico (@TJStats) en Matplotlib.

Características:
1. Cuadrícula 20x20 (GridSpec 6x8) en fondo blanco pulcro.
2. Cabecera: Headshot oficial del lanzador, Biografía completa y Logo oficial de LIDOM 360 / Franquicia.
3. Tabla Resumen: Métricas de temporada / rango (IP, PA, WHIP, ERA, FIP, K%, BB%, K-BB%) o boxscore de salida.
4. Panel Gráfico Triple:
   - Izquierda: Distribución de velocidades (Velocity KDEs) con medias individuales y de liga (statcast_2024_grouped.csv).
   - Centro: Strike Zone Plot (salida individual) o 5-Game Rolling Pitch Usage (temporada / rango).
   - Derecha: Short-Form Pitch Breaks (quiebre horizontal vs inducido vertical en pulgadas ±25 in con Glove/Arm side).
5. Tabla Sabermétrica de Repertorio:
   - Matriz detallada de lanzamientos con mapas de calor celulares comparados contra MLB.
6. Soporte adaptativo para LIDOM y México (LMB):
   - Misma cuadrícula 20x20 en Matplotlib con Workload por entrada, Leverage Index Tango RE24, Platoon splits y destinos PBP.
7. Créditos oficiales a Thomas Nestico (@TJStats) y autor en el pie de página.
"""

import io
import os
import math
import warnings
import urllib.request
from typing import Dict, List, Any, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.colors as mcolors
import matplotlib.patches as patches
import matplotlib.ticker as mtick
import seaborn as sns
import pandas as pd
import numpy as np
from PIL import Image

CANVAS_SIZE = (2400, 2400)
CANVAS_SIZE_LIDOM = (2400, 2400)
DPI = (300, 300)

PITCH_COLORS: Dict[str, Tuple[int, int, int]] = {
    "4-Seam Fastball": (210, 45, 73),
    "Four-Seam Fastball": (210, 45, 73),
    "Fastball": (210, 45, 73),
    "Sinker": (254, 157, 0),
    "Cutter": (147, 63, 44),
    "Slider": (238, 231, 22),
    "Sweeper": (221, 179, 59),
    "Curveball": (0, 161, 222),
    "Knuckle Curve": (0, 120, 200),
    "Changeup": (29, 190, 58),
    "Split-Finger": (59, 172, 172),
    "Splitter": (59, 172, 172),
    "Knuckleball": (102, 45, 145),
    "Desconocido": (140, 140, 140),
}

def _get_pitch_color(p_name: str) -> Tuple[int, int, int]:
    for k, v in PITCH_COLORS.items():
        if k.lower() in p_name.lower():
            return v
    return (140, 140, 140)

PITCH_COLOURS = {
    'FF': {'colour': '#FF007D', 'name': '4-Seam Fastball'},
    'FA': {'colour': '#FF007D', 'name': 'Fastball'},
    'SI': {'colour': '#98002E', 'name': 'Sinker'},
    'FC': {'colour': '#BE5FA0', 'name': 'Cutter'},
    'CH': {'colour': '#F79E70', 'name': 'Changeup'},
    'FS': {'colour': '#FE6100', 'name': 'Splitter'},
    'FO': {'colour': '#FFB000', 'name': 'Forkball'},
    'SL': {'colour': '#67E18D', 'name': 'Slider'},
    'ST': {'colour': '#1BB999', 'name': 'Sweeper'},
    'SV': {'colour': '#376748', 'name': 'Slurve'},
    'KC': {'colour': '#311D8B', 'name': 'Knuckle Curve'},
    'CU': {'colour': '#3025CE', 'name': 'Curveball'},
    'CS': {'colour': '#274BFC', 'name': 'Slow Curve'},
    'EP': {'colour': '#648FFF', 'name': 'Eephus'},
    'KN': {'colour': '#867A08', 'name': 'Knuckleball'},
    'PO': {'colour': '#472C30', 'name': 'Pitch Out'},
    'UN': {'colour': '#9C8975', 'name': 'Unknown'},
}

DICT_COLOUR = {k: v['colour'] for k, v in PITCH_COLOURS.items()}
DICT_PITCH = {k: v['name'] for k, v in PITCH_COLOURS.items()}

CMAP_SUM = mcolors.LinearSegmentedColormap.from_list("", ['#648FFF', '#FFFFFF', '#FFB000'])
CMAP_SUM_R = mcolors.LinearSegmentedColormap.from_list("", ['#FFB000', '#FFFFFF', '#648FFF'])
COLOUR_STATS = ['release_speed', 'release_extension', 'delta_run_exp_per_100', 'whiff_rate', 'in_zone_rate', 'chase_rate', 'xwoba']

PITCH_STATS_DICT = {
    'pitch': {'table_header': r'$\bf{Count}$', 'format': '.0f'},
    'release_speed': {'table_header': r'$\bf{Velocity}$', 'format': '.1f'},
    'pfx_z': {'table_header': r'$\bf{iVB}$', 'format': '.1f'},
    'pfx_x': {'table_header': r'$\bf{HB}$', 'format': '.1f'},
    'release_spin_rate': {'table_header': r'$\bf{Spin}$', 'format': '.0f'},
    'release_pos_x': {'table_header': r'$\bf{hRel}$', 'format': '.1f'},
    'release_pos_z': {'table_header': r'$\bf{vRel}$', 'format': '.1f'},
    'release_extension': {'table_header': r'$\bf{Ext.}$', 'format': '.1f'},
    'xwoba': {'table_header': r'$\bf{xwOBA}$', 'format': '.3f'},
    'pitch_usage': {'table_header': r'$\bf{Pitch\%}$', 'format': '.1%'},
    'whiff_rate': {'table_header': r'$\bf{Whiff\%}$', 'format': '.1%'},
    'in_zone_rate': {'table_header': r'$\bf{Zone\%}$', 'format': '.1%'},
    'chase_rate': {'table_header': r'$\bf{Chase\%}$', 'format': '.1%'},
    'delta_run_exp_per_100': {'table_header': r'$\bf{RV/100}$', 'format': '.1f'},
}

TABLE_COLUMNS = [
    'pitch_description', 'pitch', 'pitch_usage', 'release_speed',
    'pfx_z', 'pfx_x', 'release_spin_rate', 'release_pos_x',
    'release_pos_z', 'release_extension', 'delta_run_exp_per_100',
    'whiff_rate', 'in_zone_rate', 'chase_rate', 'xwoba'
]

BASELINES_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "statcast_2024_grouped.csv")
LOGO_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "lidom_logo.png")
if not os.path.exists(LOGO_PATH):
    LOGO_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logo.png")


def _clean_team_name(t_name: str) -> str:
    """Normaliza nombres de franquicias de LIDOM y LMB México."""
    t = str(t_name or "").replace("vs ", "").strip()
    subs = {
        # LIDOM
        "Tigres del Licey": "Licey",
        "Águilas Cibaeñas": "Águilas",
        "Aguilas Cibaenas": "Águilas",
        "Leones del Escogido": "Escogido",
        "Gigantes del Cibao": "Gigantes",
        "Estrellas Orientales": "Estrellas",
        "Toros del Este": "Toros",
        # LMB México
        "Diablos Rojos del México": "Diablos Rojos",
        "Diablos Rojos del Mexico": "Diablos Rojos",
        "Tecolotes de los Dos Laredos": "Tecolotes",
        "Pericos de Puebla": "Pericos",
        "Tigres de Quintana Roo": "Tigres QR",
        "Piratas de Campeche": "Piratas",
        "El Águila de Veracruz": "El Águila",
        "El Aguila de Veracruz": "El Águila",
        "Conspiradores de Querétaro": "Conspiradores",
        "Conspiradores de Queretaro": "Conspiradores",
        "Saraperos de Saltillo": "Saraperos",
        "Dorados de Chihuahua": "Dorados",
        "Algodoneros del Unión Laguna": "Algodoneros",
        "Algodoneros del Union Laguna": "Algodoneros",
        "Olmecas de Tabasco": "Olmecas",
        "Leones de Yucatán": "Leones YUC",
        "Leones de Yucatan": "Leones YUC",
        "Guerreros de Oaxaca": "Guerreros",
        "Acereros de Monclova": "Acereros",
        "Sultanes de Monterrey": "Sultanes",
        "Toros de Tijuana": "Toros TIJ",
        "Rieleros de Aguascalientes": "Rieleros",
        "Charros de Jalisco": "Charros",
        "Caliente de Durango": "Caliente",
        "Bravos de León": "Bravos LEO",
        "Bravos de Leon": "Bravos LEO",
    }
    return subs.get(t, t[:14])


def _fmt_date_short(d_str: str) -> str:
    parts = str(d_str or "").split('-')
    if len(parts) == 3:
        return f"{parts[2]}/{parts[1]}/{parts[0][2:]}"
    return str(d_str)


def _ip_str_to_outs(ip_val: Any) -> int:
    try:
        s = str(ip_val).strip()
        if '.' in s:
            parts = s.split('.')
            return int(parts[0]) * 3 + int(parts[1])
        return int(float(s)) * 3
    except Exception:
        return 0


def _outs_to_ip_str(outs: int) -> str:
    return f"{outs // 3}.{outs % 3}"


def _load_statcast_group() -> pd.DataFrame:
    if os.path.exists(BASELINES_CSV):
        try:
            return pd.read_csv(BASELINES_CSV)
        except Exception:
            pass
    return pd.DataFrame()


def _get_cell_colors(df_group: pd.DataFrame, df_statcast_group: pd.DataFrame) -> List[List[str]]:
    colour_list_df = []
    if df_statcast_group is None or df_statcast_group.empty:
        return [['#ffffff'] * len(TABLE_COLUMNS) for _ in range(len(df_group))]

    for pt in df_group['pitch_type'].unique():
        inner = []
        sel_lg = df_statcast_group[df_statcast_group['pitch_type'] == pt]
        sel_p = df_group[df_group['pitch_type'] == pt]

        for col in TABLE_COLUMNS:
            if col in COLOUR_STATS and col in sel_p.columns and not sel_p.empty:
                val = sel_p[col].values[0]
                if pd.isna(val) or type(val) not in (float, np.float64, int, np.int64):
                    inner.append('#ffffff')
                elif col == 'release_speed':
                    lg_mean = pd.to_numeric(sel_lg[col], errors='coerce').mean() if not sel_lg.empty else 90.0
                    norm = mcolors.Normalize(vmin=lg_mean * 0.95, vmax=lg_mean * 1.05)
                    inner.append(mcolors.to_hex(CMAP_SUM(norm(float(val)))))
                elif col == 'delta_run_exp_per_100':
                    norm = mcolors.Normalize(vmin=-1.5, vmax=1.5)
                    inner.append(mcolors.to_hex(CMAP_SUM(norm(float(val)))))
                elif col == 'xwoba':
                    lg_mean = pd.to_numeric(sel_lg[col], errors='coerce').mean() if not sel_lg.empty else 0.300
                    norm = mcolors.Normalize(vmin=lg_mean * 0.7, vmax=lg_mean * 1.3)
                    inner.append(mcolors.to_hex(CMAP_SUM_R(norm(float(val)))))
                else:
                    lg_mean = pd.to_numeric(sel_lg[col], errors='coerce').mean() if not sel_lg.empty else 0.300
                    norm = mcolors.Normalize(vmin=lg_mean * 0.7, vmax=lg_mean * 1.3)
                    inner.append(mcolors.to_hex(CMAP_SUM(norm(float(val)))))
            else:
                inner.append('#ffffff')
        colour_list_df.append(inner)
    return colour_list_df


def _group_pitches(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    agg_dict = {
        'pitch': ('pitch_type', 'count'),
        'release_speed': ('release_speed', 'mean'),
        'pfx_z': ('pfx_z', 'mean'),
        'pfx_x': ('pfx_x', 'mean'),
        'release_spin_rate': ('release_spin_rate', 'mean') if 'release_spin_rate' in df.columns else ('release_speed', 'count'),
        'release_pos_x': ('release_pos_x', 'mean') if 'release_pos_x' in df.columns and df['release_pos_x'].notna().any() else ('pitch_type', lambda x: np.nan),
        'release_pos_z': ('release_pos_z', 'mean') if 'release_pos_z' in df.columns and df['release_pos_z'].notna().any() else ('pitch_type', lambda x: np.nan),
        'release_extension': ('release_extension', 'mean') if 'release_extension' in df.columns and df['release_extension'].notna().any() else ('pitch_type', lambda x: np.nan),
        'delta_run_exp': ('delta_run_exp', 'sum') if 'delta_run_exp' in df.columns and df['delta_run_exp'].notna().any() else ('pitch_type', lambda x: 0.0),
        'swing': ('swing', 'sum') if 'swing' in df.columns else ('pitch_type', lambda x: 0),
        'whiff': ('whiff', 'sum') if 'whiff' in df.columns else ('pitch_type', lambda x: 0),
        'in_zone': ('in_zone', 'sum') if 'in_zone' in df.columns else ('pitch_type', lambda x: 0),
        'out_zone': ('out_zone', 'sum') if 'out_zone' in df.columns else ('pitch_type', lambda x: 0),
        'chase': ('chase', 'sum') if 'chase' in df.columns else ('pitch_type', lambda x: 0),
        'xwoba': ('estimated_woba_using_speedangle', 'mean') if 'estimated_woba_using_speedangle' in df.columns and df['estimated_woba_using_speedangle'].notna().any() else ('pitch_type', lambda x: np.nan),
    }

    df_group = df.groupby(['pitch_type']).agg(**agg_dict).reset_index()
    df_group['pitch_description'] = df_group['pitch_type'].map(DICT_PITCH).fillna(df_group['pitch_type'])
    total_pitches = max(1, df_group['pitch'].sum())
    df_group['pitch_usage'] = df_group['pitch'] / total_pitches

    swings_total = df_group['swing'].replace(0, np.nan)
    df_group['whiff_rate'] = (df_group['whiff'] / swings_total).fillna(0.0)
    df_group['in_zone_rate'] = (df_group['in_zone'] / df_group['pitch']).fillna(0.0)
    out_zone_total = df_group['out_zone'].replace(0, np.nan)
    df_group['chase_rate'] = (df_group['chase'] / out_zone_total).fillna(0.0)

    if 'delta_run_exp' in df.columns:
        df_group['delta_run_exp_per_100'] = -df_group['delta_run_exp'] / df_group['pitch'] * 100
    else:
        df_group['delta_run_exp_per_100'] = 0.0

    df_group['colour'] = df_group['pitch_type'].map(DICT_COLOUR).fillna('#808080')
    df_group = df_group.sort_values(by='pitch_usage', ascending=False).reset_index(drop=True)
    colour_list = df_group['colour'].tolist()

    ext_mean = df['release_extension'].mean() if 'release_extension' in df.columns else np.nan
    whiff_all = df['whiff'].sum() / max(1, df['swing'].sum()) if 'whiff' in df.columns else 0.0
    in_zone_all = df['in_zone'].sum() / total_pitches if 'in_zone' in df.columns else 0.0
    chase_all = df['chase'].sum() / max(1, df['out_zone'].sum()) if 'chase' in df.columns else 0.0
    xwoba_all = df['estimated_woba_using_speedangle'].mean() if 'estimated_woba_using_speedangle' in df.columns else np.nan
    rv_all = df['delta_run_exp'].sum() / total_pitches * -100 if 'delta_run_exp' in df.columns else 0.0

    plot_all = pd.DataFrame([{
        'pitch_type': 'All',
        'pitch_description': 'All Pitches',
        'pitch': total_pitches,
        'pitch_usage': 1.0,
        'release_speed': df['release_speed'].mean() if 'release_speed' in df.columns else np.nan,
        'pfx_z': np.nan,
        'pfx_x': np.nan,
        'release_spin_rate': df['release_spin_rate'].mean() if 'release_spin_rate' in df.columns else np.nan,
        'release_pos_x': np.nan,
        'release_pos_z': np.nan,
        'release_extension': ext_mean,
        'delta_run_exp_per_100': rv_all,
        'whiff_rate': whiff_all,
        'in_zone_rate': in_zone_all,
        'chase_rate': chase_all,
        'xwoba': xwoba_all,
        'colour': '#333333'
    }])

    df_group = pd.concat([df_group, plot_all], ignore_index=True)
    return df_group, colour_list


def _format_table(df_group: pd.DataFrame) -> pd.DataFrame:
    df_fmt = pd.DataFrame()
    for col in TABLE_COLUMNS:
        if col == 'pitch_description':
            df_fmt[col] = df_group[col].values
        elif col in PITCH_STATS_DICT:
            fmt = PITCH_STATS_DICT[col]['format']
            df_fmt[col] = df_group[col].apply(
                lambda x: '—' if pd.isna(x) else (format(x, fmt) if fmt else str(x))
            )
    return df_fmt.fillna('—')


# ── 2. Componentes Visuales del Pitching Summary (Matplotlib) ─────────────────

def _plot_headshot(ax: plt.Axes, photo_url: Optional[str]):
    ax.axis('off')
    img = None
    if photo_url:
        try:
            req = urllib.request.Request(photo_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                img = Image.open(io.BytesIO(resp.read()))
        except Exception:
            img = None

    if img is None and os.path.exists(LOGO_PATH):
        try:
            img = Image.open(LOGO_PATH)
        except Exception:
            pass

    if img is not None:
        ax.set_xlim(0, 1.0)
        ax.set_ylim(0, 1.0)
        ax.imshow(img, extent=[0.0, 1.0, 0.0, 1.0], origin='upper')


def _plot_bio(ax: plt.Axes, pitcher_info: Dict[str, Any], subtitle_line1: str, subtitle_line2: str):
    ax.axis('off')
    p_name = pitcher_info.get("name", "Pitcher")
    throws = pitcher_info.get("throws", pitcher_info.get("pitch_hand", "R"))
    age = pitcher_info.get("age", 28)
    height = pitcher_info.get("height", "6' 2\"")
    weight = pitcher_info.get("weight", 200)

    ax.text(0.5, 0.88, f"{p_name}", va='top', ha='center', fontsize=36, fontweight='bold', color='#070B19')
    ax.text(0.5, 0.62, f"{throws}HP • Edad: {age} • {height} / {weight} lbs", va='top', ha='center', fontsize=18, color='#475569')

    fs_sub1 = 20 if len(subtitle_line1) <= 35 else (17 if len(subtitle_line1) <= 45 else 15)
    ax.text(0.5, 0.38, f"{subtitle_line1}", va='top', ha='center', fontsize=fs_sub1, fontweight='bold', color='#0055B8')

    fs_sub2 = 16 if len(subtitle_line2) <= 35 else 14
    ax.text(0.5, 0.16, f"{subtitle_line2}", va='top', ha='center', fontsize=fs_sub2, fontstyle='italic', color='#64748B')


def _plot_logo(ax: plt.Axes):
    """Renderiza el logo oficial de LIDOM 360 en la esquina superior derecha."""
    ax.axis('off')
    if os.path.exists(LOGO_PATH):
        try:
            img = Image.open(LOGO_PATH)
            ax.set_xlim(0, 1.0)
            ax.set_ylim(0, 1.0)
            ax.imshow(img, extent=[0.0, 1.0, 0.0, 1.0], origin='upper')
            return
        except Exception:
            pass
    ax.text(0.5, 0.5, "LIDOM 360", ha='center', va='center', fontsize=20, fontweight='bold', color='#002D62')


def _plot_summary_table(ax: plt.Axes, stats_data: Dict[str, Any], is_game: bool):
    ax.axis('off')
    if is_game:
        cols = ['IP', 'H', 'R', 'ER', 'BB', 'SO', 'PITCHES', 'CSW%']
        vals = [
            str(stats_data.get('ip', '0.0')),
            str(stats_data.get('h', 0)),
            str(stats_data.get('r', 0)),
            str(stats_data.get('er', 0)),
            str(stats_data.get('bb', 0)),
            str(stats_data.get('so', 0)),
            str(stats_data.get('pitches', 0)),
            str(stats_data.get('csw_pct', '—')),
        ]
    else:
        cols = ['IP', 'PA', 'WHIP', 'ERA', 'FIP', 'K%', 'BB%', 'K-BB%']
        vals = [
            str(stats_data.get('ip', '—')),
            str(stats_data.get('pa', '—')),
            str(stats_data.get('whip', '—')),
            str(stats_data.get('era', '—')),
            str(stats_data.get('fip', '—')),
            str(stats_data.get('k_pct', '—')),
            str(stats_data.get('bb_pct', '—')),
            str(stats_data.get('k_bb_pct', '—')),
        ]

    tbl = ax.table(
        cellText=[vals],
        colLabels=cols,
        cellLoc='center',
        bbox=[0.0, 0.0, 1.0, 1.0]
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(18)
    for i in range(len(cols)):
        tbl.get_celld()[(0, i)].set_facecolor('#002D62')
        tbl.get_celld()[(0, i)].get_text().set_color('#FFFFFF')
        tbl.get_celld()[(0, i)].get_text().set_fontweight('bold')
        tbl.get_celld()[(1, i)].set_facecolor('#F8FAFC')
        tbl.get_celld()[(1, i)].get_text().set_fontweight('bold')


def _plot_velocity_kdes(df: pd.DataFrame, ax: plt.Axes, subplot_spec: Any, fig: plt.Figure, df_statcast_group: pd.DataFrame):
    ax.axis('off')
    ax.set_title('Pitch Velocity Distribution', fontdict={'size': 16, 'weight': 'bold', 'color': '#070B19'}, pad=10)

    counts = df['pitch_type'].value_counts()
    items = counts.index.tolist()
    if not items:
        return

    inner_grid = gridspec.GridSpecFromSubplotSpec(len(items), 1, subplot_spec=subplot_spec)
    ax_top = []
    for inner in inner_grid:
        ax_top.append(fig.add_subplot(inner))

    for i, pt in enumerate(items):
        ax_cur = ax_top[i]
        c = DICT_COLOUR.get(pt, '#808080')
        sel = df[df['pitch_type'] == pt]
        speeds = sel['release_speed'].dropna()

        if len(speeds) > 2 and speeds.nunique() > 1:
            try:
                sns.kdeplot(speeds, ax=ax_cur, fill=True, color=c, alpha=0.35, linewidth=1.8)
            except Exception:
                ax_cur.hist(speeds, bins=10, color=c, alpha=0.35, density=True)
        elif len(speeds) > 0:
            ax_cur.axvline(speeds.mean(), color=c, linewidth=2.5)

        p_mean = speeds.mean() if not speeds.empty else 90.0
        ax_cur.axvline(p_mean, color=c, linestyle='--', linewidth=1.5)

        if not df_statcast_group.empty and pt in df_statcast_group['pitch_type'].values:
            lg_row = df_statcast_group[df_statcast_group['pitch_type'] == pt]
            lg_mean = pd.to_numeric(lg_row['release_speed'], errors='coerce').mean()
            if not pd.isna(lg_mean):
                ax_cur.axvline(lg_mean, color='#1E293B', linestyle=':', linewidth=1.5)

        ax_cur.set_xlim(70, 105)
        ax_cur.set_ylabel(pt, fontdict={'size': 12, 'weight': 'bold', 'color': c}, rotation=0, labelpad=20)
        ax_cur.set_yticks([])
        ax_cur.spines['top'].set_visible(False)
        ax_cur.spines['right'].set_visible(False)
        ax_cur.spines['left'].set_visible(False)
        if i < len(items) - 1:
            ax_cur.set_xticks([])
            ax_cur.spines['bottom'].set_visible(False)
        else:
            ax_cur.set_xlabel('Velocity (mph)', fontdict={'size': 13, 'weight': 'bold', 'color': '#070B19'})


def _plot_strike_zone(df: pd.DataFrame, ax: plt.Axes):
    """Renderiza el scatter de pitcheos sobre la zona de strike 3x3 para salidas individuales."""
    ax.set_title('Strike Zone Plot', fontdict={'size': 16, 'weight': 'bold', 'color': '#070B19'}, pad=10)
    for pt in df['pitch_type'].unique():
        pt_df = df[df['pitch_type'] == pt]
        c = DICT_COLOUR.get(pt, '#808080')
        ax.scatter(
            pt_df['plate_x'], pt_df['plate_z'],
            color=c, edgecolors='black', alpha=0.85, s=75, label=pt, zorder=3
        )

    # Cajón de strike zone
    sz_b = float(df['sz_bot'].median()) if 'sz_bot' in df.columns and df['sz_bot'].notnull().any() else 1.5
    sz_t = float(df['sz_top'].median()) if 'sz_top' in df.columns and df['sz_top'].notnull().any() else 3.5
    sz_w = 17.0 / 12.0
    sz_l = -sz_w / 2.0

    rect = patches.Rectangle((sz_l, sz_b), sz_w, sz_t - sz_b, linewidth=2.5, edgecolor='#0F172A', facecolor='none', zorder=2)
    ax.add_patch(rect)

    # Rejilla 3x3
    w_third = sz_w / 3.0
    h_third = (sz_t - sz_b) / 3.0
    for c in range(1, 3):
        ax.plot([sz_l + c * w_third, sz_l + c * w_third], [sz_b, sz_t], color='#64748B', linestyle=':', linewidth=1.2, zorder=2)
    for r in range(1, 3):
        ax.plot([sz_l, sz_l + sz_w], [sz_b + r * h_third, sz_b + r * h_third], color='#64748B', linestyle=':', linewidth=1.2, zorder=2)

    # Home plate
    plate = patches.Polygon([[-0.708, 0], [0.708, 0], [0.708, -0.2], [0, -0.4], [-0.708, -0.2]],
                            closed=True, facecolor='#CBD5E1', edgecolor='#0F172A', linewidth=1.5, zorder=2)
    ax.add_patch(plate)

    ax.set_xlim(-2.2, 2.2)
    ax.set_ylim(-0.5, 4.5)
    ax.set_xlabel('Horizontal Plate Location (ft)', fontdict={'size': 13, 'weight': 'bold', 'color': '#070B19'})
    ax.set_ylabel('Vertical Plate Location (ft)', fontdict={'size': 13, 'weight': 'bold', 'color': '#070B19'})
    ax.set_aspect('equal', adjustable='box')
    ax.grid(True, linestyle='--', alpha=0.3)


def _plot_rolling_usage(df: pd.DataFrame, ax: plt.Axes):
    if 'game_date' not in df.columns or df.empty or df['game_date'].nunique() < 2:
        _plot_strike_zone(df, ax)
        return

    ax.set_title('5-Game Rolling Pitch Usage', fontdict={'size': 16, 'weight': 'bold', 'color': '#070B19'}, pad=10)
    g_dates = sorted(df['game_date'].unique())

    totals = df.groupby(['game_date', 'pitch_type']).size().unstack(fill_value=0)
    rolling = totals.rolling(window=min(5, len(g_dates)), min_periods=1).sum()
    pcts = rolling.div(rolling.sum(axis=1), axis=0) * 100

    x_vals = list(range(1, len(g_dates) + 1))
    for pt in pcts.columns:
        c = DICT_COLOUR.get(pt, '#808080')
        ax.plot(x_vals, pcts[pt], label=pt, color=c, linewidth=2.8)

    ax.set_ylim(0, max(pcts.max().max() * 1.15, 60))
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(xmax=100, decimals=0))
    ax.set_xlabel('Game Number', fontdict={'size': 13, 'weight': 'bold', 'color': '#070B19'})
    ax.set_ylabel('Pitch Usage', fontdict={'size': 13, 'weight': 'bold', 'color': '#070B19'})
    ax.grid(True, linestyle='--', alpha=0.3)


def _plot_pitch_breaks(df: pd.DataFrame, ax: plt.Axes):
    ax.set_title('Pitch Breaks', fontdict={'size': 16, 'weight': 'bold', 'color': '#070B19'}, pad=10)
    ax.axhline(0, color='#94A3B8', linestyle='--', linewidth=1.5)
    ax.axvline(0, color='#94A3B8', linestyle='--', linewidth=1.5)

    for pt in df['pitch_type'].unique():
        sel = df[df['pitch_type'] == pt]
        c = DICT_COLOUR.get(pt, '#808080')
        ax.scatter(sel['pfx_x'], sel['pfx_z'], color=c, label=pt, alpha=0.65, edgecolors='#0F172A', s=45)

    ax.set_xlim(-25, 25)
    ax.set_ylim(-25, 25)
    ax.set_xlabel('Horizontal Break (in)', fontdict={'size': 13, 'weight': 'bold', 'color': '#070B19'})
    ax.set_ylabel('Induced Vertical Break (in)', fontdict={'size': 13, 'weight': 'bold', 'color': '#070B19'})
    ax.text(-24, -24, r'$\leftarrow Glove\ Side$', fontsize=9, bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.8))
    ax.text(24, -24, r'$Arm\ Side \rightarrow$', fontsize=9, ha='right', bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.8))
    ax.grid(True, linestyle='--', alpha=0.3)


def _plot_footer(ax: plt.Axes, is_lidom: bool = False):
    ax.axis('off')
    ax.text(
        0.0, 0.55,
        "LIDOM 360",
        fontsize=15, fontweight='bold', color='#002D62', ha='left', va='center'
    )
    ax.text(
        0.0, 0.05,
        "@lidom360 • Jorge Leonardo Loreto",
        fontsize=11, fontweight='normal', color='#64748B', ha='left', va='center'
    )
    ax.text(
        1.0, 0.55,
        "Diseño inspirado en Thomas Nestico (@TJStats)",
        fontsize=13, fontweight='bold', color='#002D62', ha='right', va='center'
    )
    src_text = "Data: MLB Stats API / Gameday PBP" if is_lidom else "Data: MLB Statcast / Baseball Savant"
    ax.text(
        1.0, 0.05,
        src_text,
        fontsize=11, fontweight='normal', color='#64748B', ha='right', va='center'
    )


# ── 3. Motor Principal de Renderizado Nestico (MLB / Statcast) ─────────────────

def build_nestico_pitching_summary(
    df: pd.DataFrame,
    pitcher_info: Dict[str, Any],
    mode: str = "game",
    season: int = 2026,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    game_summary: Optional[Dict[str, Any]] = None,
    game_logs: Optional[List[Dict[str, Any]]] = None,
    is_lidom: bool = False,
    dpi: int = 150,
) -> bytes:
    df_statcast_group = _load_statcast_group()

    fig = plt.figure(figsize=(20, 20), facecolor='white')
    gs = gridspec.GridSpec(
        7, 8,
        height_ratios=[2, 18, 7, 36, 2, 29, 6],
        width_ratios=[1, 18, 18, 18, 18, 18, 18, 1]
    )

    ax_headshot = fig.add_subplot(gs[1, 1])
    ax_bio = fig.add_subplot(gs[1, 2:6])
    ax_logo = fig.add_subplot(gs[1, 6])
    ax_summary = fig.add_subplot(gs[2, 1:7])

    gs_plots = gridspec.GridSpecFromSubplotSpec(1, 3, subplot_spec=gs[3, 1:7], wspace=0.36)
    ax_kde = fig.add_subplot(gs_plots[0, 0])
    ax_center = fig.add_subplot(gs_plots[0, 1])
    ax_breaks = fig.add_subplot(gs_plots[0, 2])

    ax_table = fig.add_subplot(gs[5, 1:7])
    ax_footer = fig.add_subplot(gs[6, 1:7])

    # 1. Cabecera
    _plot_headshot(ax_headshot, pitcher_info.get("photo_url"))
    league_tag = "LIDOM (TrackMan)" if is_lidom else "MLB"
    team_name = pitcher_info.get("team_name", "")
    team_clean = _clean_team_name(team_name) if team_name else ""

    if mode == "season":
        sub1 = f"Resumen de Temporada ({league_tag})"
        sub2 = f"{team_clean} | Temporada {season}" if team_clean else f"Temporada {season} {league_tag}"
    elif mode == "game" and game_summary:
        sub1 = f"Salida vs {_clean_team_name(game_summary.get('opponent', 'Rival'))}"
        sub2 = f"Fecha: {game_summary.get('date', '')} • {league_tag}"
    else:
        sub1 = f"Período Personalizado ({league_tag})"
        sub2 = f"{start_date} al {end_date}"

    _plot_bio(ax_bio, pitcher_info, sub1, sub2)
    _plot_logo(ax_logo)

    # 2. Resumen Superior
    if mode == "game" and game_summary:
        _plot_summary_table(ax_summary, game_summary, is_game=True)
    else:
        tot_ip = sum(_ip_str_to_outs(g.get("ip", "0.0")) for g in game_logs) if game_logs else 0
        tot_ip_str = _outs_to_ip_str(tot_ip)
        float_ip = tot_ip / 3.0
        tot_er = sum(int(g.get("er", 0)) for g in game_logs) if game_logs else 0
        tot_h = sum(int(g.get("h", 0)) for g in game_logs) if game_logs else 0
        tot_bb = sum(int(g.get("bb", 0)) for g in game_logs) if game_logs else 0
        tot_so = sum(int(g.get("so", 0)) for g in game_logs) if game_logs else 0
        tot_bf = 0
        for g in (game_logs or []):
            outs_g = _ip_str_to_outs(g.get("ip", "0.0"))
            bf_g = int(g.get("bf") or (int(g.get("so", 0)) + int(g.get("bb", 0)) + int(g.get("h", 0)) + outs_g))
            tot_bf += bf_g
        if tot_bf == 0:
            tot_bf = len(df)

        era_c = f"{(tot_er * 9.0 / float_ip):.2f}" if float_ip > 0 else "0.00"
        whip_c = f"{((tot_bb + tot_h) / float_ip):.2f}" if float_ip > 0 else "0.00"
        k_pct = f"{(tot_so / tot_bf * 100):.1f}%" if tot_bf > 0 else "—"
        bb_pct = f"{(tot_bb / tot_bf * 100):.1f}%" if tot_bf > 0 else "—"
        k_bb_pct = f"{((tot_so - tot_bb) / tot_bf * 100):.1f}%" if tot_bf > 0 else "—"

        season_dict = {
            'ip': tot_ip_str if tot_ip > 0 else f"{len(df)//15}.0",
            'pa': str(tot_bf),
            'whip': whip_c,
            'era': era_c,
            'fip': era_c,
            'k_pct': k_pct,
            'bb_pct': bb_pct,
            'k_bb_pct': k_bb_pct,
        }
        _plot_summary_table(ax_summary, season_dict, is_game=False)

    # 3. Plots
    if not df.empty and 'pitch_type' in df.columns:
        _plot_velocity_kdes(df, ax_kde, gs_plots[0, 0], fig, df_statcast_group)
        _plot_rolling_usage(df, ax_center)
        _plot_pitch_breaks(df, ax_breaks)

        # 4. Tabla Sabermétrica de Repertorio
        df_group, colour_list = _group_pitches(df)
        df_fmt = _format_table(df_group)
        cell_colors = _get_cell_colors(df_group, df_statcast_group)

        ax_table.axis('off')
        col_labels = [PITCH_STATS_DICT[c]['table_header'] if c in PITCH_STATS_DICT else r'$\bf{Pitch\ Name}$' for c in TABLE_COLUMNS]
        col_widths = [0.11] + [(0.89 / 14.0)] * 14

        tbl = ax_table.table(
            cellText=df_fmt.values,
            colLabels=col_labels,
            colWidths=col_widths,
            cellColours=cell_colors,
            cellLoc='center',
            bbox=[0.0, 0.0, 1.0, 1.0]
        )
        tbl.auto_set_font_size(False)
        tbl.set_fontsize(13)
        for i in range(len(TABLE_COLUMNS)):
            tbl.get_celld()[(0, i)].set_facecolor('#002D62')
            tbl.get_celld()[(0, i)].get_text().set_color('#FFFFFF')
            tbl.get_celld()[(0, i)].get_text().set_fontweight('bold')

        for row_idx, pt in enumerate(df_group['pitch_type']):
            c = DICT_COLOUR.get(pt, '#002D62')
            cell = tbl.get_celld()[(row_idx + 1, 0)]
            cell.set_facecolor(c)
            cell.get_text().set_color('#FFFFFF')
            cell.get_text().set_fontweight('bold')
    else:
        ax_kde.text(0.5, 0.5, "Sin telemetría Statcast", ha='center', va='center')
        ax_center.text(0.5, 0.5, "Sin lanzamientos registrados", ha='center', va='center')
        ax_breaks.text(0.5, 0.5, "Sin mapa de quiebres", ha='center', va='center')
        ax_table.axis('off')

    # 5. Footer
    _plot_footer(ax_footer, is_lidom=is_lidom)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=dpi, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    return buf.getvalue()


# ── 4. Motor Especializado PBP para LIDOM y México ─────────────────────────────

def build_lidom_matplotlib_summary(
    pitcher_info: Dict[str, Any],
    game_summary: Dict[str, Any],
    analysis: Dict[str, Any],
    season: int = 2026,
    dpi: int = 150,
    mode: str = "game",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    game_logs: Optional[List[Dict[str, Any]]] = None,
    phase: str = "all",
    is_mexico: bool = False,
) -> bytes:
    team_name = pitcher_info.get("team_name", "Equipo")
    team_clean = _clean_team_name(team_name)

    league_name = "México" if is_mexico else "LIDOM"
    sub1_prefix = f"{league_name} • " if is_mexico else ""

    if mode == "game":
        opp_raw = game_summary.get('opponent', 'Rival')
        opp_clean = _clean_team_name(opp_raw)
        sub1 = f"vs {opp_clean}"
        sub2 = f"{team_clean} | {game_summary.get('date', '')}"
    elif mode == "season":
        phase_label = ""
        if phase == "R":
            phase_label = " (Serie Regular)"
        elif phase == "W" or phase == "L":
            phase_label = " (Round Robin)"
        elif phase == "F":
            phase_label = " (Serie Final)"

        sub1 = f"{sub1_prefix}Temporada Completa{phase_label}"
        league_tag = "LMB Verano" if is_mexico else "LIDOM"
        sub2 = f"{team_clean} | {league_tag} {season}"
    else:
        sub1 = f"{sub1_prefix}Período Personalizado"
        sub2 = f"{team_clean} | {start_date} al {end_date}"

    # Modo Temporada Completa o Rango: Historial de salidas
    if mode in ("season", "range") and game_logs is not None:
        logs = list(game_logs)

        # Enriquecer salidas si tienen CSW% o Whiff% faltante
        needs_enrich = any(
            g.get("game_pk") and (
                not g.get("csw_pct") or g.get("csw_pct") in (0, 0.0, "0", "0.0", "0.0%")
                or int(g.get("pitches") or 0) == 0
            )
            for g in logs
        )
        if needs_enrich:
            from core.pitching_engine import get_game_pitch_data
            p_id = pitcher_info.get("id")

            def _enrich_log(g: Dict[str, Any]) -> Dict[str, Any]:
                g_pk = g.get("game_pk")
                if g_pk and p_id:
                    try:
                        p_data = get_game_pitch_data(g_pk, p_id, is_lidom=(not is_mexico))
                        kpis = p_data.get("pbp_kpis", {})
                        if kpis:
                            csw_str = str(kpis.get("csw_pct", "0.0%")).replace('%', '')
                            whiff_str = str(kpis.get("whiff_pct", "0.0%")).replace('%', '')
                            g["csw_pct"] = float(csw_str) if csw_str else 0.0
                            g["whiff_pct"] = float(whiff_str) if whiff_str else 0.0
                            if int(g.get("pitches") or 0) == 0:
                                g["pitches"] = p_data.get("total_pitches", 0)
                                g["strikes"] = kpis.get("strikes", 0)
                    except Exception:
                        pass
                return g

            with ThreadPoolExecutor(max_workers=6) as ex:
                logs = list(ex.map(_enrich_log, logs))

        fig = plt.figure(figsize=(20, 20), facecolor='white')
        gs = gridspec.GridSpec(
            7, 8,
            height_ratios=[2, 18, 7, 36, 4, 27, 5],
            width_ratios=[1, 18, 18, 18, 18, 18, 18, 1]
        )

        ax_headshot = fig.add_subplot(gs[1, 1])
        ax_bio = fig.add_subplot(gs[1, 2:6])
        ax_logo = fig.add_subplot(gs[1, 6])
        ax_season_table = fig.add_subplot(gs[2, 1:7])

        gs_plots = gridspec.GridSpecFromSubplotSpec(1, 3, subplot_spec=gs[3, 1:7], wspace=0.36)
        ax_plot_1 = fig.add_subplot(gs_plots[0, 0])
        ax_plot_2 = fig.add_subplot(gs_plots[0, 1])
        ax_plot_3 = fig.add_subplot(gs_plots[0, 2])

        ax_table = fig.add_subplot(gs[5, 1:7])
        ax_footer = fig.add_subplot(gs[6, 1:7])

        _plot_headshot(ax_headshot, pitcher_info.get("photo_url"))
        _plot_bio(ax_bio, pitcher_info, sub1, sub2)
        _plot_logo(ax_logo)

        tot_outs = sum(_ip_str_to_outs(g.get("ip", "0.0")) for g in logs)
        tot_ip_str = _outs_to_ip_str(tot_outs)
        float_ip = tot_outs / 3.0
        tot_games = len(logs)
        tot_h = sum(int(g.get("h") or 0) for g in logs)
        tot_r = sum(int(g.get("r") or 0) for g in logs)
        tot_er = sum(int(g.get("er") or 0) for g in logs)
        tot_bb = sum(int(g.get("bb") or 0) for g in logs)
        tot_so = sum(int(g.get("so") or 0) for g in logs)
        tot_pitches = sum(int(g.get("pitches") or 0) for g in logs)

        era_val = f"{(tot_er * 9.0 / float_ip):.2f}" if float_ip > 0 else "0.00"
        whip_val = f"{((tot_bb + tot_h) / float_ip):.2f}" if float_ip > 0 else "0.00"
        csw_season = f"{(sum(float(g.get('csw_pct', 0)) * int(g.get('pitches', 0)) for g in logs) / tot_pitches):.1f}%" if tot_pitches > 0 else "0.0%"
        whiff_season = f"{(sum(float(g.get('whiff_pct', 0)) * int(g.get('pitches', 0)) for g in logs) / tot_pitches):.1f}%" if tot_pitches > 0 else "0.0%"

        cols_sum = ['IP', 'JUEGOS', 'WHIP', 'ERA', 'SO (K)', 'BB', 'PITCHES', 'CSW%', 'Whiff%']
        vals_sum = [tot_ip_str, str(tot_games), whip_val, era_val, str(tot_so), str(tot_bb), str(tot_pitches), csw_season, whiff_season]

        ax_season_table.axis('off')
        tbl = ax_season_table.table(
            cellText=[vals_sum],
            colLabels=cols_sum,
            cellLoc='center',
            bbox=[0.0, 0.0, 1.0, 1.0]
        )
        tbl.auto_set_font_size(False)
        tbl.set_fontsize(16)
        for i in range(len(cols_sum)):
            tbl.get_celld()[(0, i)].set_facecolor('#002D62')
            tbl.get_celld()[(0, i)].get_text().set_color('#FFFFFF')
            tbl.get_celld()[(0, i)].get_text().set_fontweight('bold')
            tbl.get_celld()[(1, i)].set_facecolor('#F8FAFC')
            tbl.get_celld()[(1, i)].get_text().set_fontweight('bold')

        sorted_logs = sorted(logs, key=lambda x: str(x.get('date', '')))
        plot_logs = sorted_logs[-10:] if len(sorted_logs) > 10 else sorted_logs
        x_indices = list(range(len(plot_logs)))
        date_labels = [str(g.get('date', ''))[-5:].replace('-', '/') for g in plot_logs]

        # Plot 1: Bolas y Strikes
        p_counts = [int(g.get('pitches') or 0) for g in plot_logs]
        strks = [int(g.get('strikes') or int(p * 0.62)) for g, p in zip(plot_logs, p_counts)]
        bolas = [max(0, p - s) for p, s in zip(p_counts, strks)]

        ax_plot_1.bar(x_indices, strks, color='#002D62', edgecolor='#0F172A', label='Strikes', width=0.55)
        ax_plot_1.bar(x_indices, bolas, bottom=strks, color='#EAB308', edgecolor='#0F172A', label='Bolas', width=0.55)
        for idx, tot in zip(x_indices, p_counts):
            if tot > 0:
                ax_plot_1.text(idx, tot + 1.2, str(tot), ha='center', va='bottom', fontsize=10, fontweight='bold', color='#070B19')
        ax_plot_1.set_xticks(x_indices)
        ax_plot_1.set_xticklabels(date_labels, rotation=45, ha='right', fontsize=11, fontweight='bold')
        ax_plot_1.set_ylim(0, max(p_counts) * 1.22 if p_counts and max(p_counts) > 0 else 30)
        ax_plot_1.set_ylabel('Conteo Pitcheos', fontsize=13, fontweight='bold', color='#070B19')
        ax_plot_1.set_title('Bolas y Strikes por Salida', fontsize=15, fontweight='bold', color='#070B19')
        ax_plot_1.legend(loc='upper right', fontsize=11)
        ax_plot_1.grid(True, linestyle='--', alpha=0.3)

        # Plot 2: Whiff% por Salida
        whiff_vals = [float(g.get('whiff_pct', 0.0)) for g in plot_logs]
        ax_plot_2.plot(x_indices, whiff_vals, color='#2563EB', marker='o', linewidth=2.8, markersize=8, label='Whiff%')
        avg_whiff = np.mean(whiff_vals) if whiff_vals else 0.0
        ax_plot_2.axhline(avg_whiff, color='#94A3B8', linestyle='--', linewidth=1.8, label=f'Promedio ({avg_whiff:.1f}%)')
        for idx, w in zip(x_indices, whiff_vals):
            ax_plot_2.text(idx, w + 1.6, f"{w:.1f}%", ha='center', va='bottom', fontsize=10, fontweight='bold', color='#1E40AF')
        ax_plot_2.set_xticks(x_indices)
        ax_plot_2.set_xticklabels(date_labels, rotation=45, ha='right', fontsize=11, fontweight='bold')
        ax_plot_2.set_ylim(0, max(max(whiff_vals or [10]) * 1.35, 38))
        ax_plot_2.set_ylabel('Whiff% (Abanicados)', fontsize=13, fontweight='bold', color='#070B19')
        ax_plot_2.set_title('Whiff% por Salida', fontsize=15, fontweight='bold', color='#070B19')
        ax_plot_2.legend(loc='upper right', fontsize=11)
        ax_plot_2.grid(True, linestyle='--', alpha=0.3)

        # Plot 3: CSW% por Salida
        csw_vals = [float(g.get('csw_pct', 0.0)) for g in plot_logs]
        ax_plot_3.plot(x_indices, csw_vals, color='#059669', marker='s', linewidth=2.8, markersize=8, label='CSW%')
        avg_csw = np.mean(csw_vals) if csw_vals else 0.0
        ax_plot_3.axhline(30.0, color='#DC2626', linestyle=':', linewidth=2.0, label='Elite CSW (30%)')
        ax_plot_3.axhline(avg_csw, color='#94A3B8', linestyle='--', linewidth=1.8, label=f'Promedio ({avg_csw:.1f}%)')
        for idx, c in zip(x_indices, csw_vals):
            ax_plot_3.text(idx, c + 1.6, f"{c:.1f}%", ha='center', va='bottom', fontsize=10, fontweight='bold', color='#065F46')
        ax_plot_3.set_xticks(x_indices)
        ax_plot_3.set_xticklabels(date_labels, rotation=45, ha='right', fontsize=11, fontweight='bold')
        ax_plot_3.set_ylim(0, max(max(csw_vals or [10]) * 1.35, 48))
        ax_plot_3.set_ylabel('CSW% (Called + Whiff)', fontsize=13, fontweight='bold', color='#070B19')
        ax_plot_3.set_title('CSW% por Salida', fontsize=15, fontweight='bold', color='#070B19')
        ax_plot_3.legend(loc='lower left', fontsize=11)
        ax_plot_3.grid(True, linestyle='--', alpha=0.3)

        # Tabla de Salidas
        ax_table.axis('off')
        disp_logs = sorted_logs[-8:] if len(sorted_logs) > 8 else sorted_logs
        disp_logs = list(reversed(disp_logs))

        table_data = []
        for g in disp_logs:
            p_cnt = int(g.get('pitches') or 0)
            s_cnt = int(g.get('strikes') or int(p_cnt * 0.62))
            csw_p = float(g.get('csw_pct') or 0.0)
            whiff_p = float(g.get('whiff_pct') or 0.0)
            dec = str(g.get('decision') or '—').strip()
            if not dec:
                dec = '—'

            table_data.append([
                _fmt_date_short(g.get('date', '')),
                _clean_team_name(g.get('opponent', 'Rival')),
                str(g.get('role', 'Abridor')),
                dec,
                str(g.get('ip', '0.0')),
                str(g.get('h', 0)),
                str(g.get('er', 0)),
                str(g.get('bb', 0)),
                str(g.get('so', 0)),
                f"{p_cnt} ({s_cnt}-{p_cnt - s_cnt})",
                f"{csw_p:.1f}%",
                f"{whiff_p:.1f}%",
            ])

        col_labels_pbp = ['Fecha', 'Rival', 'Rol', 'Dec.', 'IP', 'H', 'CL', 'BB', 'K', 'Pitcheos (P-S)', 'CSW%', 'Whiff%']
        if not table_data:
            table_data = [["—"] * len(col_labels_pbp)]

        season_table = ax_table.table(
            cellText=table_data,
            colLabels=col_labels_pbp,
            cellLoc='center',
            bbox=[0.0, 0.0, 1.0, 1.0]
        )
        season_table.auto_set_font_size(False)
        season_table.set_fontsize(14)

        for i in range(len(col_labels_pbp)):
            season_table.get_celld()[(0, i)].set_facecolor('#002D62')
            season_table.get_celld()[(0, i)].get_text().set_color('#FFFFFF')
            season_table.get_celld()[(0, i)].get_text().set_fontweight('bold')

        for r_idx in range(len(table_data)):
            bg = '#FFFFFF' if r_idx % 2 == 0 else '#F8FAFC'
            for c_idx in range(len(col_labels_pbp)):
                cell = season_table.get_celld()[(r_idx + 1, c_idx)]
                cell.set_facecolor(bg)
                if c_idx == 3:
                    dec_val = table_data[r_idx][c_idx]
                    if dec_val == 'W':
                        cell.get_text().set_color('#059669')
                        cell.get_text().set_fontweight('bold')
                    elif dec_val == 'L':
                        cell.get_text().set_color('#DC2626')
                        cell.get_text().set_fontweight('bold')
                    elif dec_val in ('SV', 'HLD'):
                        cell.get_text().set_color('#2563EB')
                        cell.get_text().set_fontweight('bold')

        _plot_footer(ax_footer, is_lidom=(not is_mexico))

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            plt.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=dpi, bbox_inches='tight', facecolor='white')
        plt.close(fig)
        return buf.getvalue()

    # Modo Salida Individual PBP
    fig = plt.figure(figsize=(20, 20), facecolor='white')
    gs = gridspec.GridSpec(
        7, 8,
        height_ratios=[2, 18, 7, 36, 2, 29, 6],
        width_ratios=[1, 18, 18, 18, 18, 18, 18, 1]
    )

    ax_headshot = fig.add_subplot(gs[1, 1])
    ax_bio = fig.add_subplot(gs[1, 2:6])
    ax_logo = fig.add_subplot(gs[1, 6])
    ax_summary = fig.add_subplot(gs[2, 1:7])

    gs_plots = gridspec.GridSpecFromSubplotSpec(1, 3, subplot_spec=gs[3, 1:7], wspace=0.36)
    ax_plot_1 = fig.add_subplot(gs_plots[0, 0])
    ax_plot_2 = fig.add_subplot(gs_plots[0, 1])
    ax_plot_3 = fig.add_subplot(gs_plots[0, 2])

    ax_table = fig.add_subplot(gs[5, 1:7])
    ax_footer = fig.add_subplot(gs[6, 1:7])

    _plot_headshot(ax_headshot, pitcher_info.get("photo_url"))
    _plot_bio(ax_bio, pitcher_info, sub1, sub2)
    _plot_logo(ax_logo)

    pitches = analysis.get("pitches", [])
    total_pitches_pbp = game_summary.get('pitches') or analysis.get('total_pitches') or len(pitches) or 0
    kpis = analysis.get("pbp_kpis", {})

    summary_dict = {
        'ip': game_summary.get('ip', '0.0'),
        'h': game_summary.get('h', 0),
        'r': game_summary.get('r', 0),
        'er': game_summary.get('er', 0),
        'bb': game_summary.get('bb', 0),
        'so': game_summary.get('so', 0),
        'pitches': total_pitches_pbp,
        'csw_pct': kpis.get('csw_pct', '—'),
    }
    _plot_summary_table(ax_summary, summary_dict, is_game=True)

    workload = analysis.get("innings_workload", [])
    if workload:
        innings = [w.get('inning') for w in workload]
        stks = [w.get('strikes', 0) for w in workload]
        bls = [w.get('balls', 0) for w in workload]
        tot_inn = [s + b for s, b in zip(stks, bls)]

        x = np.arange(len(innings))
        ax_plot_1.bar(x, stks, label='Strikes', color='#002D62', edgecolor='#0F172A')
        ax_plot_1.bar(x, bls, bottom=stks, label='Bolas', color='#EAB308', edgecolor='#0F172A')

        for idx, tot in enumerate(tot_inn):
            if tot > 0:
                ax_plot_1.text(idx, tot + 0.8, str(tot), ha='center', va='bottom', fontsize=11, fontweight='bold', color='#070B19')

        ax_plot_1.set_xticks(x)
        ax_plot_1.set_xticklabels([f"Inn {i}" for i in innings], fontsize=11, fontweight='bold')
        ax_plot_1.set_ylim(0, max(tot_inn) * 1.25 if tot_inn and max(tot_inn) > 0 else 20)
        ax_plot_1.set_ylabel('Conteo Pitcheos', fontsize=13, fontweight='bold', color='#070B19')
        ax_plot_1.set_title('Carga por Entrada (Workload)', fontsize=16, fontweight='bold', color='#070B19')
        ax_plot_1.legend(loc='upper right', fontsize=10)
        ax_plot_1.grid(True, linestyle='--', alpha=0.3)

        lis = [w.get('avg_li', 1.0) for w in workload]
        ax_plot_2.plot(x, lis, marker='o', color='#2563EB', linewidth=2.8, markersize=8, label='LI Promedio')
        ax_plot_2.axhline(1.0, color='#94A3B8', linestyle='--', linewidth=1.5, label='Línea Neutra (1.0 LI)')

        for idx, li in enumerate(lis):
            ax_plot_2.text(idx, li + 0.12, f"{li:.2f}", ha='center', va='bottom', fontsize=11, fontweight='bold', color='#1E40AF')

        ax_plot_2.set_xticks(x)
        ax_plot_2.set_xticklabels([f"Inn {i}" for i in innings], fontsize=11, fontweight='bold')
        max_li = max(lis) if lis else 1.0
        ax_plot_2.set_ylim(0, max(max_li * 1.3, 2.0))
        ax_plot_2.set_ylabel('Leverage Index (LI)', fontsize=13, fontweight='bold', color='#070B19')
        ax_plot_2.set_title('Apalancamiento (Tango RE24)', fontsize=16, fontweight='bold', color='#070B19')
        ax_plot_2.legend(loc='upper right', fontsize=10)
        ax_plot_2.grid(True, linestyle='--', alpha=0.3)
    else:
        ax_plot_1.axis('off')
        ax_plot_2.axis('off')

    splits = analysis.get("splits_platoon", {})
    vs_l = splits.get("LHB", {})
    vs_r = splits.get("RHB", {})
    p_l = vs_l.get('pitches', 0)
    p_r = vs_r.get('pitches', 0)

    cats = ['Strike%', 'Whiff%', 'CSW%']
    vals_l = [
        float(str(vs_l.get('strike_pct', '0')).replace('%', '')),
        float(str(vs_l.get('whiff_pct', '0')).replace('%', '')),
        float(str(vs_l.get('csw_pct', '0')).replace('%', ''))
    ]
    vals_r = [
        float(str(vs_r.get('strike_pct', '0')).replace('%', '')),
        float(str(vs_r.get('whiff_pct', '0')).replace('%', '')),
        float(str(vs_r.get('csw_pct', '0')).replace('%', ''))
    ]

    x = np.arange(len(cats))
    width = 0.35
    bars_l = ax_plot_3.bar(x - width/2, vals_l, width, label=f"vs Zurdos ({p_l} P)", color='#3B82F6', edgecolor='#0F172A')
    bars_r = ax_plot_3.bar(x + width/2, vals_r, width, label=f"vs Derechos ({p_r} P)", color='#F59E0B', edgecolor='#0F172A')

    for rect in bars_l:
        h = rect.get_height()
        if h > 0:
            ax_plot_3.text(rect.get_x() + rect.get_width()/2., h + 1.2, f"{h:.0f}%", ha='center', va='bottom', fontsize=10, fontweight='bold', color='#1E40AF')
    for rect in bars_r:
        h = rect.get_height()
        if h > 0:
            ax_plot_3.text(rect.get_x() + rect.get_width()/2., h + 1.2, f"{h:.0f}%", ha='center', va='bottom', fontsize=10, fontweight='bold', color='#B45309')

    ax_plot_3.set_xticks(x)
    ax_plot_3.set_xticklabels(cats, fontsize=11, fontweight='bold')
    ax_plot_3.set_ylim(0, 100)
    ax_plot_3.yaxis.set_major_formatter(mtick.PercentFormatter(xmax=100, decimals=0))
    ax_plot_3.set_ylabel('Porcentaje (%)', fontsize=13, fontweight='bold', color='#070B19')
    ax_plot_3.set_title('Platoon Splits (LHB vs RHB)', fontsize=16, fontweight='bold', color='#070B19')
    ax_plot_3.legend(loc='upper right', fontsize=10)
    ax_plot_3.grid(True, linestyle='--', alpha=0.3)

    ax_table.axis('off')
    pbp_rows = analysis.get("pbp_table", [])
    if pbp_rows:
        t_data = [[r.get('Destino', ''), str(r.get('Conteo', 0)), str(r.get('% Pitcheos', ''))] for r in pbp_rows]
        t_cols = ['Destino del Pitcheo', 'Total Conteo', 'Distribución %']
        pbp_table = ax_table.table(
            cellText=t_data,
            colLabels=t_cols,
            cellLoc='center',
            bbox=[0.12, 0.05, 0.76, 0.90]
        )
        pbp_table.auto_set_font_size(False)
        pbp_table.set_fontsize(15)
        for i in range(3):
            pbp_table.get_celld()[(0, i)].set_facecolor('#002D62')
            pbp_table.get_celld()[(0, i)].get_text().set_color('#FFFFFF')
            pbp_table.get_celld()[(0, i)].get_text().set_fontweight('bold')
        for r_idx in range(len(t_data)):
            bg = '#FFFFFF' if r_idx % 2 == 0 else '#F8FAFC'
            for c_idx in range(3):
                pbp_table.get_celld()[(r_idx + 1, c_idx)].set_facecolor(bg)

    _plot_footer(ax_footer, is_lidom=(not is_mexico))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=dpi, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    return buf.getvalue()


# ── 5. Wrapper de Compatibilidad Retroactiva ───────────────────────────────────

def build_pitching_summary_card(
    pitcher_data: Optional[Dict[str, Any]] = None,
    game_data: Optional[Dict[str, Any]] = None,
    pitch_analysis: Optional[Dict[str, Any]] = None,
    is_lidom: bool = False,
    is_mexico: bool = False,
    branch: Optional[str] = None,
    season: int = 2026,
    pitcher_info: Optional[Dict[str, Any]] = None,
    game_summary: Optional[Dict[str, Any]] = None,
    analysis: Optional[Dict[str, Any]] = None,
    mode: str = "game",
    game_logs: Optional[List[Dict[str, Any]]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    phase: str = "all",
    df_statcast: Optional[pd.DataFrame] = None,
    df: Optional[pd.DataFrame] = None,
    card_type: Optional[str] = None,
    dpi: int = 150,
    **kwargs,
) -> bytes:
    """
    Función de compatibilidad universal para generación de tarjetas HD (2400x2400 px a 300 DPI).
    Admite (pitcher_info / pitcher_data), (game_summary / game_data), (analysis / pitch_analysis),
    modos ('game', 'season', 'range') y DataFrames Statcast.
    """
    p_info = pitcher_info or pitcher_data or {}
    g_data = game_summary or game_data or {}
    p_analysis = analysis or pitch_analysis or {}
    statcast_df = df if df is not None else df_statcast
    phase_arg = phase or kwargs.get("phase", "all")
    use_mexico = is_mexico or (branch == "mexico")
    use_lidom = is_lidom or (branch == "lidom") or (branch is None and not use_mexico and p_info.get("has_lidom", False))

    has_sc = (statcast_df is not None and not statcast_df.empty and len(statcast_df[statcast_df['release_speed'].notna()]) >= 5)
    force_pbp = (card_type == "pbp")
    force_sc = (card_type == "statcast")

    if use_mexico:
        raw_bytes = build_lidom_matplotlib_summary(
            pitcher_info=p_info,
            game_summary=g_data,
            analysis=p_analysis,
            season=season,
            dpi=dpi,
            mode=mode,
            start_date=start_date,
            end_date=end_date,
            game_logs=game_logs,
            phase=phase_arg,
            is_mexico=True,
        )
    elif use_lidom:
        if force_sc or (has_sc and not force_pbp):
            raw_bytes = build_nestico_pitching_summary(
                df=statcast_df,
                pitcher_info=p_info,
                mode=mode,
                season=season,
                start_date=start_date,
                end_date=end_date,
                game_summary=g_data,
                game_logs=game_logs,
                is_lidom=True,
                dpi=dpi,
            )
        else:
            raw_bytes = build_lidom_matplotlib_summary(
                pitcher_info=p_info,
                game_summary=g_data,
                analysis=p_analysis,
                season=season,
                dpi=dpi,
                mode=mode,
                start_date=start_date,
                end_date=end_date,
                game_logs=game_logs,
                phase=phase_arg,
                is_mexico=False,
            )
    else:
        if statcast_df is not None and not statcast_df.empty:
            df_to_use = statcast_df
        else:
            pitches = p_analysis.get("pitches", [])
            if pitches:
                df_to_use = pd.DataFrame(pitches)
                if 'pitch_name' in df_to_use.columns and 'pitch_type' not in df_to_use.columns:
                    rev_pitch = {v['name'].lower(): k for k, v in PITCH_COLOURS.items()}
                    df_to_use['pitch_type'] = df_to_use['pitch_name'].apply(lambda n: rev_pitch.get(str(n).lower(), 'FF'))
                if 'release_speed' not in df_to_use.columns:
                    df_to_use['release_speed'] = 93.0
                if 'pfx_x' not in df_to_use.columns:
                    df_to_use['pfx_x'] = df_to_use.get('hb', 0.0)
                if 'pfx_z' not in df_to_use.columns:
                    df_to_use['pfx_z'] = df_to_use.get('ivb', 0.0)
                if 'game_date' not in df_to_use.columns:
                    df_to_use['game_date'] = g_data.get('date', '2026-04-17')
                if 'p_throws' not in df_to_use.columns:
                    df_to_use['p_throws'] = p_info.get('throws', 'R')
                df_to_use['swing'] = True
                df_to_use['whiff'] = df_to_use.get('is_whiff', False)
                df_to_use['in_zone'] = True
                df_to_use['out_zone'] = False
                df_to_use['chase'] = False
            else:
                df_to_use = pd.DataFrame()

        raw_bytes = build_nestico_pitching_summary(
            df=df_to_use,
            pitcher_info=p_info,
            mode=mode,
            season=season,
            start_date=start_date,
            end_date=end_date,
            game_summary=g_data,
            game_logs=game_logs,
            is_lidom=False,
            dpi=dpi,
        )

    target_size = CANVAS_SIZE_LIDOM
    im = Image.open(io.BytesIO(raw_bytes))
    im_resized = im.resize(target_size, Image.Resampling.LANCZOS)
    out_buf = io.BytesIO()
    im_resized.save(out_buf, format="PNG", dpi=DPI)
    return out_buf.getvalue()
