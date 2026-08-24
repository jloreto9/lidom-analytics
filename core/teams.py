"""Metadatos canónicos, paletas de color, estadios y logos oficiales de los 6 equipos de LIDOM."""

from typing import Dict, Any, Optional, List

LIDOM_LEAGUE_ID = 131
LIDOM_SPORT_ID = 17

TEAMS: Dict[int, Dict[str, Any]] = {
    672: {
        "id": 672,
        "abbrev": "LIC",
        "name": "Tigres del Licey",
        "short_name": "Licey",
        "city": "Santo Domingo",
        "stadium": "Estadio Quisqueya Juan Marichal",
        "primary_color": "#002D62",
        "secondary_color": "#FFFFFF",
        "accent_color": "#0055B8",
        "text_color": "#FFFFFF",
        "logo_url": "https://midfield.mlbstatic.com/v1/team/672/spots/120",
        "founded": 1907,
        "championships": 24,
    },
    667: {
        "id": 667,
        "abbrev": "AGU",
        "name": "Águilas Cibaeñas",
        "short_name": "Águilas",
        "city": "Santiago de los Caballeros",
        "stadium": "Estadio Cibao",
        "primary_color": "#FFCC00",
        "secondary_color": "#111111",
        "accent_color": "#FFAA00",
        "text_color": "#000000",
        "logo_url": "https://midfield.mlbstatic.com/v1/team/667/spots/120",
        "founded": 1933,
        "championships": 22,
    },
    671: {
        "id": 671,
        "abbrev": "ESC",
        "name": "Leones del Escogido",
        "short_name": "Escogido",
        "city": "Santo Domingo",
        "stadium": "Estadio Quisqueya Juan Marichal",
        "primary_color": "#CC0000",
        "secondary_color": "#FFFFFF",
        "accent_color": "#E60000",
        "text_color": "#FFFFFF",
        "logo_url": "https://midfield.mlbstatic.com/v1/team/671/spots/120",
        "founded": 1921,
        "championships": 16,
    },
    670: {
        "id": 670,
        "abbrev": "GIG",
        "name": "Gigantes del Cibao",
        "short_name": "Gigantes",
        "city": "San Francisco de Macorís",
        "stadium": "Estadio Julián Javier",
        "primary_color": "#5B1E31",
        "secondary_color": "#D29B38",
        "accent_color": "#7E2A44",
        "text_color": "#FFFFFF",
        "logo_url": "https://midfield.mlbstatic.com/v1/team/670/spots/120",
        "founded": 1996,
        "championships": 2,
    },
    669: {
        "id": 669,
        "abbrev": "EST",
        "name": "Estrellas Orientales",
        "short_name": "Estrellas",
        "city": "San Pedro de Macorís",
        "stadium": "Estadio Tetelo Vargas",
        "primary_color": "#005A36",
        "secondary_color": "#C49A45",
        "accent_color": "#007A48",
        "text_color": "#FFFFFF",
        "logo_url": "https://midfield.mlbstatic.com/v1/team/669/spots/120",
        "founded": 1910,
        "championships": 3,
    },
    668: {
        "id": 668,
        "abbrev": "TOR",
        "name": "Toros del Este",
        "short_name": "Toros",
        "city": "La Romana",
        "stadium": "Estadio Francisco Micheli",
        "primary_color": "#EA5B0C",
        "secondary_color": "#111111",
        "accent_color": "#FF6F1C",
        "text_color": "#FFFFFF",
        "logo_url": "https://midfield.mlbstatic.com/v1/team/668/spots/120",
        "founded": 1983,
        "championships": 3,
    },
}

# Lookup dictionaries
TEAMS_BY_ABBREV: Dict[str, Dict[str, Any]] = {
    team["abbrev"]: team for team in TEAMS.values()
}

TEAMS_BY_NAME: Dict[str, Dict[str, Any]] = {
    team["name"].lower(): team for team in TEAMS.values()
}
for team in TEAMS.values():
    TEAMS_BY_NAME[team["short_name"].lower()] = team


def get_team_by_id(team_id: int) -> Optional[Dict[str, Any]]:
    """Obtiene el diccionario de metadatos de un equipo por su teamId."""
    return TEAMS.get(team_id)


def get_team_by_abbrev(abbrev: str) -> Optional[Dict[str, Any]]:
    """Obtiene el equipo por su abreviatura canónica (LIC, AGU, ESC, GIG, EST, TOR)."""
    return TEAMS_BY_ABBREV.get(abbrev.upper())


def resolve_team(identifier: Any) -> Optional[Dict[str, Any]]:
    """Resuelve un equipo a partir de ID numérico, abreviatura o nombre."""
    if isinstance(identifier, int):
        return get_team_by_id(identifier)
    if isinstance(identifier, str):
        if identifier.isdigit():
            return get_team_by_id(int(identifier))
        abbrev_match = get_team_by_abbrev(identifier)
        if abbrev_match:
            return abbrev_match
        return TEAMS_BY_NAME.get(identifier.lower().strip())
    return None


def get_all_teams() -> List[Dict[str, Any]]:
    """Retorna lista de los 6 equipos LIDOM ordenados."""
    return list(TEAMS.values())


def get_team_color(team_id: int, fallback: str = "#002D62") -> str:
    """Retorna el color primario HEX del equipo."""
    team = get_team_by_id(team_id)
    return team["primary_color"] if team else fallback


def get_team_logo(team_id: int) -> str:
    """Retorna la URL del logo oficial en MLB Midfield."""
    team = get_team_by_id(team_id)
    return team["logo_url"] if team else f"https://midfield.mlbstatic.com/v1/team/{team_id}/spots/120"
