"""Pipeline de ingesta masiva de LIDOM (2023, 2024, 2025) a Supabase desde la MLB Stats API."""

import os
import sys
import logging
import argparse
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from supabase import create_client, Client

from core.teams import TEAMS, get_team_by_id
from core.api_client import MLBLIDOMApiClient
from core.bis_hardness import classify_batted_ball_hardness
from core.wpa_engine import compute_play_wpa, get_base_state_index
from core.supabase_client import get_supabase_credentials

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("LIDOM_INGEST")


class LIDOMSupabaseIngester:
    """Orquestador de extracción, transformación y carga (ETL) a Supabase para LIDOM."""

    def __init__(self, client: Optional[Client] = None, dry_run: bool = False):
        self.dry_run = dry_run
        self.api = MLBLIDOMApiClient()

        if dry_run:
            self.client = None
            logger.info("Modo DRY-RUN activado. No se realizarán escrituras a Supabase.")
        else:
            if client:
                self.client = client
            else:
                url, key = get_supabase_credentials()
                if not url or not key:
                    logger.warning("Credenciales de Supabase no encontradas. Cambiando automáticamente a DRY-RUN.")
                    self.dry_run = True
                    self.client = None
                else:
                    self.client = create_client(url, key)
                    logger.info("Conectado exitosamente a Supabase.")

    def seed_teams(self) -> None:
        """Puebla o actualiza los 6 equipos canónicos de LIDOM."""
        logger.info("Poblando metadatos de las 6 franquicias LIDOM...")
        teams_data = []
        for t_id, meta in TEAMS.items():
            teams_data.append({
                "id": t_id,
                "name": meta["name"],
                "short_name": meta["short_name"],
                "abbrev": meta["abbrev"],
                "city": meta["city"],
                "stadium": meta["stadium"],
                "primary_color": meta["primary_color"],
                "secondary_color": meta.get("secondary_color", "#FFFFFF"),
                "accent_color": meta.get("accent_color", meta["primary_color"]),
                "text_color": meta.get("text_color", "#FFFFFF"),
                "logo_url": meta["logo_url"],
                "founded": meta.get("founded", 1900),
                "championships": meta.get("championships", 0),
            })

        if not self.dry_run and self.client:
            self.client.table("lidom_teams").upsert(teams_data).execute()
            logger.info("Equipos guardados en `lidom_teams`.")
        else:
            logger.info(f"[DRY-RUN] Se habrían insertado {len(teams_data)} equipos.")

    def process_game(self, game_item: Dict[str, Any], season: int, with_pbp: bool = False) -> Dict[str, Any]:
        """Extrae los datos de un juego, boxscore y jugadas."""
        game_pk = game_item.get("gamePk")
        h_team = game_item.get("teams", {}).get("home", {})
        a_team = game_item.get("teams", {}).get("away", {})
        h_id = h_team.get("team", {}).get("id")
        a_id = a_team.get("team", {}).get("id")
        status = game_item.get("status", {}).get("abstractGameState", "Final")
        detailed_state = game_item.get("status", {}).get("detailedState", "Final")
        game_type = game_item.get("gameType", "R")
        game_date = game_item.get("gameDate", "")[:10]
        venue_name = game_item.get("venue", {}).get("name", "Estadio LIDOM")

        game_record = {
            "id": game_pk,
            "season": season,
            "game_date": game_date,
            "game_datetime": game_item.get("gameDate"),
            "game_type": game_type,
            "status": status,
            "detailed_state": detailed_state,
            "home_team_id": h_id,
            "away_team_id": a_id,
            "home_score": h_team.get("score", 0),
            "away_score": a_team.get("score", 0),
            "venue_name": venue_name,
            "linescore": game_item.get("linescore", {}),
        }

        players_records = []
        batting_records = []
        pitching_records = []
        plays_records = []

        # Si el juego no se ha jugado, solo retornamos el registro del juego
        if status not in ["Final", "Completed", "Completed Early", "Game Over"]:
            return {
                "game": game_record,
                "players": [],
                "batting": [],
                "pitching": [],
                "plays": [],
            }

        # Consultar Boxscore
        box = self.api.get_boxscore(game_pk)
        if box and "teams" in box:
            for side in ["home", "away"]:
                side_box = box["teams"].get(side, {})
                t_id = side_box.get("team", {}).get("id")
                players_dict = side_box.get("players", {})

                for p_key, p_val in players_dict.items():
                    person = p_val.get("person", {})
                    p_id = person.get("id")
                    if not p_id:
                        continue

                    full_name = person.get("fullName", "Jugador")
                    pos = p_val.get("position", {}).get("abbreviation", "UTL")
                    jersey = p_val.get("jerseyNumber", "")

                    players_records.append({
                        "id": p_id,
                        "full_name": full_name,
                        "team_id": t_id,
                        "primary_position": pos,
                        "jersey_number": jersey,
                        "headshot_url": f"https://img.mlbstatic.com/mlb-photos/image/upload/d_people:generic:headshot:67:current.png/w_213,q_auto:best/v1/people/{p_id}/headshot/67/current",
                    })

                    # Bateo
                    stats_bat = p_val.get("stats", {}).get("batting", {})
                    if stats_bat and stats_bat.get("atBats", 0) > 0 or stats_bat.get("plateAppearances", 0) > 0:
                        batting_records.append({
                            "game_id": game_pk,
                            "player_id": p_id,
                            "team_id": t_id,
                            "season": season,
                            "batting_order": int(p_val.get("battingOrder", 0) or 0),
                            "position": pos,
                            "ab": stats_bat.get("atBats", 0),
                            "r": stats_bat.get("runs", 0),
                            "h": stats_bat.get("hits", 0),
                            "doubles": stats_bat.get("doubles", 0),
                            "triples": stats_bat.get("triples", 0),
                            "hr": stats_bat.get("homeRuns", 0),
                            "rbi": stats_bat.get("rbi", 0),
                            "bb": stats_bat.get("baseOnBalls", 0),
                            "so": stats_bat.get("strikeOuts", 0),
                            "sb": stats_bat.get("stolenBases", 0),
                            "cs": stats_bat.get("caughtStealing", 0),
                            "hbp": stats_bat.get("hitByPitch", 0),
                            "sf": stats_bat.get("sacFlies", 0),
                            "sh": stats_bat.get("sacBunts", 0),
                        })

                    # Pitcheo
                    stats_pit = p_val.get("stats", {}).get("pitching", {})
                    if stats_pit and (stats_pit.get("inningsPitched") or stats_pit.get("pitchesThrown", 0) > 0):
                        ip_str = str(stats_pit.get("inningsPitched", "0.0"))
                        try:
                            if "." in ip_str:
                                full_inn, frac = ip_str.split(".")
                                ip_dec = float(full_inn) + (float(frac) / 3.0)
                            else:
                                ip_dec = float(ip_str)
                        except Exception:
                            ip_dec = 0.0

                        is_sp = (pos == "P" and p_val.get("gameStatus", {}).get("isStarter", False))
                        pitching_records.append({
                            "game_id": game_pk,
                            "player_id": p_id,
                            "team_id": t_id,
                            "season": season,
                            "role": "SP" if is_sp else "RP",
                            "is_starter": is_sp,
                            "ip_decimal": round(ip_dec, 2),
                            "h": stats_pit.get("hits", 0),
                            "r": stats_pit.get("runs", 0),
                            "er": stats_pit.get("earnedRuns", 0),
                            "bb": stats_pit.get("baseOnBalls", 0),
                            "so": stats_pit.get("strikeOuts", 0),
                            "hr": stats_pit.get("homeRuns", 0),
                            "hbp": stats_pit.get("hitByPitch", 0),
                            "wp": stats_pit.get("wildPitches", 0),
                            "bk": stats_pit.get("balks", 0),
                            "w": 1 if stats_pit.get("wins", 0) > 0 else 0,
                            "l": 1 if stats_pit.get("losses", 0) > 0 else 0,
                            "sv": 1 if stats_pit.get("saves", 0) > 0 else 0,
                            "hold": 1 if stats_pit.get("holds", 0) > 0 else 0,
                            "pitches_thrown": stats_pit.get("pitchesThrown", 0),
                            "strikes": stats_pit.get("strikes", 0),
                        })

        # Consultar Play-by-Play si se solicita
        if with_pbp:
            feed = self.api.get_game_feed(game_pk)
            if feed and "liveData" in feed:
                all_plays = feed.get("liveData", {}).get("plays", {}).get("allPlays", [])
                h_score, a_score = 0, 0
                for p in all_plays:
                    about = p.get("about", {})
                    inn = about.get("inning", 1)
                    is_bot = about.get("isTopInning", True) is False
                    outs = p.get("count", {}).get("outs", 0)
                    ev = p.get("result", {}).get("event", "Play")
                    ev_type = p.get("result", {}).get("eventType", "")
                    desc = p.get("result", {}).get("description", "")
                    r_h = p.get("result", {}).get("homeScore", h_score)
                    r_a = p.get("result", {}).get("awayScore", a_score)
                    diff = r_h - r_a

                    b_idx = 0
                    if p.get("matchup", {}).get("postOnFirst"): b_idx |= 1
                    if p.get("matchup", {}).get("postOnSecond"): b_idx |= 2
                    if p.get("matchup", {}).get("postOnThird"): b_idx |= 4

                    wpa_res = compute_play_wpa(inn, is_bot, max(0, outs - 1), 0, diff, outs, b_idx, diff)
                    h_score, a_score = r_h, r_a

                    # Coordenadas y dureza
                    hit_data = p.get("playEvents", [{}])[-1].get("hitData", {}) if p.get("playEvents") else {}
                    hc_x = hit_data.get("coordinates", {}).get("coordX")
                    hc_y = hit_data.get("coordinates", {}).get("coordY")
                    dist = hit_data.get("totalDistance")
                    speed = hit_data.get("launchSpeed")
                    traj = hit_data.get("trajectory", "")
                    hard_label, _ = classify_batted_ball_hardness(launch_speed=speed, trajectory=traj, event_type=ev)

                    bat_id = p.get("matchup", {}).get("batter", {}).get("id")
                    bat_name = p.get("matchup", {}).get("batter", {}).get("fullName")
                    pit_id = p.get("matchup", {}).get("pitcher", {}).get("id")
                    pit_name = p.get("matchup", {}).get("pitcher", {}).get("fullName")
                    bat_team = h_id if is_bot else a_id
                    field_team = a_id if is_bot else h_id

                    plays_records.append({
                        "game_id": game_pk,
                        "play_id": str(p.get("atBatIndex", "")),
                        "season": season,
                        "inning": inn,
                        "half_inning": "bottom" if is_bot else "top",
                        "outs": outs,
                        "batter_id": bat_id,
                        "batter_name": bat_name,
                        "pitcher_id": pit_id,
                        "pitcher_name": pit_name,
                        "batting_team_id": bat_team,
                        "fielding_team_id": field_team,
                        "event": ev,
                        "event_type": ev_type,
                        "description": desc,
                        "score_home": r_h,
                        "score_away": r_a,
                        "base_state": b_idx,
                        "we_before": wpa_res["we_before"],
                        "we_after": wpa_res["we_after"],
                        "wpa_batter": wpa_res["wpa_batter"],
                        "wpa_pitcher": wpa_res["wpa_pitcher"],
                        "leverage_index": wpa_res["leverage_index"],
                        "hc_x": hc_x,
                        "hc_y": hc_y,
                        "distance": dist,
                        "launch_speed": speed,
                        "trajectory": traj,
                        "hardness": hard_label,
                    })

        return {
            "game": game_record,
            "players": players_records,
            "batting": batting_records,
            "pitching": pitching_records,
            "plays": plays_records,
        }

    def ingest_season(self, season: int, max_workers: int = 8, with_pbp: bool = False, limit_games: Optional[int] = None) -> None:
        """Descarga e inserta todos los juegos y estadísticas de una temporada de LIDOM."""
        logger.info(f"=== INICIANDO INGESTA LIDOM — TEMPORADA {season} ===")
        schedule = self.api.get_schedule(season=season)
        if not schedule:
            logger.error(f"No se encontraron juegos para la temporada {season} en MLB Stats API.")
            return

        if limit_games:
            schedule = schedule[:limit_games]

        total_games = len(schedule)
        logger.info(f"Se procesarán {total_games} partidos de la temporada {season} con {max_workers} hilos...")

        all_games = []
        all_players_dict = {}
        all_batting = []
        all_pitching = []
        all_plays = []

        completed_count = 0
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_game = {
                executor.submit(self.process_game, g, season, with_pbp): g.get("gamePk")
                for g in schedule
            }

            for future in as_completed(future_to_game):
                g_pk = future_to_game[future]
                try:
                    res = future.result()
                    all_games.append(res["game"])
                    for p in res["players"]:
                        all_players_dict[p["id"]] = p
                    all_batting.extend(res["batting"])
                    all_pitching.extend(res["pitching"])
                    all_plays.extend(res["plays"])
                    completed_count += 1

                    if completed_count % 25 == 0 or completed_count == total_games:
                        logger.info(f"Progreso: {completed_count}/{total_games} juegos procesados ({(completed_count/total_games)*100:.1f}%)")
                except Exception as exc:
                    logger.error(f"Error procesando juego {g_pk}: {exc}")

        # Ejecutar Upserts en Supabase por lotes
        logger.info(f"Totales extraídos ({season}): {len(all_games)} juegos, {len(all_players_dict)} jugadores, {len(all_batting)} registros de bateo, {len(all_pitching)} registros de pitcheo, {len(all_plays)} jugadas.")

        if not self.dry_run and self.client:
            # 1. Games
            self._batch_upsert("lidom_games", all_games)
            # 2. Players
            self._batch_upsert("lidom_players", list(all_players_dict.values()))
            # 3. Batting Stats
            self._batch_upsert("lidom_batting_stats", all_batting, on_conflict="game_id,player_id")
            # 4. Pitching Stats
            self._batch_upsert("lidom_pitching_stats", all_pitching, on_conflict="game_id,player_id")
            # 5. Plays
            if all_plays:
                self._batch_upsert("lidom_plays", all_plays)

            logger.info(f"✅ ¡Temporada {season} de LIDOM sincronizada exitosamente en Supabase!")
        else:
            logger.info(f"✅ [DRY-RUN] Simulación completa para la temporada {season}.")

    def _batch_upsert(self, table_name: str, records: List[Dict[str, Any]], batch_size: int = 100, on_conflict: Optional[str] = None) -> None:
        """Ejecuta inserciones por lotes para evitar límites de payload en Supabase."""
        if not records or not self.client:
            return

        total = len(records)
        logger.info(f"Guardando {total} registros en `{table_name}` en lotes de {batch_size}...")
        for i in range(0, total, batch_size):
            chunk = records[i:i + batch_size]
            try:
                query = self.client.table(table_name).upsert(chunk)
                if on_conflict:
                    query = query.on_conflict(on_conflict)
                query.execute()
            except Exception as e:
                logger.error(f"Error guardando lote {i//batch_size + 1} en {table_name}: {e}")


def main():
    parser = argparse.ArgumentParser(description="Ingesta masiva de LIDOM a Supabase.")
    parser.add_argument("--seasons", nargs="+", type=int, default=[2023, 2024], help="Temporadas a ingerir (ej: 2023 2024)")
    parser.add_argument("--workers", type=int, default=8, help="Número de hilos concurrentes")
    parser.add_argument("--skip-pbp", action="store_true", help="Omitir extracción granular de play-by-play (por defecto se incluye)")
    parser.add_argument("--sample", type=int, default=None, help="Limitar a N juegos por temporada (para pruebas rápidas)")
    parser.add_argument("--dry-run", action="store_true", help="Ejecutar sin escribir en la base de datos")

    args = parser.parse_args()

    ingester = LIDOMSupabaseIngester(dry_run=args.dry_run)
    ingester.seed_teams()

    include_pbp = not args.skip_pbp

    for season in args.seasons:
        ingester.ingest_season(
            season=season,
            max_workers=args.workers,
            with_pbp=include_pbp,
            limit_games=args.sample,
        )


if __name__ == "__main__":
    main()
