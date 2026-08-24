"""Motor de Ratings ELO y Simulación Monte Carlo de Playoffs para LIDOM."""

import math
import random
from typing import Dict, Any, List, Tuple, Optional
from core.teams import TEAMS, get_all_teams

HOME_ADVANTAGE_ELO = 24.0
DEFAULT_K_FACTOR = 24.0
BASE_ELO = 1500.0


class EloEngine:
    """Motor para calcular y proyectar ratings ELO y simular temporadas de LIDOM."""

    def __init__(self, k_factor: float = DEFAULT_K_FACTOR, home_adv: float = HOME_ADVANTAGE_ELO):
        self.k_factor = k_factor
        self.home_adv = home_adv
        self.ratings: Dict[int, float] = {
            # Inicialización basada en potencia histórica y campeonatos recientes
            672: 1530.0,  # Tigres del Licey
            667: 1515.0,  # Águilas Cibaeñas
            671: 1510.0,  # Leones del Escogido
            669: 1505.0,  # Estrellas Orientales
            670: 1475.0,  # Gigantes del Cibao
            668: 1465.0,  # Toros del Este
        }

    def win_probability(self, elo_home: float, elo_away: float) -> float:
        """Calcula la probabilidad de victoria del equipo local."""
        diff = (elo_home + self.home_adv) - elo_away
        return 1.0 / (1.0 + math.pow(10.0, -diff / 400.0))

    def update_rating(
        self,
        home_id: int,
        away_id: int,
        home_score: int,
        away_score: int,
    ) -> Tuple[float, float]:
        """Actualiza los ratings ELO de ambos equipos tras un juego finalizado."""
        r_home = self.ratings.get(home_id, BASE_ELO)
        r_away = self.ratings.get(away_id, BASE_ELO)

        p_home = self.win_probability(r_home, r_away)
        actual_home = 1.0 if home_score > away_score else (0.5 if home_score == away_score else 0.0)

        # Multiplicador por margen de victoria (MOV)
        score_diff = abs(home_score - away_score)
        mov_mult = math.log(max(score_diff, 1) + 1.0) * (2.2 / ((r_home - r_away if actual_home == 1 else r_away - r_home) * 0.001 + 2.2))
        mov_mult = max(0.5, min(mov_mult, 2.5))

        delta = self.k_factor * mov_mult * (actual_home - p_home)
        self.ratings[home_id] = round(r_home + delta, 1)
        self.ratings[away_id] = round(r_away - delta, 1)

        return self.ratings[home_id], self.ratings[away_id]

    def get_power_rankings(self) -> List[Dict[str, Any]]:
        """Retorna los Power Rankings ordenados por rating ELO actual."""
        rankings = []
        for team in get_all_teams():
            t_id = team["id"]
            rating = self.ratings.get(t_id, BASE_ELO)
            rankings.append({
                "team_id": t_id,
                "name": team["name"],
                "short_name": team["short_name"],
                "abbrev": team["abbrev"],
                "elo": rating,
                "primary_color": team["primary_color"],
                "logo_url": team["logo_url"],
            })
        rankings.sort(key=lambda x: x["elo"], reverse=True)
        for i, r in enumerate(rankings):
            r["rank"] = i + 1
        return rankings

    def simulate_game(self, home_id: int, away_id: int, custom_ratings: Dict[int, float]) -> int:
        """Simula un juego individual retornando el ID del equipo ganador."""
        r_h = custom_ratings.get(home_id, BASE_ELO)
        r_a = custom_ratings.get(away_id, BASE_ELO)
        prob_home = self.win_probability(r_h, r_a)
        return home_id if random.random() < prob_home else away_id

    def run_monte_carlo_simulation(
        self,
        current_standings: Optional[Dict[int, Dict[str, int]]] = None,
        iterations: int = 5000,
    ) -> Dict[str, Any]:
        """
        Simula el torneo completo de LIDOM:
        1. Serie Regular restante (Clasifican Top 4 al Round Robin).
        2. Round Robin de 18 juegos (Clasifican Top 2 a la Serie Final).
        3. Serie Final al mejor de 7 (Campeón de LIDOM).
        """
        team_ids = list(TEAMS.keys())
        results = {
            t_id: {
                "round_robin_count": 0,
                "finals_count": 0,
                "champion_count": 0,
                "avg_wins": 0.0,
            }
            for t_id in team_ids
        }

        # Matriz de partidos por jugar o simulados
        for _ in range(iterations):
            ratings_copy = dict(self.ratings)
            wins_sim = {t: (current_standings[t]["wins"] if current_standings and t in current_standings else 0) for t in team_ids}

            # Simular partidos de serie regular (50 juegos por equipo = 150 juegos total)
            games_played_each = {t: (current_standings[t]["games"] if current_standings and t in current_standings else 0) for t in team_ids}
            for i in range(len(team_ids)):
                for j in range(i + 1, len(team_ids)):
                    t1, t2 = team_ids[i], team_ids[j]
                    # Cada par juega 10 juegos en regular (5 local/5 visitante)
                    needed_t1_h = max(0, 5 - (games_played_each[t1] // 10))
                    for _ in range(needed_t1_h):
                        winner = self.simulate_game(t1, t2, ratings_copy)
                        wins_sim[winner] += 1
                    needed_t2_h = max(0, 5 - (games_played_each[t2] // 10))
                    for _ in range(needed_t2_h):
                        winner = self.simulate_game(t2, t1, ratings_copy)
                        wins_sim[winner] += 1

            # Clasificación al Round Robin (Top 4)
            sorted_regular = sorted(team_ids, key=lambda t: (wins_sim[t], random.random()), reverse=True)
            top_4 = sorted_regular[:4]
            for t in top_4:
                results[t]["round_robin_count"] += 1

            # Round Robin: 18 juegos entre los 4 equipos (6 juegos vs cada rival, 3 local/3 visita)
            rr_wins = {t: 0 for t in top_4}
            for i in range(4):
                for j in range(i + 1, 4):
                    t1, t2 = top_4[i], top_4[j]
                    for _ in range(3):
                        w = self.simulate_game(t1, t2, ratings_copy)
                        rr_wins[w] += 1
                    for _ in range(3):
                        w = self.simulate_game(t2, t1, ratings_copy)
                        rr_wins[w] += 1

            sorted_rr = sorted(top_4, key=lambda t: (rr_wins[t], random.random()), reverse=True)
            finalists = sorted_rr[:2]
            for t in finalists:
                results[t]["finals_count"] += 1

            # Serie Final: Al mejor de 7 (primer equipo con 4 victorias)
            f1, f2 = finalists[0], finalists[1]
            f1_wins, f2_wins = 0, 0
            # Formato 2-2-1-1-1
            home_sequence = [f1, f1, f2, f2, f1, f2, f1]
            for g_idx in range(7):
                h = home_sequence[g_idx]
                a = f2 if h == f1 else f1
                w = self.simulate_game(h, a, ratings_copy)
                if w == f1:
                    f1_wins += 1
                else:
                    f2_wins += 1
                if f1_wins == 4 or f2_wins == 4:
                    break

            champion = f1 if f1_wins == 4 else f2
            results[champion]["champion_count"] += 1

        # Consolidar porcentajes
        prob_summary = []
        for t_id in team_ids:
            team_meta = TEAMS[t_id]
            prob_summary.append({
                "team_id": t_id,
                "name": team_meta["name"],
                "short_name": team_meta["short_name"],
                "abbrev": team_meta["abbrev"],
                "primary_color": team_meta["primary_color"],
                "logo_url": team_meta["logo_url"],
                "round_robin_pct": round((results[t_id]["round_robin_count"] / iterations) * 100, 1),
                "finals_pct": round((results[t_id]["finals_count"] / iterations) * 100, 1),
                "champion_pct": round((results[t_id]["champion_count"] / iterations) * 100, 1),
            })

        prob_summary.sort(key=lambda x: x["champion_pct"], reverse=True)
        return {
            "iterations": iterations,
            "projections": prob_summary,
        }
