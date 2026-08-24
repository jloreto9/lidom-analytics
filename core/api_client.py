"""Cliente para consumir la MLB Stats API para LIDOM (sportId=17, leagueId=131)."""

import logging
from typing import Dict, Any, Optional, List
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

BASE_URL_V1 = "https://statsapi.mlb.com/api/v1"
BASE_URL_V1_1 = "https://statsapi.mlb.com/api/v1.1"

LIDOM_LEAGUE_ID = 131
LIDOM_SPORT_ID = 17


class MLBLIDOMApiClient:
    """Cliente HTTP resiliente para consultar la API de MLB Stats para LIDOM."""

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.session = requests.Session()
        retries = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.session.headers.update({
            "User-Agent": "LIDOM360-Analytics/1.0 (Baseball Sabermetrics Platform)",
            "Accept": "application/json",
        })

    def _get(self, url: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Realiza una petición GET segura retornando JSON o None en caso de fallo."""
        try:
            resp = self.session.get(url, params=params, timeout=self.timeout)
            if resp.status_code == 200:
                return resp.json()
            logger.warning(f"MLB API returned status {resp.status_code} for {url}")
            return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    def get_schedule(self, season: int = 2024, game_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Obtiene el calendario de juegos de LIDOM para la temporada dada.
        game_type: 'R' (Regular), 'W' (Round Robin), 'F' (Final) o None (todos).
        """
        url = f"{BASE_URL_V1}/schedule"
        params: Dict[str, Any] = {
            "sportId": LIDOM_SPORT_ID,
            "leagueId": LIDOM_LEAGUE_ID,
            "season": season,
            "hydrate": "team,linescore,boxscore(scoringPlays)",
        }
        if game_type:
            params["gameType"] = game_type

        data = self._get(url, params=params)
        if not data or "dates" not in data:
            return []

        games = []
        for date_item in data.get("dates", []):
            for game in date_item.get("games", []):
                games.append(game)
        return games

    def get_standings(self, season: int = 2024, standings_type: str = "regularSeason") -> Optional[Dict[str, Any]]:
        """Obtiene la tabla de posiciones oficial de LIDOM."""
        url = f"{BASE_URL_V1}/standings"
        params = {
            "leagueId": LIDOM_LEAGUE_ID,
            "season": season,
            "standingsTypes": standings_type,
            "hydrate": "team",
        }
        return self._get(url, params=params)

    def get_game_feed(self, game_pk: int) -> Optional[Dict[str, Any]]:
        """Obtiene el live feed detallado play-by-play de un partido (v1.1)."""
        url = f"{BASE_URL_V1_1}/game/{game_pk}/feed/live"
        return self._get(url)

    def get_boxscore(self, game_pk: int) -> Optional[Dict[str, Any]]:
        """Obtiene el boxscore oficial estructurado de un juego."""
        url = f"{BASE_URL_V1}/game/{game_pk}/boxscore"
        return self._get(url)

    def get_team_roster(self, team_id: int, season: int = 2024) -> Optional[Dict[str, Any]]:
        """Obtiene el roster activo de un equipo para una temporada."""
        url = f"{BASE_URL_V1}/teams/{team_id}/roster"
        params = {"season": season, "rosterType": "active"}
        return self._get(url, params=params)

    def get_player_stats(self, player_id: int, season: int = 2024) -> Optional[Dict[str, Any]]:
        """Obtiene estadísticas de un jugador en la liga LIDOM."""
        url = f"{BASE_URL_V1}/people/{player_id}/stats"
        params = {
            "stats": "season",
            "season": season,
            "group": "hitting,pitching",
            "leagueId": LIDOM_LEAGUE_ID,
        }
        return self._get(url, params=params)
