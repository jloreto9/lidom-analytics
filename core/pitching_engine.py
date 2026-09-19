# core/pitching_engine.py
"""
pitching_engine.py
------------------
Motor analítico y de ingesta de datos para el Pitching Summary & Telemetría de LIDOM 360.
Soporta:
1. Búsqueda universal de lanzadores (MLB, Triple-A, MiLB, LIDOM, México LMB).
2. Detección automática de historial en las 6 franquicias de LIDOM (Licey, Águilas, Escogido, Gigantes, Estrellas, Toros).
3. Obtención de Game Logs (aperturas y relevos) con decisiones oficiales (W, L, SV, HLD, —) y conteos P-S.
4. Extracción pitcheo a pitcheo vía Baseball Savant Gamefeed y MLB Gameday Live Feed.
5. Cálculo de métricas Statcast completas (IVB, HB, Velo, Spin, CSW%, Whiff%, Zone%)
   y métricas PBP sabermétricas adaptadas para LIDOM y México (Workload, LI Tango RE24, Platoon splits).
6. Persistencia y caché local en .cache/lidom_pbp/ y .cache/statcast/ para consultas ultrarrápidas.
"""

import os
import json
import time
import socket
import urllib.parse
import urllib.request
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# Timeout global de socket (30s) para evitar bloqueos por bibliotecas de terceros (ej: pybaseball)
socket.setdefaulttimeout(30.0)

import streamlit as st

def cache_ttl(ttl_seconds: int = 3600):
    """Decorador de caché adaptado a Streamlit."""
    return st.cache_data(ttl=ttl_seconds, show_spinner=False)

from core.teams import TEAMS, get_all_teams, get_team_by_id, get_team_by_abbrev, get_team_color, get_team_logo
from core.wpa_engine import calculate_leverage_index, get_base_state_index

LIDOM_TEAMS = {t["id"]: t["name"] for t in TEAMS.values()}
LIDOM_ABBR = {t["id"]: t["abbrev"] for t in TEAMS.values()}

LIDOM_LEAGUE_ID = 131
LIDOM_SPORT_ID = 17
MEXICO_SPORT_ID = 23
MLB_SPORT_ID = 1
AAA_SPORT_ID = 11

CACHE_PBP_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ".cache",
    "lidom_pbp"
)
os.makedirs(CACHE_PBP_DIR, exist_ok=True)

CACHE_STATCAST_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ".cache",
    "statcast"
)
os.makedirs(CACHE_STATCAST_DIR, exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
}


def _safe_int(val: Any) -> int:
    """Convierte cualquier valor a int de forma defensiva evitando TypeErrors."""
    try:
        if val is None:
            return 0
        return int(float(val))
    except (ValueError, TypeError):
        return 0


def _safe_float(val: Any) -> float:
    """Convierte cualquier valor a float de forma defensiva."""
    try:
        if val is None:
            return 0.0
        return float(val)
    except (ValueError, TypeError):
        return 0.0


# ── 1. Búsqueda Universal de Lanzadores y Resolución por ID ───────────────────

@cache_ttl(ttl_seconds=7200)
def _get_known_lidom_pitcher_ids() -> set:
    """Obtiene los IDs de lanzadores icónicos o con registro en LIDOM."""
    lidom_ids = {
        491624,  # César Valdez (Licey)
        467657,  # Esmil Rogers (Licey/Toros)
        467655,  # Radhamés Liz (Estrellas/Licey/Toros)
        448855,  # Raúl Valdés (Toros)
        446454,  # Jairo Asencio (Licey)
        628711,  # Enny Romero (Escogido/Águilas)
        642547,  # Framber Valdez (Águilas/Astros)
        661563,  # Luis Gil (Licey/Yankees)
        642547,  # Freddy Peralta (Toros/Brewers)
        656302,  # Cristopher Sánchez (Toros/Phillies)
        678394,  # Brayan Bello (Toros/Red Sox)
        666374,  # Ronel Blanco (Estrellas/Astros)
        622491,  # Luis Castillo (Águilas/Mariners)
        622075,  # Erick Leal (LIDOM/México/LVBP)
        457918,  # Junior Guerra
        544150,  # Albert Suárez
        518586,  # Jhoulys Chacín
    }
    # Cargar de archivos locales en .cache si existen
    cache_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    if os.path.exists(cache_dir):
        for f in os.listdir(cache_dir):
            if f.startswith("pitching_stats_") and f.endswith(".json"):
                try:
                    p = os.path.join(cache_dir, f)
                    with open(p, "r", encoding="utf-8") as fp:
                        s_data = json.load(fp)
                        for row in s_data:
                            pid = row.get("player_id") or row.get("id")
                            if pid:
                                lidom_ids.add(int(pid))
                except Exception:
                    pass
    return lidom_ids


