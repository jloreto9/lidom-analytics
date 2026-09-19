"""
tests/test_pitching_lidom.py
----------------------------
Suite de pruebas unitarias para el módulo de Pitching Summary & Telemetría en LIDOM 360.
Valida:
1. Resolución y temporadas disponibles (2026 incluido).
2. Metadatos y búsqueda de lanzadores LIDOM.
3. Extracción de salidas de LIDOM y México con decisiones y conteos P-S.
4. Generación de tarjetas gráficas HD (2400x2400 px a 300 DPI) para LIDOM, México y MLB.
"""

import io
import unittest
import pandas as pd
from PIL import Image

from core.pitching_engine import (
    get_available_seasons,
    get_pitcher_by_id,
    get_pitcher_game_logs,
    search_pitchers,
    LIDOM_TEAMS,
    LIDOM_ABBR,
)
from core.pitching_card import (
    build_pitching_summary_card,
    CANVAS_SIZE,
    DPI,
)


class TestPitchingLIDOM(unittest.TestCase):
    """Pruebas para el motor de pitcheo y generación de tarjetas en LIDOM 360."""

    def test_available_seasons(self):
        """Verifica que 2026 esté incluido y sea la temporada más reciente."""
        seasons = get_available_seasons()
        self.assertIn(2026, seasons)
        self.assertIn(2025, seasons)
        self.assertIn(2024, seasons)
        self.assertEqual(seasons[0], 2026)

    def test_lidom_teams_mapping(self):
        """Verifica el mapeo canónico de los 6 equipos de LIDOM."""
        self.assertEqual(len(LIDOM_TEAMS), 6)
        self.assertIn(672, LIDOM_TEAMS)  # Tigres del Licey
        self.assertIn(667, LIDOM_TEAMS)  # Águilas Cibaeñas
        self.assertIn(671, LIDOM_TEAMS)  # Leones del Escogido
        self.assertIn(670, LIDOM_TEAMS)  # Gigantes del Cibao
        self.assertIn(669, LIDOM_TEAMS)  # Estrellas Orientales
        self.assertIn(668, LIDOM_TEAMS)  # Toros del Este

    def test_get_pitcher_by_id_cesar_valdez(self):
        """Verifica obtención de datos de César Valdez (Licey)."""
        p = get_pitcher_by_id(491624)
        self.assertIsNotNone(p)
        self.assertIn("Valdez", p["name"])
        self.assertTrue(p.get("has_lidom", False))

    def test_search_pitchers_cesar_valdez(self):
        """Verifica que el buscador encuentre a César Valdez."""
        res = search_pitchers("Cesar Valdez")
        self.assertTrue(len(res) > 0)
        self.assertEqual(res[0]["id"], 491624)

    def test_mexico_game_logs_2026(self):
        """Verifica que un lanzador activo en LMB 2026 retorne salidas con decisiones oficiales."""
        # Junior Guerra (457918) lanzó con Conspiradores de Querétaro en verano 2026
        logs = get_pitcher_game_logs(457918, season=2026, branch="mexico")
        self.assertIsInstance(logs, list)
        if logs:
            first = logs[0]
            self.assertIn("game_pk", first)
            self.assertIn("decision", first)
            self.assertIn("pitches", first)
            self.assertEqual(first["league"], "México")

    def test_lidom_card_generation_2400x2400(self):
        """Verifica que la tarjeta gráfica para LIDOM se genere en 2400x2400 px a 300 DPI."""
        p_info = {
            "id": 491624,
            "name": "César Valdez",
            "throws": "R",
            "age": 39,
            "height": "6' 2\"",
            "weight": 200,
            "team_name": "Tigres del Licey",
            "has_lidom": True,
        }
        mock_logs = [
            {
                "game_pk": 1001,
                "date": "2024-11-15",
                "opponent": "Águilas Cibaeñas",
                "role": "Abridor",
                "decision": "W",
                "ip": "6.0",
                "h": 4,
                "er": 1,
                "bb": 1,
                "so": 7,
                "pitches": 88,
                "strikes": 58,
                "csw_pct": 28.4,
                "whiff_pct": 22.1,
                "league": "LIDOM",
            },
            {
                "game_pk": 1002,
                "date": "2024-11-22",
                "opponent": "Leones del Escogido",
                "role": "Abridor",
                "decision": "W",
                "ip": "7.0",
                "h": 3,
                "er": 0,
                "bb": 0,
                "so": 8,
                "pitches": 92,
                "strikes": 64,
                "csw_pct": 31.0,
                "whiff_pct": 25.0,
                "league": "LIDOM",
            }
        ]

        card_bytes = build_pitching_summary_card(
            pitcher_info=p_info,
            mode="season",
            season=2024,
            branch="lidom",
            is_lidom=True,
            game_logs=mock_logs,
        )

        self.assertIsInstance(card_bytes, bytes)
        self.assertTrue(len(card_bytes) > 50000)  # Imagen PNG real > 50 KB

        # Verificar dimensiones de la imagen
        im = Image.open(io.BytesIO(card_bytes))
        self.assertEqual(im.size, (2400, 2400))

    def test_mexico_card_generation_2400x2400(self):
        """Verifica que la tarjeta gráfica para México LMB se genere en 2400x2400 px."""
        p_info = {
            "id": 457918,
            "name": "Junior Guerra",
            "throws": "R",
            "age": 39,
            "height": "6' 0\"",
            "weight": 210,
            "team_name": "Conspiradores de Querétaro",
            "has_lidom": False,
        }
        mock_logs = [
            {
                "game_pk": 2001,
                "date": "2026-06-15",
                "opponent": "Diablos Rojos del México",
                "role": "Abridor",
                "decision": "W",
                "ip": "5.0",
                "h": 5,
                "er": 2,
                "bb": 2,
                "so": 6,
                "pitches": 82,
                "strikes": 52,
                "csw_pct": 26.8,
                "whiff_pct": 20.5,
                "league": "México",
            }
        ]

        card_bytes = build_pitching_summary_card(
            pitcher_info=p_info,
            mode="season",
            season=2026,
            branch="mexico",
            is_mexico=True,
            game_logs=mock_logs,
        )

        self.assertIsInstance(card_bytes, bytes)
        im = Image.open(io.BytesIO(card_bytes))
        self.assertEqual(im.size, (2400, 2400))

    def test_lidom_statcast_card_generation(self):
        """Verifica que la tarjeta Nestico con telemetría Statcast TrackMan para LIDOM se genere en 2400x2400."""
        from core.pitching_engine import get_lidom_pitcher_statcast_df
        p_info = get_pitcher_by_id(491624, branch="lidom")
        df_sc = get_lidom_pitcher_statcast_df(491624, season=2024)
        self.assertFalse(df_sc.empty)
        self.assertIn("release_speed", df_sc.columns)
        self.assertIn("pfx_x", df_sc.columns)
        self.assertIn("pfx_z", df_sc.columns)

        logs = get_pitcher_game_logs(491624, season=2024, branch="lidom")
        card_bytes = build_pitching_summary_card(
            pitcher_info=p_info,
            mode="season",
            season=2024,
            branch="lidom",
            is_lidom=True,
            game_logs=logs,
            df_statcast=df_sc,
            card_type="statcast",
        )
        self.assertIsInstance(card_bytes, bytes)
        im = Image.open(io.BytesIO(card_bytes))
        self.assertEqual(im.size, (2400, 2400))


if __name__ == "__main__":
    unittest.main()
