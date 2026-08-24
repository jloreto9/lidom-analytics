"""Suite de pruebas unitarias para LIDOM 360 (Motores analíticos, sabermetría y datos)."""

import unittest
import pandas as pd
import numpy as np

from core.teams import (
    TEAMS, get_all_teams, get_team_by_id, get_team_by_abbrev,
    resolve_team, get_team_color, get_team_logo
)
from core.api_client import MLBLIDOMApiClient
from core.bis_hardness import classify_batted_ball_hardness, calculate_contact_profile
from core.wpa_engine import (
    get_base_state_index, get_run_expectancy, calculate_win_expectancy,
    calculate_leverage_index, compute_play_wpa
)
from core.elo_engine import EloEngine
from core.situational import is_risp, is_bases_loaded, calculate_sabermetric_slash, get_situational_splits
from core.bullpen import compute_reliever_metrics, aggregate_team_bullpen
from core.data_loader import LIDOMDataLoader


class TestLIDOMCore(unittest.TestCase):
    """Pruebas unitarias de integridad y cálculo para LIDOM 360."""

    def test_teams_metadata(self):
        """Verifica que los 6 equipos de LIDOM estén correctamente definidos."""
        teams = get_all_teams()
        self.assertEqual(len(teams), 6)

        expected_ids = {672, 667, 671, 670, 669, 668}
        self.assertEqual(set(TEAMS.keys()), expected_ids)

        # Verificar Licey
        licey = get_team_by_id(672)
        self.assertIsNotNone(licey)
        self.assertEqual(licey["abbrev"], "LIC")
        self.assertEqual(licey["primary_color"], "#002D62")

        # Verificar Águilas
        aguilas = get_team_by_abbrev("AGU")
        self.assertIsNotNone(aguilas)
        self.assertEqual(aguilas["id"], 667)
        self.assertEqual(aguilas["primary_color"], "#FFCC00")

        # Resolver por nombre
        escogido = resolve_team("Leones del Escogido")
        self.assertIsNotNone(escogido)
        self.assertEqual(escogido["id"], 671)

    def test_bis_hardness_classification(self):
        """Valida el modelo determinístico de calidad de contacto (BIS)."""
        # Prueba con velocidad medida
        h1, _ = classify_batted_ball_hardness(launch_speed=98.5)
        self.assertEqual(h1, "Hard")

        h2, _ = classify_batted_ball_hardness(launch_speed=87.0)
        self.assertEqual(h2, "Medium")

        h3, _ = classify_batted_ball_hardness(launch_speed=72.0)
        self.assertEqual(h3, "Soft")

        # Prueba con eventos y trayectorias
        h_hr, _ = classify_batted_ball_hardness(event_type="home_run")
        self.assertEqual(h_hr, "Hard")

        h_pop, _ = classify_batted_ball_hardness(trajectory="popup")
        self.assertEqual(h_pop, "Soft")

        # Perfil de contacto
        profile = calculate_contact_profile([
            {"launch_speed": 100.0},
            {"launch_speed": 85.0},
            {"launch_speed": 70.0},
        ])
        self.assertAlmostEqual(profile["hard_pct"], 33.3, places=1)
        self.assertAlmostEqual(profile["medium_pct"], 33.3, places=1)
        self.assertAlmostEqual(profile["soft_pct"], 33.3, places=1)

    def test_wpa_and_re24(self):
        """Valida la matriz RE24, Win Expectancy y cálculo de WPA."""
        # 0 outs, bases vacías
        re_empty = get_run_expectancy(0, 0)
        self.assertAlmostEqual(re_empty, 0.481, places=3)

        # 0 outs, bases llenas (índice 7)
        re_loaded = get_run_expectancy(0, 7)
        self.assertAlmostEqual(re_loaded, 2.292, places=3)

        # Win Expectancy al inicio de juego (empate) debe estar cerca del 50%
        we_start = calculate_win_expectancy(1, False, 0, 0, 0)
        self.assertTrue(0.40 <= we_start <= 0.60)

        # Ventaja amplia en inning tardío
        we_blowout = calculate_win_expectancy(9, False, 2, 0, 5) # Local arriba por 5
        self.assertTrue(we_blowout > 0.95)

        # Leverage Index en juego empatado en el 9no
        li_high = calculate_leverage_index(9, False, 1, 4, 0)
        self.assertTrue(li_high > 1.5)

        # WPA por jugada
        play_wpa = compute_play_wpa(9, True, 2, 0, -1, 2, 0, 1, game_ended=True)
        self.assertTrue(play_wpa["wpa_batter"] > 0)
        self.assertEqual(play_wpa["wpa_batter"], -play_wpa["wpa_pitcher"])

    def test_elo_and_monte_carlo(self):
        """Verifica el cálculo de ELO y la simulación Monte Carlo."""
        engine = EloEngine()
        rankings = engine.get_power_rankings()
        self.assertEqual(len(rankings), 6)

        # Actualizar rating con victoria de Licey vs Águilas
        r_lic_before = engine.ratings[672]
        r_agu_before = engine.ratings[667]
        r_lic_after, r_agu_after = engine.update_rating(672, 667, home_score=5, away_score=2)

        self.assertTrue(r_lic_after > r_lic_before)
        self.assertTrue(r_agu_after < r_agu_before)

        # Simulación Monte Carlo (100 iteraciones para test rápido)
        mc = engine.run_monte_carlo_simulation(iterations=100)
        self.assertEqual(mc["iterations"], 100)
        self.assertEqual(len(mc["projections"]), 6)
        total_champ_pct = sum(p["champion_pct"] for p in mc["projections"])
        self.assertAlmostEqual(total_champ_pct, 100.0, delta=1.0)

    def test_situational_splits(self):
        """Verifica el cálculo de splits situacionales."""
        self.assertTrue(is_risp(get_base_state_index(False, True, False))) # 2da base
        self.assertTrue(is_risp(get_base_state_index(False, False, True))) # 3ra base
        self.assertFalse(is_risp(get_base_state_index(True, False, False))) # Solo 1ra base
        self.assertTrue(is_bases_loaded(get_base_state_index(True, True, True)))

        mock_df = pd.DataFrame({
            "event": ["single", "strikeout", "home_run", "walk", "double"],
            "hardness": ["Medium", "Soft", "Hard", "Medium", "Hard"],
            "base_state": [2, 0, 7, 1, 4],
            "leverage_index": [1.8, 0.5, 2.4, 0.9, 1.6],
            "inning": [1, 3, 5, 7, 9],
            "score_diff": [0, 1, 0, -1, 0],
        })

        splits = get_situational_splits(mock_df)
        self.assertIn("General", splits)
        self.assertIn("RISP (Posición Anotadora)", splits)
        self.assertIn("Bases Llenas", splits)
        self.assertIn("Clutch (Alto Apalancamiento LI≥1.5)", splits)

    def test_bullpen_metrics(self):
        """Verifica las métricas de corredores heredados y bullpen."""
        logs = [
            {"ip": 1.0, "inherited_runners": 2, "inherited_runners_scored": 1, "entry_leverage": 1.8, "wpa": 0.05, "er": 0, "h": 1, "bb": 0, "so": 2},
            {"ip": 1.0, "inherited_runners": 1, "inherited_runners_scored": 0, "entry_leverage": 1.2, "wpa": 0.03, "er": 0, "h": 0, "bb": 1, "so": 1},
        ]
        metrics = compute_reliever_metrics(logs)
        self.assertEqual(metrics["G"], 2)
        self.assertEqual(metrics["IP"], 2.0)
        self.assertEqual(metrics["IR"], 3)
        self.assertEqual(metrics["IRS"], 1)
        self.assertEqual(metrics["IRS_pct"], "33.3%")

    def test_data_loader(self):
        """Verifica que el DataLoader genere DataFrames consistentes."""
        loader = LIDOMDataLoader()
        df_standings = loader.get_standings_df(season=2024)
        self.assertEqual(len(df_standings), 6)
        self.assertIn("Equipo", df_standings.columns)
        self.assertIn("DIFF", df_standings.columns)

        df_hit = loader.get_hitting_leaderboard(season=2024)
        self.assertFalse(df_hit.empty)
        self.assertIn("wOBA", df_hit.columns)

        df_pitch = loader.get_pitching_leaderboard(season=2024)
        self.assertFalse(df_pitch.empty)
        self.assertIn("ERA", df_pitch.columns)

    def test_supabase_client_and_schema(self):
        """Valida que el cliente Supabase maneje credenciales y fallbacks de manera segura."""
        from core.supabase_client import get_supabase_credentials, is_supabase_connected, init_supabase

        # Validar que no lance excepciones al inicializar
        client = init_supabase()
        is_conn = is_supabase_connected()
        self.assertIsInstance(is_conn, bool)

    def test_versus_pool_and_h2h(self):
        """Valida la generación del pool de jugadores, percentiles y tabla H2H para Matchup 360."""
        from views.versus import build_h2h_table, RADAR_METRICS_BAT, RADAR_METRICS_PIT, determine_winner
        loader = LIDOMDataLoader()

        # Bateadores
        df_bat = loader.get_versus_player_pool(season=2024, role="Bateadores")
        self.assertFalse(df_bat.empty)
        self.assertIn("P_wOBA", df_bat.columns)
        self.assertIn("P_wRC+", df_bat.columns)
        self.assertIn("Headshot", df_bat.columns)

        p1_bat = df_bat.iloc[0]
        p2_bat = df_bat.iloc[1] if len(df_bat) > 1 else df_bat.iloc[0]
        h2h_bat = build_h2h_table(p1_bat, p2_bat, is_batter=True)
        self.assertFalse(h2h_bat.empty)
        self.assertIn("Ventaja / Ganador", h2h_bat.columns)

        # Lanzadores
        df_pit = loader.get_versus_player_pool(season=2024, role="Lanzadores")
        self.assertFalse(df_pit.empty)
        self.assertIn("P_ERA", df_pit.columns)
        self.assertIn("P_FIP", df_pit.columns)

        p1_pit = df_pit.iloc[0]
        p2_pit = df_pit.iloc[1] if len(df_pit) > 1 else df_pit.iloc[0]
        h2h_pit = build_h2h_table(p1_pit, p2_pit, is_batter=False)
        self.assertFalse(h2h_pit.empty)
        self.assertIn("Ventaja / Ganador", h2h_pit.columns)

        # Generación de Imagen PNG
        from views.versus import build_matchup_image
        png_bytes = build_matchup_image(p1_bat, p2_bat, is_batter=True, df_h2h=h2h_bat, season=2024)
        self.assertIsInstance(png_bytes, bytes)
        self.assertTrue(len(png_bytes) > 1000)
        self.assertTrue(png_bytes.startswith(b"\x89PNG\r\n\x1a\n"))

    def test_lineup_engine(self):
        """Valida el motor de lineups, cálculo de Base Runs y optimización de Tom Tango."""
        from core.lineup_engine import LineupEngine
        loader = LIDOMDataLoader()
        pool = loader.get_versus_player_pool(season=2024, role="Bateadores")
        self.assertFalse(pool.empty)

        engine = LineupEngine(season=2024)

        # Probar los 6 equipos
        for team_code in ["LIC", "AGU", "ESC", "GIG", "EST", "TOR"]:
            df_lineup = engine.get_preset_lineup(team_code, pool)
            self.assertEqual(len(df_lineup), 9)
            # Validar que los 9 jugadores sean distintos
            self.assertEqual(df_lineup["Name"].nunique(), 9)

            metrics = engine.calculate_expected_runs(df_lineup)
            self.assertTrue(metrics["runs_per_game"] > 1.5)
            self.assertTrue(metrics["runs_per_season"] > 75.0)
            self.assertEqual(len(metrics["slot_contributions"]), 9)

            df_opt, curr_m, opt_m = engine.optimize_lineup(df_lineup)
            self.assertEqual(len(df_opt), 9)
            self.assertEqual(list(df_opt["Slot"]), list(range(1, 10)))
            self.assertTrue(opt_m["runs_per_game"] > 0)


if __name__ == "__main__":
    unittest.main()
