"""Cliente y gestor de consultas para Supabase en LIDOM 360."""

import os
import logging
from typing import Optional, List, Dict, Any
import pandas as pd
from supabase import create_client, Client
import streamlit as st

logger = logging.getLogger(__name__)


def get_supabase_credentials() -> tuple[Optional[str], Optional[str]]:
    """Obtiene URL y Key de Supabase desde Streamlit secrets, variables de entorno o archivo .streamlit/secrets.toml."""
    url = None
    key = None

    # 1. Intentar desde Streamlit secrets
    try:
        url = st.secrets.get("SUPABASE_URL") or st.secrets.get("supabase", {}).get("url")
        key = st.secrets.get("SUPABASE_KEY") or st.secrets.get("SUPABASE_SERVICE_ROLE_KEY") or st.secrets.get("supabase", {}).get("key")
    except Exception:
        pass

    # 2. Fallback a variables de entorno
    if not url:
        url = os.environ.get("SUPABASE_URL")
    if not key:
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_ANON_KEY")

    # 3. Fallback a archivo .streamlit/secrets.toml local si se ejecuta fuera de Streamlit
    if not url or not key:
        try:
            import tomllib
            secrets_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".streamlit", "secrets.toml")
            if os.path.exists(secrets_path):
                with open(secrets_path, "rb") as f:
                    sec = tomllib.load(f)
                    url = url or sec.get("SUPABASE_URL") or sec.get("supabase", {}).get("url")
                    key = key or sec.get("SUPABASE_KEY") or sec.get("SUPABASE_SERVICE_ROLE_KEY") or sec.get("supabase", {}).get("key")
        except Exception:
            pass

    return url, key


def ping_supabase() -> bool:
    """Envía un ping HTTP autenticado a Supabase para registrar actividad y prevenir el auto-pause (Free Tier)."""
    import requests

    url, key = get_supabase_credentials()
    if not url or not key:
        logger.warning("Credenciales de Supabase no disponibles para el ping Keep-Alive.")
        return False

    try:
        headers = {"apikey": key, "Authorization": f"Bearer {key}"}
        endpoint = f"{url.rstrip('/')}/auth/v1/health"
        resp = requests.get(endpoint, headers=headers, timeout=10)
        if resp.status_code == 200:
            logger.info("✅ Supabase Keep-Alive exitoso: actividad registrada para prevenir auto-pause.")
            return True
        else:
            logger.warning(f"Supabase Keep-Alive retornó código {resp.status_code}: {resp.text[:100]}")
            return False
    except Exception as e:
        logger.warning(f"No se pudo completar el ping Keep-Alive a Supabase: {e}")
        return False


@st.cache_resource
def init_supabase() -> Optional[Client]:
    """Inicializa la conexión con Supabase con manejo seguro de excepciones."""
    url, key = get_supabase_credentials()
    if not url or not key:
        logger.info("Credenciales de Supabase no detectadas. Usando modo local / API fallback.")
        return None
    try:
        client = create_client(url, key)
        return client
    except Exception as e:
        logger.error(f"Error conectando a Supabase: {e}")
        return None


def is_supabase_connected() -> bool:
    """Verifica si la instancia de Supabase está activa y conectada."""
    client = init_supabase()
    return client is not None


@st.cache_data(ttl=600)
def fetch_standings_from_db(season: int = 2024, game_type: str = "R") -> Optional[pd.DataFrame]:
    """Calcula y obtiene la tabla de posiciones desde la tabla `lidom_games` en Supabase."""
    client = init_supabase()
    if not client:
        return None

    try:
        # Obtener juegos finalizados
        response = client.table("lidom_games") \
            .select("*, home_team:lidom_teams!lidom_games_home_team_id_fkey(name, abbrev, primary_color, logo_url), away_team:lidom_teams!lidom_games_away_team_id_fkey(name, abbrev, primary_color, logo_url)") \
            .eq("season", season) \
            .eq("game_type", game_type) \
            .in_("status", ["Final", "Completed", "Completed Early", "Game Over"]) \
            .execute()

        if not response.data:
            return None

        games_df = pd.DataFrame(response.data)
        teams_resp = client.table("lidom_teams").select("*").execute()
        if not teams_resp.data:
            return None

        teams_df = pd.DataFrame(teams_resp.data)
        standings_data = []

        for _, team in teams_df.iterrows():
            t_id = team["id"]
            t_games = games_df[(games_df["home_team_id"] == t_id) | (games_df["away_team_id"] == t_id)]
            wins = 0
            losses = 0
            ca = 0
            cp = 0
            streak_str = "-"

            if len(t_games) > 0:
                t_games_sorted = t_games.sort_values("game_date")
                racha_list = []

                for _, g in t_games_sorted.iterrows():
                    is_h = g["home_team_id"] == t_id
                    my_s = g["home_score"] if is_h else g["away_score"]
                    opp_s = g["away_score"] if is_h else g["home_score"]
                    ca += (my_s or 0)
                    cp += (opp_s or 0)

                    if (my_s or 0) > (opp_s or 0):
                        wins += 1
                        racha_list.append("W")
                    else:
                        losses += 1
                        racha_list.append("L")

                if racha_list:
                    stk_type = racha_list[-1]
                    stk_count = 0
                    for r in reversed(racha_list):
                        if r == stk_type:
                            stk_count += 1
                        else:
                            break
                    streak_str = f"{stk_type}{stk_count}"

            total_g = wins + losses
            pct = (wins / total_g) if total_g > 0 else 0.0
            diff = ca - cp

            standings_data.append({
                "team_id": t_id,
                "Equipo": team["name"],
                "Abbrev": team["abbrev"],
                "Color": team["primary_color"],
                "Logo": team["logo_url"],
                "G": total_g,
                "W": wins,
                "L": losses,
                "PCT": f"{pct:.3f}".lstrip("0") if pct > 0 else ".000",
                "CA": ca,
                "CP": cp,
                "DIFF": f"{diff:+d}",
                "Racha": streak_str,
                "_pct_num": pct,
                "_wins": wins,
                "_losses": losses,
            })

        if not standings_data:
            return None

        df = pd.DataFrame(standings_data).sort_values(by="_pct_num", ascending=False)
        top_w = df.iloc[0]["_wins"]
        top_l = df.iloc[0]["_losses"]

        df["GB"] = df.apply(
            lambda r: "-" if r["team_id"] == df.iloc[0]["team_id"] else f"{((top_w - r['_wins']) + (r['_losses'] - top_l)) / 2.0:.1f}",
            axis=1
        )
        return df.drop(columns=["_pct_num", "_wins", "_losses"])

    except Exception as e:
        logger.error(f"Error consultando standings de Supabase: {e}")
        return None