@cache_ttl(ttl_seconds=3600)
def _get_lidom_pitcher_metadata(pitcher_id: int) -> Dict[str, Any]:
    """Consulta metadatos de un lanzador en LIDOM y retorna su franquicia."""
    known_ids = _get_known_lidom_pitcher_ids()
    is_known = pitcher_id in known_ids

    # 1. Consultar Supabase si está disponible
    try:
        from core.supabase_client import get_supabase_credentials
        from supabase import create_client
        url, key = get_supabase_credentials()
        if url and key:
            sb = create_client(url, key)
            res = sb.table('lidom_pitching_stats').select('team_id, lidom_players(full_name)').eq('player_id', pitcher_id).limit(1).execute()
            if res.data:
                tid = int(res.data[0].get('team_id') or 0)
                p_data = res.data[0].get('lidom_players') or {}
                p_name = p_data.get('full_name', '') if isinstance(p_data, dict) else ''
                t_name = LIDOM_TEAMS.get(tid, "Equipo LIDOM")
                t_abbr = LIDOM_ABBR.get(tid, "LID")
                return {
                    "has_lidom": True,
                    "team_id": tid,
                    "team_name": t_name,
                    "team_abbr": t_abbr,
                    "name": p_name,
                }
    except Exception:
        pass

    # 2. Consultar data local en data/
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    if os.path.exists(data_dir):
        for f in os.listdir(data_dir):
            if f.startswith("pitching_stats_") and f.endswith(".json"):
                try:
                    p = os.path.join(data_dir, f)
                    with open(p, "r", encoding="utf-8") as fp:
                        s_data = json.load(fp)
                        for row in s_data:
                            if row.get("player_id") == pitcher_id or row.get("id") == pitcher_id:
                                tid = int(row.get("team_id") or 0)
                                return {
                                    "has_lidom": True,
                                    "team_id": tid,
                                    "team_name": LIDOM_TEAMS.get(tid, "Equipo LIDOM"),
                                    "team_abbr": LIDOM_ABBR.get(tid, "LID"),
                                    "name": row.get("name", ""),
                                }
                except Exception:
                    pass

    return {
        "has_lidom": is_known,
        "team_id": 672 if is_known else 0,
        "team_name": "Tigres del Licey" if is_known else "Lanzador",
        "team_abbr": "LIC" if is_known else "MLB",
        "name": "",
    }


@cache_ttl(ttl_seconds=3600)
def get_pitcher_by_id(pitcher_id: int, *args, **kwargs) -> Optional[Dict[str, Any]]:
    """Obtiene los metadatos completos de un lanzador a partir de su ID."""
    url = f"https://statsapi.mlb.com/api/v1/people/{pitcher_id}?hydrate=currentTeam"
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            people = data.get("people", [])
            if not people:
                return None
            p = people[0]
            curr_team = p.get("currentTeam", {})
            mlb_team_name = curr_team.get("name", "Agente Libre")
            mlb_team_id = curr_team.get("id", 0)

            # Extraer metadata de LIDOM
            meta = _get_lidom_pitcher_metadata(pitcher_id)

            display_team = meta["team_name"] if meta["has_lidom"] else mlb_team_name
            display_abbr = meta["team_abbr"] if meta["has_lidom"] else (curr_team.get("abbreviation") or "MLB")

            return {
                "id": p.get("id"),
                "name": p.get("fullName"),
                "pitch_hand": p.get("pitchHand", {}).get("code", "R"),
                "bat_side": p.get("batSide", {}).get("code", "R"),
                "height": p.get("height", ""),
                "weight": p.get("weight", ""),
                "age": p.get("currentAge", 0),
                "birth_date": p.get("birthDate", ""),
                "team_id": meta["team_id"] if meta["has_lidom"] else mlb_team_id,
                "team_name": display_team,
                "team_abbr": display_abbr,
                "mlb_team_name": mlb_team_name,
                "photo_url": f"https://img.mlbstatic.com/mlb-photos/player/silo/180x180/{p.get('id')}.png",
                "has_lidom": meta["has_lidom"],
            }
    except Exception:
        return None


@cache_ttl(ttl_seconds=1800)
def search_pitchers(query: str, sport_ids: str = "1,11,17,23") -> List[Dict[str, Any]]:
    """
    Búsqueda universal de lanzadores por nombre (MLB, MiLB, LIDOM, México LMB).
    """
    if not query or len(query.strip()) < 2:
        return []

    q_clean = query.strip()
    encoded = urllib.parse.quote(q_clean)
    url = f"https://statsapi.mlb.com/api/v1/people/search?names={encoded}&sportIds={sport_ids}&active=true"

    results: List[Dict[str, Any]] = []
    seen_ids = set()

    # Prioridad: lanzadores conocidos
    for p_id in _get_known_lidom_pitcher_ids():
        p_obj = get_pitcher_by_id(p_id)
        if p_obj and q_clean.lower() in p_obj["name"].lower():
            results.append(p_obj)
            seen_ids.add(p_id)

    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            people = data.get("people", [])
            for p in people:
                p_id = p.get("id")
                if p_id in seen_ids:
                    continue
                pos = p.get("primaryPosition", {}).get("abbreviation", "")
                if pos != "P":
                    continue

                curr_team = p.get("currentTeam", {})
                mlb_team_name = curr_team.get("name", "Agente Libre")
                mlb_team_id = curr_team.get("id", 0)

                meta = _get_lidom_pitcher_metadata(p_id)
                display_team = meta["team_name"] if meta["has_lidom"] else mlb_team_name
                display_abbr = meta["team_abbr"] if meta["has_lidom"] else (curr_team.get("abbreviation") or "MLB")

                results.append({
                    "id": p_id,
                    "name": p.get("fullName"),
                    "pitch_hand": p.get("pitchHand", {}).get("code", "R"),
                    "bat_side": p.get("batSide", {}).get("code", "R"),
                    "height": p.get("height", ""),
                    "weight": p.get("weight", ""),
                    "age": p.get("currentAge", 0),
                    "birth_date": p.get("birthDate", ""),
                    "team_id": meta["team_id"] if meta["has_lidom"] else mlb_team_id,
                    "team_name": display_team,
                    "team_abbr": display_abbr,
                    "mlb_team_name": mlb_team_name,
                    "photo_url": f"https://img.mlbstatic.com/mlb-photos/player/silo/180x180/{p_id}.png",
                    "has_lidom": meta["has_lidom"],
                })
                seen_ids.add(p_id)
    except Exception:
        pass

    # Ordenar priorizando lanzadores con historial en LIDOM
    results.sort(key=lambda x: (not x.get("has_lidom", False), x.get("name", "")))
    return results[:25]


# ── 2. Obtención de Game Logs (Aperturas y Relevos) ───────────────────────────

