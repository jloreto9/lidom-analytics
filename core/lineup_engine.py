"""Motor Sabermétrico de Analítica y Optimización de Lineups para LIDOM (Base Runs & Tango Lineup Theory)."""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Tuple, Optional

from core.teams import get_team_by_abbrev


# ── Factores de Ponderación de Turnos al Bate por Slot (50 Juegos LIDOM) ──────
# Slot 1 promedia ~4.67 PA/G hasta Slot 9 con ~3.63 PA/G en una temporada de 50 juegos.
SLOT_PA_WEIGHTS = {
    1: 4.67,
    2: 4.54,
    3: 4.41,
    4: 4.28,
    5: 4.15,
    6: 4.02,
    7: 3.89,
    8: 3.76,
    9: 3.63,
}

# Ponderadores de impacto sabermétrico por posición en el orden (Tom Tango's The Book)
# Refleja el apalancamiento de situaciones de base y outs al tomar turno.
TANGO_SLOT_LEVERAGE = {
    1: {"obp_weight": 1.45, "slg_weight": 0.80, "woba_mult": 1.05, "role": "Leadoff / Embasador Élite"},
    2: {"obp_weight": 1.30, "slg_weight": 1.25, "woba_mult": 1.15, "role": "Mejor Bateador Integral"},
    3: {"obp_weight": 1.05, "slg_weight": 1.10, "woba_mult": 1.00, "role": "Contacto + Poder"},
    4: {"obp_weight": 1.00, "slg_weight": 1.40, "woba_mult": 1.12, "role": "Cleanup / Productor Principal"},
    5: {"obp_weight": 0.95, "slg_weight": 1.20, "woba_mult": 1.02, "role": "Segundo Cleanup / Poder"},
    6: {"obp_weight": 0.90, "slg_weight": 0.95, "woba_mult": 0.94, "role": "Producción Secundaria"},
    7: {"obp_weight": 0.85, "slg_weight": 0.85, "woba_mult": 0.88, "role": "Fondo del Orden"},
    8: {"obp_weight": 0.80, "slg_weight": 0.80, "woba_mult": 0.84, "role": "Bateador de Menor Producción"},
    9: {"obp_weight": 1.15, "slg_weight": 0.75, "woba_mult": 0.92, "role": "Segundo Leadoff / Mesa para 1-2-3"},
}

