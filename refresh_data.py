"""Script CLI para ingesta y actualización de datos de LIDOM desde la MLB Stats API."""

import os
import json
import logging
import argparse
from core.api_client import MLBLIDOMApiClient
from core.teams import TEAMS

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("LIDOM_REFRESH")

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def refresh_season_data(season: int = 2024) -> None:
    """Descarga y persiste datos de la temporada de LIDOM."""
    os.makedirs(DATA_DIR, exist_ok=True)
    client = MLBLIDOMApiClient()

    logger.info(f"Iniciando ingesta de LIDOM para la temporada {season}...")

    # 1. Standings
    logger.info("Descargando tabla de posiciones...")
    standings = client.get_standings(season=season)
    if standings:
        path = os.path.join(DATA_DIR, f"standings_{season}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(standings, f, ensure_ascii=False, indent=2)
        logger.info(f"Standings guardados en {path}")

    # 2. Schedule
    logger.info("Descargando calendario de juegos...")
    schedule = client.get_schedule(season=season)
    if schedule:
        path = os.path.join(DATA_DIR, f"schedule_{season}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(schedule, f, ensure_ascii=False, indent=2)
        logger.info(f"Calendario ({len(schedule)} juegos) guardado en {path}")

    # 3. Rosters por Equipo
    for team_id, team_meta in TEAMS.items():
        logger.info(f"Descargando roster de {team_meta['name']} ({team_meta['abbrev']})...")
        roster = client.get_team_roster(team_id=team_id, season=season)
        if roster:
            path = os.path.join(DATA_DIR, f"roster_{team_meta['abbrev']}_{season}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(roster, f, ensure_ascii=False, indent=2)

    logger.info("¡Ingesta de datos de LIDOM completada con éxito!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Actualizar datos de LIDOM desde MLB Stats API.")
    parser.add_argument("--season", type=int, default=2024, help="Temporada LIDOM (ej: 2024)")
    args = parser.parse_args()

    refresh_season_data(season=args.season)