def _parse_decision(stat: Optional[dict]) -> str:
    """Extrae la decisión W, L, SV o HLD de una salida de manera defensiva."""
    if not isinstance(stat, dict):
        return ""
    if _safe_int(stat.get("wins")) > 0:
        return "W"
    if _safe_int(stat.get("losses")) > 0:
        return "L"
    if _safe_int(stat.get("saves")) > 0:
        return "SV"
    if _safe_int(stat.get("holds")) > 0:
        return "HLD"
    return ""


@cache_ttl(ttl_seconds=1800)
def get_pitcher_game_logs(
    pitcher_id: int,
    season: int = 2026,
    is_lidom: bool = True,
    branch: str = "lidom",
    phase: str = "all",
    *args,
    **kwargs
) -> List[Dict[str, Any]]:
    """
    Obtiene las salidas individuales de un lanzador con sus estadísticas y decisiones oficiales.
    Soporta ramas: 'lidom', 'mexico', 'mlb'.
    """
    if branch == "mexico":
        return _get_mexico_pitcher_game_logs(pitcher_id, season, phase=phase)
    if is_lidom or branch == "lidom":
        return _get_lidom_pitcher_game_logs(pitcher_id, season, phase=phase)

    # MLB y MiLB vía MLB Stats API
    url = (
        f"https://statsapi.mlb.com/api/v1/people/{pitcher_id}/stats"
        f"?stats=gameLog&group=pitching&season={season}&sportIds=1,11,12"
    )
    logs: List[Dict[str, Any]] = []
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            stats = data.get("stats", [])
            if stats:
                splits = stats[0].get("splits", [])
                for s in splits:
                    game = s.get("game", {})
                    stat = s.get("stat", {})
                    opp = s.get("opponent", {}).get("name", "Rival")
                    date_str = str(s.get("date") or "")
                    gpk = game.get("gamePk", 0)
                    is_start = _safe_int(stat.get("gamesStarted")) > 0
                    g_type = s.get("gameType") or "R"

                    if phase and phase != "all" and g_type != phase:
                        continue

                    logs.append({
                        "game_pk": gpk,
                        "date": date_str,
                        "opponent": opp,
                        "is_starter": is_start,
                        "role": "Abridor" if is_start else "Relevista",
                        "game_type": g_type,
                        "phase": g_type,
                        "ip": stat.get("inningsPitched", "0.0"),
                        "h": stat.get("hits", 0),
                        "r": stat.get("runs", 0),
                        "er": stat.get("earnedRuns", 0),
                        "bb": stat.get("baseOnBalls", 0),
                        "so": stat.get("strikeOuts", 0),
                        "hr": stat.get("homeRuns", 0),
                        "pitches": stat.get("numberOfPitches", 0),
                        "strikes": stat.get("strikes", 0),
                        "era": stat.get("era", "0.00"),
                        "decision": _parse_decision(stat),
                        "league": "MLB" if s.get("sport", {}).get("id") == 1 else "MiLB",
                    })
    except Exception:
        pass

    logs.sort(key=lambda x: str(x.get("date") or ""), reverse=True)
    return logs