# Lineups canónicos representativos por franquicia
DEFAULT_PRESET_LINEUPS: Dict[str, List[Dict[str, Any]]] = {
    "LIC": [
        {"slot": 1, "name": "Emilio Bonifacio", "pos": "CF", "bats": "A", "role_desc": "Capitán / Velocidad"},
        {"slot": 2, "name": "Cristhian Adames", "pos": "3B", "bats": "A", "role_desc": "Contacto / Disciplina"},
        {"slot": 3, "name": "Ramón Hernández", "pos": "1B", "bats": "D", "role_desc": "Poder Extralimite"},
        {"slot": 4, "name": "Jorge Alfaro", "pos": "DH", "bats": "D", "role_desc": "Fuerza / Cleanup"},
        {"slot": 5, "name": "Michael De La Cruz", "pos": "C", "bats": "A", "role_desc": "Receptor / OBP"},
        {"slot": 6, "name": "Sergio Alcántara", "pos": "SS", "bats": "A", "role_desc": "Guante / Conteo"},
        {"slot": 7, "name": "Dawel Lugo", "pos": "2B", "bats": "D", "role_desc": "Contacto"},
        {"slot": 8, "name": "Luis Barrera", "pos": "LF", "bats": "Z", "role_desc": "Jardinero / Velocidad"},
        {"slot": 9, "name": "Michael De León", "pos": "RF", "bats": "A", "role_desc": "Defensa / Mesa"},
    ],
    "AGU": [
        {"slot": 1, "name": "Yairo Muñoz", "pos": "3B", "bats": "D", "role_desc": "Bateador de Promedio"},
        {"slot": 2, "name": "Starlin Castro", "pos": "2B", "bats": "D", "role_desc": "Veteranía / Contacto"},
        {"slot": 3, "name": "Jerar Encarnación", "pos": "RF", "bats": "D", "role_desc": "Poder Masivo"},
        {"slot": 4, "name": "Alexander Canario", "pos": "LF", "bats": "D", "role_desc": "Extralimite / Productor"},
        {"slot": 5, "name": "Juan Lagares", "pos": "CF", "bats": "D", "role_desc": "Jardinero / Contacto"},
        {"slot": 6, "name": "Jonathan Villar", "pos": "DH", "bats": "A", "role_desc": "Velocidad / Poder"},
        {"slot": 7, "name": "Erick Mejía", "pos": "1B", "bats": "A", "role_desc": "Versatilidad"},
        {"slot": 8, "name": "Pedro Severino", "pos": "C", "bats": "D", "role_desc": "Receptor Defensivo"},
        {"slot": 9, "name": "Ramón Torres", "pos": "SS", "bats": "A", "role_desc": "Segundo Leadoff"},
    ],
    "ESC": [
        {"slot": 1, "name": "Junior Lake", "pos": "LF", "bats": "D", "role_desc": "OBP / Extrabases"},
        {"slot": 2, "name": "Erik González", "pos": "SS", "bats": "D", "role_desc": "Bateador Completo"},
        {"slot": 3, "name": "Franchy Cordero", "pos": "RF", "bats": "Z", "role_desc": "Poder Zurdo"},
        {"slot": 4, "name": "Franmil Reyes", "pos": "DH", "bats": "D", "role_desc": "Poder Élite LIDOM"},
        {"slot": 5, "name": "Héctor Rodríguez", "pos": "CF", "bats": "Z", "role_desc": "Novato / Velocidad"},
        {"slot": 6, "name": "Aderlin Rodríguez", "pos": "1B", "bats": "D", "role_desc": "Fuerza / Impulsador"},
        {"slot": 7, "name": "Junior Caminero", "pos": "3B", "bats": "D", "role_desc": "Prospecto Élite"},
        {"slot": 8, "name": "Pedro Florimón", "pos": "2B", "bats": "A", "role_desc": "Veterano / Guante"},
        {"slot": 9, "name": "Freili Encarnación", "pos": "C", "bats": "D", "role_desc": "Mascota / Bloqueo"},
    ],
    "GIG": [
        {"slot": 1, "name": "Kelvin Gutiérrez", "pos": "3B", "bats": "D", "role_desc": "Líder de OBP"},
        {"slot": 2, "name": "Henry Urrutia", "pos": "DH", "bats": "Z", "role_desc": "Bate Puro / Extrabases"},
        {"slot": 3, "name": "Marcell Ozuna", "pos": "LF", "bats": "D", "role_desc": "Slugger Élite"},
        {"slot": 4, "name": "Carlos Peguero", "pos": "RF", "bats": "Z", "role_desc": "Jonronero Histórico"},
        {"slot": 5, "name": "Hanser Alberto", "pos": "2B", "bats": "D", "role_desc": "Máquina de Hits"},
        {"slot": 6, "name": "Edwin Espinal", "pos": "1B", "bats": "D", "role_desc": "Impulsadas Oportunas"},
        {"slot": 7, "name": "José Sirí", "pos": "CF", "bats": "D", "role_desc": "Poder & Velocidad"},
        {"slot": 8, "name": "Carlos Paulino", "pos": "C", "bats": "D", "role_desc": "Receptor / Manejo de Pitcheo"},
        {"slot": 9, "name": "Richard Ureña", "pos": "SS", "bats": "A", "role_desc": "Ambidiestro / Enlace"},
    ],
    "EST": [
        {"slot": 1, "name": "Raimel Tapia", "pos": "RF", "bats": "Z", "role_desc": "Contacto / Piernas"},
        {"slot": 2, "name": "Robinson Canó", "pos": "2B", "bats": "Z", "role_desc": "Leyenda / Disciplina"},
        {"slot": 3, "name": "Vidal Bruján", "pos": "CF", "bats": "A", "role_desc": "Velocidad / OBP"},
        {"slot": 4, "name": "Miguel Sanó", "pos": "1B", "bats": "D", "role_desc": "Poder Auténtico"},
        {"slot": 5, "name": "Lewin Díaz", "pos": "DH", "bats": "Z", "role_desc": "Extrabases / Guante"},
        {"slot": 6, "name": "Christian Bethancourt", "pos": "C", "bats": "D", "role_desc": "Fuerza / Brazo"},
        {"slot": 7, "name": "Eguy Rosario", "pos": "3B", "bats": "D", "role_desc": "Extralimite / Juventud"},
        {"slot": 8, "name": "José Tena", "pos": "SS", "bats": "Z", "role_desc": "Infielder Dinámico"},
        {"slot": 9, "name": "Junior Lake", "pos": "LF", "bats": "D", "role_desc": "Mesa de Ataque"},
    ],
    "TOR": [
        {"slot": 1, "name": "Ronny Simon", "pos": "2B", "bats": "A", "role_desc": "MVP / Embasado"},
        {"slot": 2, "name": "Yamaico Navarro", "pos": "DH", "bats": "D", "role_desc": "Ojo Clínico / BB"},
        {"slot": 3, "name": "Jeimer Candelario", "pos": "3B", "bats": "A", "role_desc": "Bateador de Línea"},
        {"slot": 4, "name": "Eloy Jiménez", "pos": "LF", "bats": "D", "role_desc": "Fuerza Bruta"},
        {"slot": 5, "name": "Cristhian Adames", "pos": "SS", "bats": "A", "role_desc": "Poder Oportuno"},
        {"slot": 6, "name": "Webster Rivas", "pos": "C", "bats": "D", "role_desc": "Receptor / Contacto"},
        {"slot": 7, "name": "Bryan De La Cruz", "pos": "RF", "bats": "D", "role_desc": "Extrabases"},
        {"slot": 8, "name": "Yairo Muñoz", "pos": "1B", "bats": "D", "role_desc": "Contacto"},
        {"slot": 9, "name": "Luis Liberato", "pos": "CF", "bats": "Z", "role_desc": "Velocidad / Segundo Leadoff"},
    ],
}