def _fetch_all_from_supabase(table_name: str, select_clause: str, filters: list) -> list:
    """Recupera todos los registros de una tabla paginando en bloques de 1,000."""
    client = init_supabase()
    if not client:
        return []
    records = []
    page = 0
    page_size = 1000
    while True:
        query = client.table(table_name).select(select_clause)
        for col, val in filters:
            query = query.eq(col, val)
        resp = query.range(page * page_size, (page + 1) * page_size - 1).execute()
        if not resp.data:
            break
        records.extend(resp.data)
        if len(resp.data) < page_size:
            break
        page += 1
    return records


@st.cache_data(ttl=1800)
def fetch_batting_leaderboard_from_db(season: int = 2024, team_id: Optional[int] = None) -> Optional[pd.DataFrame]:
    """Obtiene estadísticas de bateo agrupadas por jugador desde `lidom_batting_stats`."""
    try:
        filters = [("season", season)]
        if team_id:
            filters.append(("team_id", team_id))

        select_clause = "*, player:lidom_players!lidom_batting_stats_player_id_fkey(full_name, primary_position), team:lidom_teams!lidom_batting_stats_team_id_fkey(abbrev)"
        data = _fetch_all_from_supabase("lidom_batting_stats", select_clause, filters)
        if not data:
            return None

        raw_df = pd.DataFrame(data)
        raw_df["name"] = raw_df["player"].apply(lambda x: x.get("full_name", "N/D") if isinstance(x, dict) else "N/D")
        raw_df["pos"] = raw_df["player"].apply(lambda x: x.get("primary_position", "UTL") if isinstance(x, dict) else "UTL")
        raw_df["team"] = raw_df["team"].apply(lambda x: x.get("abbrev", "LID") if isinstance(x, dict) else "LID")

        # Agrupar por jugador
        grouped = raw_df.groupby(["player_id", "name", "team", "pos"]).agg({
            "ab": "sum", "r": "sum", "h": "sum", "doubles": "sum", "triples": "sum",
            "hr": "sum", "rbi": "sum", "bb": "sum", "so": "sum", "sb": "sum", "hbp": "sum", "sf": "sum",
            "game_id": "count"
        }).reset_index().rename(columns={"game_id": "G", "ab": "AB", "r": "R", "h": "H", "doubles": "2B", "triples": "3B", "hr": "HR", "rbi": "RBI", "bb": "BB", "so": "SO", "sb": "SB"})

        # Métricas sabermétricas
        tb = (grouped["H"] - grouped["2B"] - grouped["3B"] - grouped["HR"]) + (2 * grouped["2B"]) + (3 * grouped["3B"]) + (4 * grouped["HR"])
        pa = grouped["AB"] + grouped["BB"] + grouped["hbp"] + grouped["sf"]
        avg_num = (grouped["H"] / grouped["AB"].replace(0, 1)).fillna(0)
        obp_num = ((grouped["H"] + grouped["BB"] + grouped["hbp"]) / pa.replace(0, 1)).fillna(0)
        slg_num = (tb / grouped["AB"].replace(0, 1)).fillna(0)
        ops_num = obp_num + slg_num
        iso_num = (slg_num - avg_num).clip(lower=0)

        # wOBA aproximado
        woba_num = ((0.69 * grouped["BB"]) + (0.72 * grouped["hbp"]) + (0.88 * (grouped["H"] - grouped["2B"] - grouped["3B"] - grouped["HR"])) + (1.24 * grouped["2B"]) + (1.56 * grouped["3B"]) + (2.01 * grouped["HR"])) / pa.replace(0, 1)

        grouped["AVG"] = avg_num.apply(lambda x: f"{x:.3f}".lstrip("0") if x < 1.0 else f"{x:.3f}")
        grouped["OBP"] = obp_num.apply(lambda x: f"{x:.3f}".lstrip("0") if x < 1.0 else f"{x:.3f}")
        grouped["SLG"] = slg_num.apply(lambda x: f"{x:.3f}".lstrip("0") if x < 1.0 else f"{x:.3f}")
        grouped["OPS"] = ops_num.apply(lambda x: f"{x:.3f}".lstrip("0") if x < 1.0 else f"{x:.3f}")
        grouped["ISO"] = iso_num.apply(lambda x: f"{x:.3f}".lstrip("0") if x < 1.0 else f"{x:.3f}")
        grouped["wOBA"] = woba_num.apply(lambda x: f"{x:.3f}".lstrip("0") if x < 1.0 else f"{x:.3f}")
        grouped["wRC+"] = ((woba_num / 0.320) * 100).round(0).astype(int)
        grouped["WPA"] = 0.0
        grouped["Hard%"] = 38.0
        grouped["BB%"] = ((grouped["BB"] / pa.replace(0, 1)) * 100).round(1)
        grouped["K%"] = ((grouped["SO"] / pa.replace(0, 1)) * 100).round(1)

        grouped["_avg_num"] = avg_num
        grouped["_obp_num"] = obp_num
        grouped["_slg_num"] = slg_num
        grouped["_ops_num"] = ops_num
        grouped["_woba_num"] = woba_num
        grouped["_iso_num"] = iso_num

        return grouped.sort_values(by="OPS", ascending=False)

    except Exception as e:
        logger.error(f"Error consultando bateo de Supabase: {e}")
        return None