def _get_lidom_pitcher_game_logs(pitcher_id: int, season: int, phase: str = "all") -> List[Dict[str, Any]]:
    """Obtiene salidas de LIDOM desde Supabase o MLB Stats API (sportId=17, leagueId=131)."""
    logs: List[Dict[str, Any]] = []

    # 1. Intentar consultar MLB Stats API oficial (sportId=17, leagueId=131)
    try:
        api_url = (
            f"https://statsapi.mlb.com/api/v1/people/{pitcher_id}/stats"
            f"?stats=gameLog&group=pitching&season={season}&sportId=17&leagueId=131&gameType=R,F,D,L,W,P"
        )
        req = urllib.request.Request(api_url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            stats = data.get("stats", [])
            if stats:
                splits = stats[0].get("splits", [])
                for s in splits:
                    game = s.get("game", {})
                    stat = s.get("stat", {})
                    opp_obj = s.get("opponent", {})
                    opp_id = opp_obj.get("id", 0)
                    opp = opp_obj.get("name") or LIDOM_TEAMS.get(opp_id, "Rival")
                    date_str = str(s.get("date") or "")
                    gpk = game.get("gamePk", 0)
                    gt = s.get("gameType") or "R"

                    if phase and phase != "all" and gt != phase:
                        continue

                    is_start = _safe_int(stat.get("gamesStarted")) > 0
                    p_cnt = int(stat.get("numberOfPitches", 0) or 0)
                    s_cnt = int(stat.get("strikes", 0) or 0)
                    dec = _parse_decision(stat)

                    logs.append({
                        "game_pk": gpk,
                        "date": date_str,
                        "opponent": opp,
                        "is_starter": is_start,
                        "role": "Abridor" if is_start else "Relevista",
                        "game_type": gt,
                        "phase": gt,
                        "ip": stat.get("inningsPitched", "0.0"),
                        "h": stat.get("hits", 0),
                        "r": stat.get("runs", 0),
                        "er": stat.get("earnedRuns", 0),
                        "bb": stat.get("baseOnBalls", 0),
                        "so": stat.get("strikeOuts", 0),
                        "hr": stat.get("homeRuns", 0),
                        "pitches": p_cnt,
                        "strikes": s_cnt,
                        "era": stat.get("era", "0.00"),
                        "decision": dec,
                        "league": "LIDOM",
                    })
                if logs:
                    logs.sort(key=lambda x: str(x.get("date") or ""), reverse=True)
                    return logs
    except Exception:
        pass

    # 2. Fallback a Supabase si está disponible
    try:
        from core.supabase_client import get_supabase_credentials
        from supabase import create_client
        url, key = get_supabase_credentials()
        if url and key:
            sb = create_client(url, key)
            query = sb.table('lidom_pitching_stats').select(
                'game_id, innings_pitched, hits, runs, earned_runs, walks, strikeouts, home_runs, pitches_thrown, strikes, era, wins, losses, saves, lidom_games(game_date, game_type, home_team_id, away_team_id)'
            ).eq('player_id', pitcher_id)
            res = query.execute()
            if res.data:
                for row in res.data:
                    game = row.get('lidom_games') or {}
                    g_date = game.get('game_date', '')
                    g_type = game.get('game_type', 'R')
                    if phase and phase != "all" and g_type != phase:
                        continue
                    opp_id = game.get('away_team_id')
                    opp_name = LIDOM_TEAMS.get(opp_id, "Rival LIDOM")
                    dec = "W" if _safe_int(row.get("wins")) > 0 else ("L" if _safe_int(row.get("losses")) > 0 else ("SV" if _safe_int(row.get("saves")) > 0 else ""))

                    logs.append({
                        "game_pk": row.get("game_id", 0),
                        "date": g_date,
                        "opponent": opp_name,
                        "is_starter": True,
                        "role": "Abridor",
                        "game_type": g_type,
                        "phase": g_type,
                        "ip": str(row.get("innings_pitched", "0.0")),
                        "h": row.get("hits", 0),
                        "r": row.get("runs", 0),
                        "er": row.get("earned_runs", 0),
                        "bb": row.get("walks", 0),
                        "so": row.get("strikeouts", 0),
                        "hr": row.get("home_runs", 0),
                        "pitches": row.get("pitches_thrown", 0),
                        "strikes": row.get("strikes", 0),
                        "era": str(row.get("era", "0.00")),
                        "decision": dec,
                        "league": "LIDOM",
                    })
                if logs:
                    logs.sort(key=lambda x: str(x.get("date") or ""), reverse=True)
                    return logs
    except Exception:
        pass

    return logs


def _get_mexico_pitcher_game_logs(pitcher_id: int, season: int, phase: str = "all") -> List[Dict[str, Any]]:
    """
    Obtiene las salidas del lanzador en la Liga Mexicana de Béisbol (LMB - Verano).
    sportId=23, leagueId=125 vía MLB Stats API.
    """
    url = (
        f"https://statsapi.mlb.com/api/v1/people/{pitcher_id}/stats"
        f"?stats=gameLog&group=pitching&season={season}&sportId=23&gameType=R,F,D,L,W,P"
    )
    logs: List[Dict[str, Any]] = []
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            stats = data.get("stats", [])
            if stats:
                splits = stats[0].get("splits", [])
                seen_pks = set()
                for s in splits:
                    game = s.get("game", {})
                    stat = s.get("stat", {})
                    team = s.get("team", {}).get("name", "Liga Mexicana")
                    opp = s.get("opponent", {}).get("name", "Rival")
                    date_str = str(s.get("date") or "")
                    gpk = game.get("gamePk", 0)
                    g_type = s.get("gameType") or "R"

                    dedup_key = gpk if gpk else date_str
                    if dedup_key and dedup_key in seen_pks:
                        continue

                    if phase and phase != "all":
                        if phase == "R" and g_type != "R":
                            continue
                        elif phase in ("P", "L", "F") and g_type not in ("P", "L", "F", "D", "W") and g_type != phase:
                            continue

                    if dedup_key:
                        seen_pks.add(dedup_key)

                    is_start = _safe_int(stat.get("gamesStarted")) > 0
                    p_cnt = int(stat.get("numberOfPitches", 0) or 0)
                    s_cnt = int(stat.get("strikes", 0) or 0)
                    dec = _parse_decision(stat)

                    logs.append({
                        "game_pk": gpk,
                        "date": date_str,
                        "opponent": opp,
                        "team": team,
                        "is_starter": is_start,
                        "role": "Abridor" if is_start else "Relevista",
                        "game_type": g_type,
                        "phase": g_type,
                        "ip": stat.get("inningsPitched", "0.0"),
                        "h": stat.get("hits", 0),
                        "r": stat.get("runs", 0),
                        "er": stat.get("earnedRuns", 0),
                        "bb": stat.get("baseOnBalls", 0),
                        "so": stat.get("strikeOuts", 0),
                        "hr": stat.get("homeRuns", 0),
                        "pitches": p_cnt,
                        "strikes": s_cnt,
                        "era": stat.get("era", "0.00"),
                        "decision": dec,
                        "league": "México",
                    })
    except Exception:
        pass

    logs.sort(key=lambda x: str(x.get("date") or ""), reverse=True)
    return logs


# ── 3. Extracción y Parseo de Pitcheos (Savant & Gameday) ──────────────────────

def _fetch_game_payload(game_pk: int, is_lidom: bool = False) -> Dict[str, Any]:
    """Descarga el payload de pitcheos con caché en disco .cache/lidom_pbp/{game_pk}.json."""
    cache_file = os.path.join(CACHE_PBP_DIR, f"{game_pk}.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as fp:
                return json.load(fp)
        except Exception:
            pass

    payload: Dict[str, Any] = {}

    if not is_lidom:
        savant_url = f"https://baseballsavant.mlb.com/gf?game_pk={game_pk}"
        try:
            req = urllib.request.Request(savant_url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if "team_home" in data or "team_away" in data:
                    payload = {"source": "savant", "data": data}
        except Exception:
            pass

    if not payload:
        live_url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"
        try:
            req = urllib.request.Request(live_url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                payload = {"source": "gameday", "data": data}
        except Exception:
            pass

    if payload:
        try:
            with open(cache_file, "w", encoding="utf-8") as fp:
                json.dump(payload, fp)
        except Exception:
            pass

    return payload


def _parse_gameday_pitches(data: Dict[str, Any], pitcher_id: int) -> List[Dict[str, Any]]:
    """Parsea pitcheos desde el feed live de MLB Gameday para un lanzador."""
    pitches: List[Dict[str, Any]] = []
    live_data = data.get("liveData", {})
    plays = live_data.get("plays", {}).get("allPlays", [])

    for play in plays:
        matchup = play.get("matchup", {})
        p_id = matchup.get("pitcher", {}).get("id")
        if p_id != pitcher_id:
            continue

        batter_side = matchup.get("batSide", {}).get("code", "R")
        about = play.get("about", {})
        inning = about.get("inning", 1)
        is_bottom = (about.get("halfInning") == "bottom")

        play_events = play.get("playEvents", [])
        for ev in play_events:
            if not ev.get("isPitch"):
                continue

            pitch_data = ev.get("pitchData", {})
            coords = pitch_data.get("coordinates", {})
            details = ev.get("details", {})

            p_name = details.get("type", {}).get("description") or "Pitch"
            speed = pitch_data.get("startSpeed")
            spin = pitch_data.get("breaks", {}).get("spinRate")
            pfx_x = pitch_data.get("breaks", {}).get("breakHorizontal")
            pfx_z = pitch_data.get("breaks", {}).get("breakVerticalInduced")
            px = coords.get("pX")
            pz = coords.get("pZ")

            desc = details.get("description", "").lower()
            is_whiff = "swinging_strike" in desc or "missed_bunt" in desc
            is_called = "called_strike" in desc
            is_foul = "foul" in desc
            is_in_play = "in_play" in desc or "hit_into_play" in desc
            is_ball = "ball" in desc

            in_zone = details.get("isInPlay", False) or is_called
            if px is not None and pz is not None:
                in_zone = (-0.85 <= float(px) <= 0.85) and (1.5 <= float(pz) <= 3.5)

            # Leverage Index
            count = ev.get("count", {})
            outs = count.get("outs", 0)
            base_idx = 0
            li = calculate_leverage_index(inning, is_bottom, outs, base_idx, 0)

            pitches.append({
                "pitch_name": p_name,
                "speed": float(speed) if speed else None,
                "spin": int(spin) if spin else None,
                "ivb": float(pfx_z) if pfx_z else None,
                "hb": float(pfx_x) if pfx_x else None,
                "plate_x": float(px) if px else 0.0,
                "plate_z": float(pz) if pz else 2.5,
                "is_whiff": is_whiff,
                "is_called": is_called,
                "is_foul": is_foul,
                "is_in_play": is_in_play,
                "is_ball": is_ball,
                "is_zone": in_zone,
                "batter_side": batter_side,
                "inning": inning,
                "leverage_index": li,
            })
    return pitches


def _parse_savant_pitches(data: Dict[str, Any], pitcher_id: int) -> List[Dict[str, Any]]:
    """Parsea pitcheos desde el payload de Baseball Savant."""
    pitches: List[Dict[str, Any]] = []
    team_home = data.get("team_home", [])
    team_away = data.get("team_away", [])
    all_events = team_home + team_away

    for ev in all_events:
        p_id = ev.get("pitcher")
        if p_id != pitcher_id:
            continue

        p_name = ev.get("pitch_name") or "Pitch"
        speed = ev.get("release_speed")
        spin = ev.get("release_spin_rate")
        pfx_x = ev.get("pfx_x")
        pfx_z = ev.get("pfx_z")
        px = ev.get("plate_x")
        pz = ev.get("plate_z")

        ivb = float(pfx_z) * 12.0 if pfx_z is not None else None
        hb = float(pfx_x) * 12.0 if pfx_x is not None else None

        desc = str(ev.get("description", "")).lower()
        is_whiff = "swinging_strike" in desc or "missed_bunt" in desc
        is_called = "called_strike" in desc
        is_foul = "foul" in desc
        is_in_play = "hit_into_play" in desc
        is_ball = "ball" in desc

        in_zone = bool(ev.get("zone", 0) in range(1, 10))

        pitches.append({
            "pitch_name": p_name,
            "speed": float(speed) if speed else None,
            "spin": int(spin) if spin else None,
            "ivb": ivb,
            "hb": hb,
            "plate_x": float(px) if px else 0.0,
            "plate_z": float(pz) if pz else 2.5,
            "is_whiff": is_whiff,
            "is_called": is_called,
            "is_foul": is_foul,
            "is_in_play": is_in_play,
            "is_ball": is_ball,
            "is_zone": in_zone,
            "batter_side": ev.get("stand", "R"),
            "inning": ev.get("inning", 1),
            "leverage_index": 1.0,
        })
    return pitches


@cache_ttl(ttl_seconds=1800)
def get_game_pitch_data(game_pk: int, pitcher_id: int, is_lidom: bool = False) -> Dict[str, Any]:
    """Extrae, limpia y calcula toda la analítica de pitcheos de una salida dada."""
    raw = _fetch_game_payload(game_pk, is_lidom=is_lidom)
    if not raw:
        return {"error": f"No se encontraron datos para el juego {game_pk}"}

    source = raw.get("source")
    data = raw.get("data", {})

    if source == "savant":
        parsed_pitches = _parse_savant_pitches(data, pitcher_id)
    else:
        parsed_pitches = _parse_gameday_pitches(data, pitcher_id)

    if not parsed_pitches:
        return {
            "game_pk": game_pk,
            "pitcher_id": pitcher_id,
            "total_pitches": 0,
            "pitches": [],
            "statcast_table": [],
            "pbp_table": [],
            "pbp_kpis": {},
            "innings_workload": [],
            "splits_platoon": {},
            "has_statcast": False,
        }

    has_statcast = any(
        p.get("speed") is not None and p.get("ivb") is not None
        for p in parsed_pitches
    )

    statcast_table = _build_statcast_table(parsed_pitches) if has_statcast else []
    pbp_table, pbp_kpis = _build_pbp_summary(parsed_pitches)
    innings_workload = _build_inning_workload(parsed_pitches)
    splits_platoon = _build_platoon_splits(parsed_pitches)

    return {
        "game_pk": game_pk,
        "pitcher_id": pitcher_id,
        "total_pitches": len(parsed_pitches),
        "pitches": parsed_pitches,
        "statcast_table": statcast_table,
        "pbp_table": pbp_table,
        "pbp_kpis": pbp_kpis,
        "innings_workload": innings_workload,
        "splits_platoon": splits_platoon,
        "has_statcast": has_statcast,
    }


def _build_statcast_table(pitches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Construye la tabla resumen de lanzamientos para repertorio Statcast."""
    by_type: Dict[str, List[Dict[str, Any]]] = {}
    for p in pitches:
        p_name = p.get("pitch_name") or "Fastball"
        by_type.setdefault(p_name, []).append(p)

    tot_pitches = len(pitches)
    rows = []
    for p_name, p_list in by_type.items():
        cnt = len(p_list)
        pct = (cnt / tot_pitches * 100) if tot_pitches > 0 else 0.0

        speeds = [p["speed"] for p in p_list if p.get("speed")]
        spins = [p["spin"] for p in p_list if p.get("spin")]
        ivbs = [p["ivb"] for p in p_list if p.get("ivb")]
        hbs = [p["hb"] for p in p_list if p.get("hb")]

        swings = sum(1 for p in p_list if p.get("is_whiff") or p.get("is_foul") or p.get("is_in_play"))
        whiffs = sum(1 for p in p_list if p.get("is_whiff"))
        called = sum(1 for p in p_list if p.get("is_called"))
        csw = whiffs + called

        whiff_pct = (whiffs / swings * 100) if swings > 0 else 0.0
        csw_pct = (csw / cnt * 100) if cnt > 0 else 0.0
        zone_pct = (sum(1 for p in p_list if p.get("is_zone")) / cnt * 100) if cnt > 0 else 0.0

        rows.append({
            "name": p_name,
            "count": cnt,
            "usage": round(pct, 1),
            "velo": round(sum(speeds) / len(speeds), 1) if speeds else 0.0,
            "spin": int(sum(spins) / len(spins)) if spins else 0,
            "ivb": round(sum(ivbs) / len(ivbs), 1) if ivbs else 0.0,
            "hb": round(sum(hbs) / len(hbs), 1) if hbs else 0.0,
            "whiff_pct": round(whiff_pct, 1),
            "csw_pct": round(csw_pct, 1),
            "zone_pct": round(zone_pct, 1),
        })

    rows.sort(key=lambda x: x["count"], reverse=True)
    return rows


def _build_pbp_summary(pitches: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Construye resumen de destinos de pitcheos para ligas PBP (LIDOM / México)."""
    tot = len(pitches)
    if tot == 0:
        return [], {}

    strikes = sum(1 for p in pitches if p.get("is_whiff") or p.get("is_called") or p.get("is_foul") or p.get("is_in_play"))
    balls = sum(1 for p in pitches if p.get("is_ball"))
    whiffs = sum(1 for p in pitches if p.get("is_whiff"))
    called = sum(1 for p in pitches if p.get("is_called"))
    fouls = sum(1 for p in pitches if p.get("is_foul"))
    in_play = sum(1 for p in pitches if p.get("is_in_play"))

    swings = whiffs + fouls + in_play
    csw = whiffs + called

    kpis = {
        "strikes": strikes,
        "balls": balls,
        "strike_pct": f"{(strikes / tot * 100):.1f}%",
        "whiff_pct": f"{(whiffs / swings * 100):.1f}%" if swings > 0 else "0.0%",
        "csw_pct": f"{(csw / tot * 100):.1f}%",
        "in_play": in_play,
        "fouls": fouls,
        "called_strikes": called,
    }

    table = [
        {"Destino": "Abanicado (Whiff)", "Conteo": whiffs, "% Pitcheos": f"{(whiffs/tot*100):.1f}%"},
        {"Destino": "Strike Cantado", "Conteo": called, "% Pitcheos": f"{(called/tot*100):.1f}%"},
        {"Destino": "Foul Ball", "Conteo": fouls, "% Pitcheos": f"{(fouls/tot*100):.1f}%"},
        {"Destino": "En Juego", "Conteo": in_play, "% Pitcheos": f"{(in_play/tot*100):.1f}%"},
        {"Destino": "Bola Mala", "Conteo": balls, "% Pitcheos": f"{(balls/tot*100):.1f}%"},
    ]
    return table, kpis


def _build_inning_workload(pitches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Calcula conteo de pitcheos, strikes y apalancamiento promedio por entrada."""
    by_inn: Dict[int, List[Dict[str, Any]]] = {}
    for p in pitches:
        inn = p.get("inning", 1)
        by_inn.setdefault(inn, []).append(p)

    workload = []
    for inn in sorted(by_inn.keys()):
        p_list = by_inn[inn]
        tot = len(p_list)
        stks = sum(1 for p in p_list if not p.get("is_ball"))
        lis = [p.get("leverage_index", 1.0) for p in p_list]
        avg_li = sum(lis) / len(lis) if lis else 1.0

        workload.append({
            "inning": inn,
            "pitches": tot,
            "strikes": stks,
            "balls": tot - stks,
            "avg_li": round(avg_li, 2),
        })
    return workload


def _build_platoon_splits(pitches: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calcula métricas de control divididas por bateadores zurdos (LHB) y derechos (RHB)."""
    lhb = [p for p in pitches if p.get("batter_side") == "L"]
    rhb = [p for p in pitches if p.get("batter_side") == "R"]

    def _calc_metrics(p_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        tot = len(p_list)
        if tot == 0:
            return {"pitches": 0, "strike_pct": "0.0%", "whiff_pct": "0.0%", "csw_pct": "0.0%"}
        stks = sum(1 for p in p_list if not p.get("is_ball"))
        swings = sum(1 for p in p_list if p.get("is_whiff") or p.get("is_foul") or p.get("is_in_play"))
        whiffs = sum(1 for p in p_list if p.get("is_whiff"))
        csw = whiffs + sum(1 for p in p_list if p.get("is_called"))
        return {
            "pitches": tot,
            "strike_pct": f"{(stks / tot * 100):.1f}%",
            "whiff_pct": f"{(whiffs / swings * 100):.1f}%" if swings > 0 else "0.0%",
            "csw_pct": f"{(csw / tot * 100):.1f}%",
        }

    return {"LHB": _calc_metrics(lhb), "RHB": _calc_metrics(rhb)}


# ── 4. Descarga y Análisis Statcast de Temporada Completa ───────────────────────

PITCH_CODE_TO_NAME: Dict[str, str] = {
    "FF": "4-Seam Fastball",
    "FA": "Fastball",
    "SI": "Sinker",
    "FC": "Cutter",
    "CH": "Changeup",
    "FS": "Splitter",
    "FO": "Forkball",
    "SL": "Slider",
    "ST": "Sweeper",
    "SV": "Slurve",
    "KC": "Knuckle Curve",
    "CU": "Curveball",
    "CS": "Slow Curve",
    "EP": "Eephus",
    "KN": "Knuckleball",
}


@cache_ttl(ttl_seconds=3600)
def get_lidom_pitcher_statcast_df(
    pitcher_id: int,
    season: int = 2024,
    mode: str = "season",
    game_pk: Optional[int] = None,
    phase: str = "all",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> pd.DataFrame:
    """Extrae lanzamientos con telemetría Statcast/TrackMan para LIDOM directamente desde la API oficial de MLB."""
    cache_name = f"lidom_sc_{pitcher_id}_{season}_{mode}_{phase}"
    if mode == "game" and game_pk:
        cache_name += f"_{game_pk}"
    elif mode == "range" and start_date and end_date:
        cache_name += f"_{start_date}_{end_date}"
    cache_path = os.path.join(CACHE_STATCAST_DIR, f"{cache_name}.parquet")

    if os.path.exists(cache_path):
        try:
            return pd.read_parquet(cache_path)
        except Exception:
            pass

    logs = get_pitcher_game_logs(pitcher_id, season=season, branch="lidom", phase=phase)
    if not logs:
        return pd.DataFrame()

    if mode == "game" and game_pk:
        target_logs = [g for g in logs if str(g.get("game_pk")) == str(game_pk)]
    elif mode == "range" and start_date and end_date:
        target_logs = [g for g in logs if start_date <= str(g.get("date", "")) <= end_date]
    else:
        target_logs = logs

    if not target_logs:
        return pd.DataFrame()

    def _fetch_game_pitches(g: Dict[str, Any]) -> List[Dict[str, Any]]:
        pk = g.get("game_pk")
        date_str = str(g.get("date", ""))
        furl = f"https://statsapi.mlb.com/api/v1.1/game/{pk}/feed/live"
        req = urllib.request.Request(furl, headers=HEADERS)
        game_pitches = []
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                fdata = json.loads(resp.read().decode("utf-8"))
            plays = fdata.get("liveData", {}).get("plays", {}).get("allPlays", [])
            for play in plays:
                matchup = play.get("matchup", {})
                if matchup.get("pitcher", {}).get("id") == pitcher_id:
                    stand = matchup.get("batSide", {}).get("code", "R")
                    p_throws = matchup.get("pitchHand", {}).get("code", "R")
                    for pe in play.get("playEvents", []):
                        if pe.get("isPitch"):
                            pdata = pe.get("pitchData", {})
                            details = pe.get("details", {})
                            coords = pdata.get("coordinates", {})
                            breaks = pdata.get("breaks", {})
                            speed = pdata.get("startSpeed")
                            if speed is not None:
                                ptype_obj = details.get("type", {})
                                p_code = ptype_obj.get("code") or "FF"
                                p_name = ptype_obj.get("description") or PITCH_CODE_TO_NAME.get(p_code, "4-Seam Fastball")
                                ivb = breaks.get("breakVerticalInduced")
                                if ivb is None and coords.get("pfxZ") is not None:
                                    ivb = float(coords.get("pfxZ")) * 12.0
                                hb = breaks.get("breakHorizontal")
                                if hb is None and coords.get("pfxX") is not None:
                                    hb = float(coords.get("pfxX")) * 12.0

                                desc_clean = details.get("description", "").lower()
                                code_val = details.get("code", "")
                                is_whiff = ("swinging" in desc_clean or "missed" in desc_clean or code_val == "S" or "whiff" in desc_clean)
                                is_called = ("called" in desc_clean or code_val == "C")
                                is_foul = ("foul" in desc_clean or code_val in ("F", "T", "O"))
                                is_in_play = ("in play" in desc_clean or "hit_into_play" in desc_clean or code_val in ("X", "D", "E"))
                                is_swing = is_whiff or is_foul or is_in_play
                                zone_val = int(pdata.get("zone", 0)) if pdata.get("zone") is not None else 0
                                in_zone = zone_val in range(1, 10)

                                px = coords.get("pX")
                                pz = coords.get("pZ")

                                game_pitches.append({
                                    "game_pk": pk,
                                    "game_date": date_str,
                                    "pitch_type": p_code,
                                    "pitch_name": p_name,
                                    "release_speed": float(speed),
                                    "release_spin_rate": float(breaks.get("spinRate")) if breaks.get("spinRate") is not None else 2150.0,
                                    "release_extension": float(pdata.get("extension")) if pdata.get("extension") is not None else 6.0,
                                    "release_pos_x": float(coords.get("x0")) if coords.get("x0") is not None else np.nan,
                                    "release_pos_z": float(coords.get("z0")) if coords.get("z0") is not None else np.nan,
                                    "pfx_x": float(hb) if hb is not None else 0.0,
                                    "pfx_z": float(ivb) if ivb is not None else 0.0,
                                    "plate_x": float(px) if px is not None else 0.0,
                                    "plate_z": float(pz) if pz is not None else 2.5,
                                    "zone": zone_val,
                                    "sz_top": float(pdata.get("strikeZoneTop", 3.3)),
                                    "sz_bot": float(pdata.get("strikeZoneBottom", 1.5)),
                                    "stand": stand,
                                    "p_throws": p_throws,
                                    "type": details.get("code", "S"),
                                    "description": details.get("description", ""),
                                    "swing": is_swing,
                                    "whiff": is_whiff,
                                    "in_zone": in_zone,
                                    "out_zone": not in_zone,
                                    "chase": (not in_zone) and is_swing,
                                })
        except Exception:
            pass
        return game_pitches

    all_pitches = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        results = ex.map(_fetch_game_pitches, target_logs)
        for r in results:
            all_pitches.extend(r)

    if not all_pitches:
        return pd.DataFrame()

    df_res = pd.DataFrame(all_pitches)
    try:
        df_res.to_parquet(cache_path, index=False)
    except Exception:
        pass
    return df_res


@cache_ttl(ttl_seconds=3600)
def get_statcast_pitcher_df(
    pitcher_id: int,
    season: int = 2026,
    mode: str = "season",
    game_pk: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> pd.DataFrame:
    """Descarga lanzamientos Statcast vía pybaseball / Baseball Savant con caché en Parquet."""
    cache_name = f"sc_{pitcher_id}_{season}_{mode}"
    if mode == "game" and game_pk:
        cache_name += f"_{game_pk}"
    elif mode == "range" and start_date and end_date:
        cache_name += f"_{start_date}_{end_date}"
    cache_path = os.path.join(CACHE_STATCAST_DIR, f"{cache_name}.parquet")

    if os.path.exists(cache_path):
        try:
            return pd.read_parquet(cache_path)
        except Exception:
            pass

    df = pd.DataFrame()
    try:
        from pybaseball import statcast_pitcher
        if mode == "game" and start_date:
            df = statcast_pitcher(start_date, start_date, player_id=pitcher_id)
        elif mode == "range" and start_date and end_date:
            df = statcast_pitcher(start_date, end_date, player_id=pitcher_id)
        else:
            s_date = f"{season}-03-20"
            e_date = f"{season}-11-10"
            df = statcast_pitcher(s_date, e_date, player_id=pitcher_id)
    except Exception:
        pass

    if df is not None and not df.empty:
        try:
            df.to_parquet(cache_path, index=False)
        except Exception:
            pass
    return df if df is not None else pd.DataFrame()


def get_available_seasons() -> List[int]:
    """Retorna las temporadas canónicas disponibles para análisis."""
    return [2026, 2025, 2024, 2023, 2022]


def get_pitcher_season_statcast_df(
    pitcher_id: int,
    season: int = 2026,
    branch: str = "mlb",
    **kwargs
) -> pd.DataFrame:
    """Descarga lanzamientos Statcast para un lanzador en una temporada completa."""
    if branch == "lidom":
        return get_lidom_pitcher_statcast_df(pitcher_id, season=season, mode="season", **kwargs)
    return get_statcast_pitcher_df(pitcher_id, season=season, mode="season", **kwargs)


def get_pitch_analysis_for_df(df_sc: pd.DataFrame) -> Dict[str, Any]:
    """Calcula el resumen de análisis de lanzamientos para un DataFrame Statcast."""
    if df_sc is None or df_sc.empty:
        return {"total_pitches": 0, "statcast_table": [], "pitches": [], "pbp_kpis": {}}
    pitches_list = []
    for _, row in df_sc.iterrows():
        p_name = row.get("pitch_name") or "4-Seam Fastball"
        speed = row.get("release_speed")
        spin = row.get("release_spin_rate")
        pfx_x = row.get("pfx_x")
        pfx_z = row.get("pfx_z")
        try:
            val_x = float(pfx_x) if pfx_x is not None and not pd.isna(pfx_x) else 0.0
            hb = val_x if abs(val_x) > 6 else val_x * 12.0
        except Exception:
            hb = 0.0
        try:
            val_z = float(pfx_z) if pfx_z is not None and not pd.isna(pfx_z) else 0.0
            ivb = val_z if abs(val_z) > 6 else val_z * 12.0
        except Exception:
            ivb = 0.0

        is_whiff = bool(row.get("whiff", False))
        desc = str(row.get("description", "")).lower()
        is_called = "called_strike" in desc
        is_foul = "foul" in desc
        is_in_play = "in_play" in desc or "hit_into_play" in desc
        in_z = bool(row.get("in_zone", False))
        px = row.get("plate_x")
        pz = row.get("plate_z")

        pitches_list.append({
            "pitch_name": p_name,
            "speed": float(speed) if speed is not None and not pd.isna(speed) else None,
            "spin": int(spin) if spin is not None and not pd.isna(spin) else None,
            "ivb": round(ivb, 1),
            "hb": round(hb, 1),
            "is_whiff": is_whiff,
            "is_called": is_called,
            "is_foul": is_foul,
            "is_in_play": is_in_play,
            "is_zone": in_z,
            "plate_x": float(px) if px is not None and not pd.isna(px) else 0.0,
            "plate_z": float(pz) if pz is not None and not pd.isna(pz) else 2.5,
        })
    table = _build_statcast_table(pitches_list)
    tot = len(pitches_list)
    whiffs = sum(1 for p in pitches_list if p.get("is_whiff"))
    swings = sum(1 for p in pitches_list if p.get("is_whiff") or p.get("is_foul") or p.get("is_in_play"))
    called = sum(1 for p in pitches_list if p.get("is_called"))
    csw = whiffs + called
    csw_pct = f"{(csw / tot * 100):.1f}%" if tot > 0 else "0.0%"
    whiff_pct = f"{(whiffs / swings * 100):.1f}%" if swings > 0 else "0.0%"
    return {
        "total_pitches": tot,
        "statcast_table": table,
        "pitches": pitches_list,
        "pbp_kpis": {
            "csw_pct": csw_pct,
            "whiff_pct": whiff_pct,
        }
    }