class LineupEngine:
    """Motor de cálculo y optimización de alineaciones sabermétricas para LIDOM."""

    def __init__(self, season: int = 2024):
        self.season = season

    def get_preset_lineup(self, team_abbrev: str, pool_df: pd.DataFrame) -> pd.DataFrame:
        """Construye el DataFrame de la alineación titular con estadísticas reales del pool."""
        team_abbrev = team_abbrev.upper()
        presets = DEFAULT_PRESET_LINEUPS.get(team_abbrev, DEFAULT_PRESET_LINEUPS["LIC"])

        rows = []
        used_names = set()

        for p in presets:
            slot = p["slot"]
            p_name = p["name"]

            # 1. Buscar coincidencia exacta por nombre
            match = pool_df[(pool_df["Name"] == p_name) & (~pool_df["Name"].isin(used_names))]
            
            # 2. Si no hay coincidencia exacta o ya se usó, buscar por equipo no usado
            if match.empty:
                team_matches = pool_df[(pool_df["Team"] == team_abbrev) & (~pool_df["Name"].isin(used_names))]
                if not team_matches.empty:
                    player_data = team_matches.iloc[0].to_dict()
                else:
                    rem = pool_df[~pool_df["Name"].isin(used_names)]
                    player_data = rem.iloc[0].to_dict() if not rem.empty else pool_df.iloc[0].to_dict()
            else:
                player_data = match.iloc[0].to_dict()

            used_names.add(player_data["Name"])
            player_data["Slot"] = slot
            player_data["Bats"] = p.get("bats", "D")
            player_data["Role_Desc"] = p.get("role_desc", "Titular")
            player_data["Assigned_Pos"] = p.get("pos", player_data.get("Pos", "UTIL"))
            rows.append(player_data)

        df_lineup = pd.DataFrame(rows)
        return df_lineup

    def calculate_expected_runs(self, lineup_df: pd.DataFrame) -> Dict[str, Any]:
        """Calcula las Carreras Esperadas por Juego (R/G) y por temporada (50 juegos) usando BaseRuns ponderado."""
        if len(lineup_df) < 9:
            return {"runs_per_game": 0.0, "runs_per_season": 0.0, "woba_team": 0.0, "slot_contributions": []}

        slot_contributions = []
        total_runs_game = 0.0
        weighted_woba_sum = 0.0
        total_pa_weights = sum(SLOT_PA_WEIGHTS.values())

        for idx, (_, player) in enumerate(lineup_df.iloc[:9].iterrows()):
            slot = idx + 1
            pa_weight = SLOT_PA_WEIGHTS[slot]
            tango_cfg = TANGO_SLOT_LEVERAGE[slot]

            # Extraer métricas numéricas
            woba_val = float(player.get("_woba_num", player.get("wOBA", 0.320)))
            obp_val = float(player.get("_obp_num", player.get("OBP", 0.320)))
            slg_val = float(player.get("_slg_num", player.get("SLG", 0.390)))
            hard_val = float(str(player.get("Hard%", 35.0)).replace("%", ""))

            # Base Runs simplificado para el bateador en su slot
            # Factor A (Embasado), Factor B (Avance de corredores), Factor C (Outs), Factor D (Jonrones)
            # Producción de carreras esperada por PA ajustada a LIDOM
            slot_rc_per_pa = (
                (obp_val * tango_cfg["obp_weight"]) * 0.48 +
                (slg_val * tango_cfg["slg_weight"]) * 0.32 +
                ((hard_val / 100.0) * 0.12)
            ) * tango_cfg["woba_mult"]

            slot_runs_game = slot_rc_per_pa * (pa_weight / 4.0)
            total_runs_game += slot_runs_game
            weighted_woba_sum += (woba_val * pa_weight)

            slot_contributions.append({
                "Slot": slot,
                "Name": player["Name"],
                "Pos": player.get("Assigned_Pos", player.get("Pos", "UTIL")),
                "Bats": player.get("Bats", "D"),
                "PA_Game": pa_weight,
                "PA_Season": round(pa_weight * 50, 1),
                "wOBA": f"{woba_val:.3f}".lstrip("0") if woba_val < 1.0 else f"{woba_val:.3f}",
                "OBP": f"{obp_val:.3f}".lstrip("0") if obp_val < 1.0 else f"{obp_val:.3f}",
                "SLG": f"{slg_val:.3f}".lstrip("0") if slg_val < 1.0 else f"{slg_val:.3f}",
                "wRC+": int(player.get("wRC+", 100)),
                "Runs_Contributed_Game": round(slot_runs_game, 2),
                "Runs_Contributed_Season": round(slot_runs_game * 50, 1),
                "Tango_Role": tango_cfg["role"],
            })

        # Sinergia de secuencia (protección y balance zurdo/derecho)
        platoon_switches = 0
        bats_list = [p.get("Bats", "D") for _, p in lineup_df.iloc[:9].iterrows()]
        for i in range(len(bats_list) - 1):
            if bats_list[i] != bats_list[i + 1] or "A" in (bats_list[i], bats_list[i + 1]):
                platoon_switches += 1
        platoon_bonus = (platoon_switches / 8.0) * 0.15  # Hasta +0.15 R/G por evitar racimos de mismo lado

        final_r_game = round(total_runs_game + platoon_bonus, 2)
        final_r_season = round(final_r_game * 50, 1)
        team_woba = round(weighted_woba_sum / total_pa_weights, 3)

        return {
            "runs_per_game": final_r_game,
            "runs_per_season": final_r_season,
            "team_woba": f"{team_woba:.3f}".lstrip("0"),
            "platoon_balance_score": round((platoon_switches / 8.0) * 100),
            "slot_contributions": slot_contributions,
        }

    def optimize_lineup(self, current_lineup_df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any], Dict[str, Any]]:
        """Aplica la teoría de optimización sabermétrica de Tom Tango para ordenar los 9 bateadores."""
        df_9 = current_lineup_df.iloc[:9].copy()
        
        # Asignar claves de ordenamiento
        df_9["_woba_f"] = df_9["wOBA"].apply(lambda x: float(str(x).replace("%", "")))
        df_9["_obp_f"] = df_9["OBP"].apply(lambda x: float(str(x).replace("%", "")))
        df_9["_slg_f"] = df_9["SLG"].apply(lambda x: float(str(x).replace("%", "")))
        df_9["_iso_f"] = df_9["_slg_f"] - df_9["_obp_f"]

        pool_indices = set(df_9.index)
        optimal_slots = {}

        # 1. Slot #2: El mejor bateador integral del equipo (Mayor wOBA)
        best_woba_idx = df_9.loc[list(pool_indices), "_woba_f"].idxmax()
        optimal_slots[2] = df_9.loc[best_woba_idx].to_dict()
        pool_indices.remove(best_woba_idx)

        # 2. Slot #1: El mejor OBP entre los bateadores de élite restantes
        best_obp_idx = df_9.loc[list(pool_indices), "_obp_f"].idxmax()
        optimal_slots[1] = df_9.loc[best_obp_idx].to_dict()
        pool_indices.remove(best_obp_idx)

        # 3. Slot #4: El bateador de mayor poder aislado (ISO / SLG)
        best_iso_idx = df_9.loc[list(pool_indices), "_iso_f"].idxmax()
        optimal_slots[4] = df_9.loc[best_iso_idx].to_dict()
        pool_indices.remove(best_iso_idx)

        # 4. Slot #5: Segundo bateador de mayor poder
        second_power_idx = df_9.loc[list(pool_indices), "_slg_f"].idxmax()
        optimal_slots[5] = df_9.loc[second_power_idx].to_dict()
        pool_indices.remove(second_power_idx)

        # 5. Slot #3: Bateador de alto contacto y promedio remanente
        best_hit_idx = df_9.loc[list(pool_indices), "_woba_f"].idxmax()
        optimal_slots[3] = df_9.loc[best_hit_idx].to_dict()
        pool_indices.remove(best_hit_idx)

        # 6. Slot #9: Segundo Leadoff (Mejor OBP de los 4 restantes para enlazar con 1-2-3)
        second_leadoff_idx = df_9.loc[list(pool_indices), "_obp_f"].idxmax()
        optimal_slots[9] = df_9.loc[second_leadoff_idx].to_dict()
        pool_indices.remove(second_leadoff_idx)

        # 7. Slots #6, #7, #8: Orden descendente de wOBA
        remaining_sorted = df_9.loc[list(pool_indices)].sort_values("_woba_f", ascending=False).index.tolist()
        optimal_slots[6] = df_9.loc[remaining_sorted[0]].to_dict()
        optimal_slots[7] = df_9.loc[remaining_sorted[1]].to_dict()
        optimal_slots[8] = df_9.loc[remaining_sorted[2]].to_dict()

        # Armar DataFrame ordenado de 1 a 9
        opt_rows = []
        for s in range(1, 10):
            p_data = optimal_slots[s]
            p_data["Slot"] = s
            p_data["Optimal_Role"] = TANGO_SLOT_LEVERAGE[s]["role"]
            opt_rows.append(p_data)

        df_optimized = pd.DataFrame(opt_rows)

        # Métricas de comparación
        curr_metrics = self.calculate_expected_runs(df_9)
        opt_metrics = self.calculate_expected_runs(df_optimized)

        return df_optimized, curr_metrics, opt_metrics