@st.cache_data(ttl=1800)
def fetch_pitching_leaderboard_from_db(season: int = 2024, team_id: Optional[int] = None) -> Optional[pd.DataFrame]:
    """Obtiene estadísticas de pitcheo agrupadas por jugador desde `lidom_pitching_stats`."""
    try:
        filters = [("season", season)]
        if team_id:
            filters.append(("team_id", team_id))

        select_clause = "*, player:lidom_players!lidom_pitching_stats_player_id_fkey(full_name, primary_position), team:lidom_teams!lidom_pitching_stats_team_id_fkey(abbrev)"
        data = _fetch_all_from_supabase("lidom_pitching_stats", select_clause, filters)
        if not data:
            return None

        raw_df = pd.DataFrame(data)
        raw_df["name"] = raw_df["player"].apply(lambda x: x.get("full_name", "N/D") if isinstance(x, dict) else "N/D")
        raw_df["role"] = raw_df["role"].fillna("RP")
        raw_df["team"] = raw_df["team"].apply(lambda x: x.get("abbrev", "LID") if isinstance(x, dict) else "LID")

        grouped = raw_df.groupby(["player_id", "name", "team", "role"]).agg({
            "ip_decimal": "sum", "h": "sum", "r": "sum", "er": "sum", "bb": "sum",
            "so": "sum", "hr": "sum", "w": "sum", "l": "sum", "sv": "sum", "is_starter": "sum",
            "game_id": "count"
        }).reset_index().rename(columns={"game_id": "G", "is_starter": "GS", "ip_decimal": "IP", "h": "H", "r": "R", "er": "ER", "bb": "BB", "so": "SO", "hr": "HR", "w": "W", "l": "L", "sv": "SV"})

        # Métricas
        ip_safe = grouped["IP"].replace(0, 0.1)
        era_f = ((grouped["ER"] * 9.0) / ip_safe).round(2)
        whip_f = ((grouped["H"] + grouped["BB"]) / ip_safe).round(2)
        fip_f = (((13 * grouped["HR"]) + (3 * (grouped["BB"])) - (2 * grouped["SO"])) / ip_safe + 3.10).round(2)
        k9_f = ((grouped["SO"] * 9.0) / ip_safe).round(1)
        bb9_f = ((grouped["BB"] * 9.0) / ip_safe).round(1)
        bf_approx = (grouped["IP"] * 3.0) + grouped["H"] + grouped["BB"]
        k_pct = ((grouped["SO"] / bf_approx.replace(0, 1)) * 100).round(1)

        grouped["ERA"] = era_f.astype(str)
        grouped["WHIP"] = whip_f.astype(str)
        grouped["FIP"] = fip_f.astype(str)
        grouped["K/9"] = k9_f.astype(str)
        grouped["BB/9"] = bb9_f.astype(str)
        grouped["K%"] = k_pct
        grouped["WPA"] = 0.0

        grouped["_era_f"] = era_f
        grouped["_whip_f"] = whip_f
        grouped["_fip_f"] = fip_f
        grouped["_ip_f"] = grouped["IP"]

        return grouped.sort_values(by="IP", ascending=False)

    except Exception as e:
        logger.error(f"Error consultando pitcheo de Supabase: {e}")
        return None
