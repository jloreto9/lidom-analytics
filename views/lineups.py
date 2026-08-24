"""Vista de Analítica y Optimización de Lineups para LIDOM (Base Runs, Tracker & Tango Theory)."""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from typing import Dict, Any, List

from core.data_loader import LIDOMDataLoader
from core.lineup_engine import LineupEngine, TANGO_SLOT_LEVERAGE, SLOT_PA_WEIGHTS
from core.teams import TEAMS, get_team_by_id, get_team_by_abbrev


def format_rate(val: Any) -> str:
    """Formatea métricas de bateo con punto inicial sin cero (ej: .325)."""
    if val is None or pd.isna(val):
        return "—"
    try:
        s = str(val).strip()
        f = float(s.replace("%", ""))
        if 0.0 <= f < 1.0:
            return f"{f:.3f}".lstrip("0")
        elif f >= 1.0:
            return f"{f:.3f}" if ("." in s or isinstance(val, float)) else s
        return s
    except Exception:
        return str(val)


def build_lineup_production_chart(current_contributions: List[Dict[str, Any]], opt_contributions: List[Dict[str, Any]], team_name: str) -> go.Figure:
    """Crea un gráfico de barras comparativo de producción esperada de carreras por slot."""
    slots = [f"Slot #{c['Slot']}" for c in current_contributions]
    curr_runs = [c["Runs_Contributed_Season"] for c in current_contributions]
    opt_runs = [c["Runs_Contributed_Season"] for c in opt_contributions]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=slots,
        y=curr_runs,
        name="Alineación Actual",
        marker=dict(color="#38BDF8", opacity=0.85),
        text=[f"{r:.1f} R" for r in curr_runs],
        textposition="auto",
    ))

    fig.add_trace(go.Bar(
        x=slots,
        y=opt_runs,
        name="Alineación Óptima (Tango)",
        marker=dict(color="#FF3B56", opacity=0.85),
        text=[f"{r:.1f} R" for r in opt_runs],
        textposition="auto",
    ))

    fig.update_layout(
        title=f"Aporte de Carreras Proyectadas por Slot (50 Juegos) — {team_name}",
        paper_bgcolor="#070C1A",
        plot_bgcolor="#0D152B",
        font=dict(color="#E2E8F0", family="Outfit, sans-serif"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=40, r=40, t=60, b=40),
        height=380,
        barmode="group",
        xaxis=dict(gridcolor="rgba(255,255,255,0.05)", title="Posición en el Orden"),
        yaxis=dict(gridcolor="rgba(255,255,255,0.08)", title="Carreras Aportadas (50G)"),
    )
    return fig


def build_lineup_h2h_trajectory(df1_contrib: List[Dict[str, Any]], df2_contrib: List[Dict[str, Any]], t1_name: str, t2_name: str) -> go.Figure:
    """Gráfico de trayectoria acumulativa de producción de carreras slot por slot."""
    slots = [f"Slot #{i}" for i in range(1, 10)]
    c1_cum = np.cumsum([c["Runs_Contributed_Season"] for c in df1_contrib])
    c2_cum = np.cumsum([c["Runs_Contributed_Season"] for c in df2_contrib])

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=slots,
        y=c1_cum,
        mode="lines+markers",
        name=f"🔴 {t1_name}",
        line=dict(color="#FF3B56", width=3.5),
        marker=dict(size=8, color="#FF3B56"),
    ))

    fig.add_trace(go.Scatter(
        x=slots,
        y=c2_cum,
        mode="lines+markers",
        name=f"🔵 {t2_name}",
        line=dict(color="#38BDF8", width=3.5),
        marker=dict(size=8, color="#38BDF8"),
    ))

    fig.update_layout(
        title="Curva Acumulativa de Producción de Carreras en 50 Juegos",
        paper_bgcolor="#070C1A",
        plot_bgcolor="#0D152B",
        font=dict(color="#E2E8F0", family="Outfit, sans-serif"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=40, r=40, t=60, b=40),
        height=380,
        xaxis=dict(gridcolor="rgba(255,255,255,0.05)", title="Posición en el Orden al Bate"),
        yaxis=dict(gridcolor="rgba(255,255,255,0.08)", title="Carreras Acumuladas"),
    )
    return fig


def render_lineups_view(season: int = 2024) -> None:
    """Renderiza la vista completa de Analítica y Optimización de Lineups con 3 pestañas integrales."""
    st.markdown("""
    <div style="text-align: center; margin-bottom: 20px;">
        <h1 style="font-size: 2.2rem; font-weight: 800; background: linear-gradient(135deg, #FF3B56 0%, #38BDF8 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 5px;">
            📋 Laboratorio de Lineups & Optimización Sabermétrica
        </h1>
        <p style="color: #94A3B8; font-size: 0.95rem; max-width: 850px; margin: 0 auto;">
            Modelado de carreras esperadas (<span style="color: #38BDF8;">R/G</span>) con <b>Base Runs</b>, optimizador 1-9 de <b>Tom Tango (The Book)</b>, tracker de alineaciones más repetidas y análisis de rendimiento por turno al bate.
        </p>
    </div>
    """, unsafe_allow_html=True)

    loader = LIDOMDataLoader()
    engine = LineupEngine(season=season)

    # 1. Cargar Pool de Bateadores
    with st.spinner("Cargando estadísticas de bateadores para lineups..."):
        pool_df = loader.get_versus_player_pool(season=season, role="Bateadores")

    if pool_df.empty:
        st.error("No se pudieron cargar los datos de jugadores para construir las alineaciones.")
        return

    team_options = {meta["name"]: meta["abbrev"] for meta in TEAMS.values()}

    # 3 PESTAÑAS PRINCIPALES
    tab_sim, tab_tracker, tab_slots = st.tabs([
        "🧪 Simulador & Optimizador de Tango",
        "🌟 Tracker de Lineups Más Repetidos",
        "📊 Matriz de Calor & Aporte por Turno",
    ])

    # =========================================================================
    # TAB 1: SIMULADOR & OPTIMIZADOR TANGO
    # =========================================================================
    with tab_sim:
        col_t1, col_mode = st.columns([1, 1])

        with col_t1:
            sel_team_name = st.selectbox("🏟️ Seleccionar Franquicia LIDOM:", list(team_options.keys()), index=0, key="sim_team_sel")
            team_abbrev = team_options[sel_team_name]
            team_meta = get_team_by_abbrev(team_abbrev) or {}

        with col_mode:
            lineup_mode = st.radio(
                "⚙️ Modalidad de Alineación:",
                ["🚀 Alineación Titular Oficial (Preset)", "🛠️ Constructor Personalizado (Custom 1-9)"],
                horizontal=True,
                key="sim_lineup_mode"
            )

        if "Preset" in lineup_mode:
            df_current_lineup = engine.get_preset_lineup(team_abbrev, pool_df)
        else:
            st.info("💡 Selecciona a los 9 bateadores para cada posición del orden al bate:")
            team_players = pool_df[pool_df["Team"] == team_abbrev]
            if len(team_players) < 9:
                team_players = pool_df

            player_names = team_players["Name"].tolist()
            custom_rows = []
            c_cols = st.columns(3)
            for s in range(1, 10):
                with c_cols[(s - 1) % 3]:
                    picked_name = st.selectbox(f"Slot #{s}:", player_names, index=(s - 1) % len(player_names), key=f"slot_pick_{s}")
                    p_match = pool_df[pool_df["Name"] == picked_name].iloc[0].to_dict()
                    p_match["Slot"] = s
                    p_match["Bats"] = "D" if s % 2 == 0 else "Z"
                    p_match["Assigned_Pos"] = p_match.get("Pos", "UTIL")
                    custom_rows.append(p_match)
            df_current_lineup = pd.DataFrame(custom_rows)

        # Cálculo y Optimización Sabermétrica
        df_opt_lineup, curr_metrics, opt_metrics = engine.optimize_lineup(df_current_lineup)
        delta_runs_season = round(opt_metrics["runs_per_season"] - curr_metrics["runs_per_season"], 1)
        delta_runs_game = round(opt_metrics["runs_per_game"] - curr_metrics["runs_per_game"], 2)

        st.markdown("---")
        st.markdown("### ⚡ Evaluación de Producción Ofensiva")

        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        with kpi1:
            st.metric(
                label="Carreras Esperadas / Juego (R/G)",
                value=f"{curr_metrics['runs_per_game']:.2f} R/G",
                delta=f"{delta_runs_game:+.2f} R/G (Óptimo: {opt_metrics['runs_per_game']:.2f})" if abs(delta_runs_game) > 0.01 else "Óptimo",
            )
        with kpi2:
            st.metric(
                label="Proyección Temporada (50 Juegos)",
                value=f"{curr_metrics['runs_per_season']:.1f} R",
                delta=f"{delta_runs_season:+.1f} Carreras" if abs(delta_runs_season) > 0.1 else "Alineación Eficiente",
            )
        with kpi3:
            st.metric(
                label="wOBA Ponderado del Lineup",
                value=format_rate(curr_metrics["team_woba"]),
                delta=f"Óptimo: {format_rate(opt_metrics['team_woba'])}",
            )
        with kpi4:
            st.metric(
                label="Balance de Platoon (Z/D)",
                value=f"{curr_metrics['platoon_balance_score']}%",
                delta="Alternancia Z/D Protegida" if curr_metrics['platoon_balance_score'] >= 60 else "Vulnerable a Relevo",
            )

        # Tablero Comparativo: Alineación Actual vs. Alineación Óptima (Tango)
        st.markdown("<br>", unsafe_allow_html=True)
        col_cur_view, col_opt_view = st.columns(2)

        with col_cur_view:
            st.markdown(f"""
            <div style="background: rgba(13, 21, 43, 0.85); border: 2px solid #38BDF8; border-radius: 12px; padding: 15px; margin-bottom: 12px;">
                <div style="display: flex; align-items: center; justify-content: space-between;">
                    <h3 style="margin: 0; color: #38BDF8; font-size: 1.15rem;">📋 Alineación Actual ({team_meta.get('short_name', team_abbrev)})</h3>
                    <span style="background: rgba(56, 189, 248, 0.15); color: #38BDF8; padding: 3px 10px; border-radius: 20px; font-weight: 700; font-size: 0.8rem;">{curr_metrics['runs_per_game']} R/G</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            for _, row in df_current_lineup.iterrows():
                s = row["Slot"]
                w_val = format_rate(row.get("wOBA", ".320"))
                o_val = format_rate(row.get("OBP", ".320"))
                s_val = format_rate(row.get("SLG", ".390"))
                wrc = row.get("wRC+", 100)
                bats = row.get("Bats", "D")
                bats_badge = "🟢 Ambidiestro" if bats == "A" else ("🔵 Zurdo" if bats == "Z" else "🔴 Derecho")
                headshot = row.get("Headshot", "https://img.mlbstatic.com/mlb-photos/image/upload/v1/people/generic/headshot/67/current")

                st.markdown(f"""
                <div style="display: flex; align-items: center; justify-content: space-between; background: #0A1124; border: 1px solid rgba(255,255,255,0.06); border-radius: 8px; padding: 8px 12px; margin-bottom: 6px;">
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <span style="font-weight: 800; font-size: 1.1rem; color: #38BDF8; width: 22px;">#{s}</span>
                        <img src="{headshot}" style="width: 38px; height: 38px; border-radius: 50%; object-fit: cover; border: 1px solid #38BDF8; background: #070B19;">
                        <div>
                            <div style="font-weight: 700; color: #FFFFFF; font-size: 0.95rem;">{row['Name']}</div>
                            <div style="font-size: 0.75rem; color: #94A3B8;">{row.get('Assigned_Pos', row.get('Pos', 'UTIL'))} &nbsp;|&nbsp; {bats_badge}</div>
                        </div>
                    </div>
                    <div style="text-align: right;">
                        <div style="font-size: 0.85rem; font-weight: 700; color: #F8FAFC;">wOBA: <span style="color: #38BDF8;">{w_val}</span> &nbsp;|&nbsp; wRC+: {wrc}</div>
                        <div style="font-size: 0.72rem; color: #64748B;">OBP: {o_val} / SLG: {s_val}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

        with col_opt_view:
            st.markdown(f"""
            <div style="background: rgba(13, 21, 43, 0.85); border: 2px solid #FF3B56; border-radius: 12px; padding: 15px; margin-bottom: 12px;">
                <div style="display: flex; align-items: center; justify-content: space-between;">
                    <h3 style="margin: 0; color: #FF3B56; font-size: 1.15rem;">⚡ Alineación Óptima (Tom Tango Model)</h3>
                    <span style="background: rgba(255, 59, 86, 0.15); color: #FF3B56; padding: 3px 10px; border-radius: 20px; font-weight: 700; font-size: 0.8rem;">{opt_metrics['runs_per_game']} R/G</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            for _, row in df_opt_lineup.iterrows():
                s = row["Slot"]
                w_val = format_rate(row.get("wOBA", ".320"))
                o_val = format_rate(row.get("OBP", ".320"))
                s_val = format_rate(row.get("SLG", ".390"))
                wrc = row.get("wRC+", 100)
                role = row.get("Optimal_Role", TANGO_SLOT_LEVERAGE[s]["role"])
                headshot = row.get("Headshot", "https://img.mlbstatic.com/mlb-photos/image/upload/v1/people/generic/headshot/67/current")

                st.markdown(f"""
                <div style="display: flex; align-items: center; justify-content: space-between; background: #0A1124; border: 1px solid rgba(255,255,255,0.06); border-radius: 8px; padding: 8px 12px; margin-bottom: 6px;">
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <span style="font-weight: 800; font-size: 1.1rem; color: #FF3B56; width: 22px;">#{s}</span>
                        <img src="{headshot}" style="width: 38px; height: 38px; border-radius: 50%; object-fit: cover; border: 1px solid #FF3B56; background: #070B19;">
                        <div>
                            <div style="font-weight: 700; color: #FFFFFF; font-size: 0.95rem;">{row['Name']}</div>
                            <div style="font-size: 0.75rem; color: #FF8095;">{role}</div>
                        </div>
                    </div>
                    <div style="text-align: right;">
                        <div style="font-size: 0.85rem; font-weight: 700; color: #F8FAFC;">wOBA: <span style="color: #FF3B56;">{w_val}</span> &nbsp;|&nbsp; wRC+: {wrc}</div>
                        <div style="font-size: 0.72rem; color: #64748B;">OBP: {o_val} / SLG: {s_val}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

        with st.expander("📖 ¿Por qué funciona la Teoría de Optimización de Lineups de Tom Tango?"):
            st.markdown("""
            Según los estudios de **Tom Tango, Mitchel Lichtman y Andrew Dolphin** en *The Book: Playing the Percentages in Baseball*:
            
            1. **El Mejor Bateador va en el Slot #2:** El bateador número 2 toma más turnos que el 3, 4 y 5 a lo largo de la temporada y llega al plato en la 1ra entrada con 0 o 1 out (situaciones de alto apalancamiento).
            2. **El Slot #1 requiere OBP Puro:** Su función principal es llegar a base sin outs para que los bateadores 2, 3 y 4 generen racimos de carreras.
            3. **El Slot #4 es para el Máximo Poder (ISO/SLG):** Es el turno que batea con mayor densidad histórica de corredores en base.
            4. **El Slot #3 está sobrevalorado tradicionalmente:** Suele batear en el 1er inning con 2 outs y bases limpias, por lo que es mejor colocar allí a un bateador de buen contacto antes que al mejor slugger.
            5. **El Slot #9 es el "Segundo Leadoff":** Tener a un bateador con buen OBP en el 9no puesto sirve de puente hacia el tope del orden (1-2-3).
            """)

        st.markdown("<br>", unsafe_allow_html=True)
        tab_chart, tab_matchup = st.tabs(["📊 Producción por Slot en el Orden", "⚔️ Matchup H2H de Alineaciones"])

        with tab_chart:
            fig_prod = build_lineup_production_chart(
                curr_metrics["slot_contributions"],
                opt_metrics["slot_contributions"],
                team_meta.get("name", team_abbrev),
            )
            st.plotly_chart(fig_prod, use_container_width=True)

        with tab_matchup:
            st.subheader("Comparación Cara a Cara de Dos Alineaciones LIDOM")
            c1, c2 = st.columns(2)
            with c1:
                t1_sel = st.selectbox("Equipo Local:", list(team_options.keys()), index=0, key="h2h_t1")
            with c2:
                t2_sel = st.selectbox("Equipo Visitante:", list(team_options.keys()), index=1, key="h2h_t2")

            t1_ab = team_options[t1_sel]
            t2_ab = team_options[t2_sel]

            df_t1 = engine.get_preset_lineup(t1_ab, pool_df)
            df_t2 = engine.get_preset_lineup(t2_ab, pool_df)

            m_t1 = engine.calculate_expected_runs(df_t1)
            m_t2 = engine.calculate_expected_runs(df_t2)

            fig_h2h = build_lineup_h2h_trajectory(m_t1["slot_contributions"], m_t2["slot_contributions"], t1_sel, t2_sel)
            st.plotly_chart(fig_h2h, use_container_width=True)

    # =========================================================================
    # TAB 2: TRACKER DE LINEUPS MÁS REPETIDOS
    # =========================================================================
    with tab_tracker:
        st.subheader("📋 Tracker de Alineaciones Titulares y Récord W-L")
        st.markdown("Identifica las combinaciones de 9 bateadores más utilizadas por cada franquicia a lo largo de la temporada y su récord de victorias/derrotas.")

        sel_track_team = st.selectbox("🏟️ Seleccionar Franquicia para Análisis de Lineups:", list(team_options.keys()), index=0, key="track_team_sel")
        track_abbrev = team_options[sel_track_team]
        track_meta = get_team_by_abbrev(track_abbrev) or {}

        lineups_games = loader.get_team_season_lineups(season=season, team_abbrev=track_abbrev)

        if not lineups_games:
            st.info(f"No se encontraron datos históricos de alineaciones para {sel_track_team} en la temporada {season}.")
        else:
            # Agrupar alineaciones exactas
            lineup_groups = {}
            for g in lineups_games:
                starters = g["starters"]
                key = tuple((s["order"], s["player_name"], s["position"]) for s in sorted(starters, key=lambda x: x["order"]))
                if key not in lineup_groups:
                    lineup_groups[key] = {
                        "games_count": 0,
                        "wins": 0,
                        "losses": 0,
                        "games": [],
                        "starters": sorted(starters, key=lambda x: x["order"])
                    }
                won = g["won"]
                lineup_groups[key]["games_count"] += 1
                if won:
                    lineup_groups[key]["wins"] += 1
                else:
                    lineup_groups[key]["losses"] += 1
                lineup_groups[key]["games"].append({
                    "game_date": g["game_date"],
                    "opposing_team": g["opposing_team"],
                    "score": g["score_str"],
                    "won": won
                })

            sorted_unique_lineups = sorted(
                lineup_groups.values(),
                key=lambda x: (x["games_count"], x["wins"]),
                reverse=True
            )

            # KPIs
            tot_juegos = len(lineups_games)
            tot_uniques = len(sorted_unique_lineups)
            top_rep = sorted_unique_lineups[0]["games_count"] if sorted_unique_lineups else 0
            w_top = sorted_unique_lineups[0]["wins"] if sorted_unique_lineups else 0
            l_top = sorted_unique_lineups[0]["losses"] if sorted_unique_lineups else 0
            pct_top = (w_top / top_rep) if top_rep > 0 else 0

            tk1, tk2, tk3, tk4 = st.columns(4)
            with tk1:
                st.metric("Total Juegos Analizados", f"{tot_juegos} JJ")
            with tk2:
                st.metric("Alineaciones Únicas Usadas", f"{tot_uniques}")
            with tk3:
                st.metric("Alineación Más Frecuente", f"{top_rep} juegos")
            with tk4:
                st.metric("Récord de la Alineación #1", f"{w_top} - {l_top}", f".{int(pct_top*1000):03d} PCT")

            st.markdown("---")

            subtab_top_lu, subtab_card = st.tabs([
                "🌟 Alineaciones Más Utilizadas",
                "🎴 Tarjeta de Alineación por Juego (Lineup Card)"
            ])

            with subtab_top_lu:
                st.markdown("#### 🌟 Combinaciones de Orden al Bate Más Frecuentes")
                st.markdown("Despliega cada alineación para ver los 9 titulares y la lista de encuentros disputados con esa combinación exacta:")

                pos_names = {
                    "1B": "Primera Base", "2B": "Segunda Base", "3B": "Tercera Base",
                    "SS": "Campocorto", "LF": "Jardín Izquierdo", "CF": "Jardín Central",
                    "RF": "Jardín Derecho", "C": "Receptor", "DH": "Bateador Designado", "UTIL": "Utility"
                }

                for idx, u_lu in enumerate(sorted_unique_lineups[:15], 1):
                    pct_val = (u_lu["wins"] / u_lu["games_count"]) if u_lu["games_count"] > 0 else 0
                    s1 = u_lu['starters'][0]['player_name'] if len(u_lu['starters']) > 0 else ""
                    s2 = u_lu['starters'][1]['player_name'] if len(u_lu['starters']) > 1 else ""
                    s3 = u_lu['starters'][2]['player_name'] if len(u_lu['starters']) > 2 else ""
                    s4 = u_lu['starters'][3]['player_name'] if len(u_lu['starters']) > 3 else ""

                    expander_title = f"🏆 Alineación #{idx} — {u_lu['games_count']} JJ ({u_lu['wins']} V - {u_lu['losses']} D | .{int(pct_val*1000):03d} PCT) — 1. {s1}, 2. {s2}, 3. {s3}, 4. {s4}..."

                    with st.expander(expander_title, expanded=(idx == 1)):
                        c_l_left, c_l_right = st.columns(2)
                        with c_l_left:
                            for s in u_lu["starters"][:5]:
                                b_col = "#38BDF8" if s['order'] <= 3 else ("#F59E0B" if s['order'] == 4 else "#8B5CF6")
                                pos_desc = pos_names.get(s['position'], s['position'])
                                st.markdown(f"""
                                <div style='background: #0A1124; padding: 10px 14px; border-radius: 6px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #1E293B;'>
                                    <div><span style='background: {b_col}; color: white; padding: 3px 8px; border-radius: 4px; font-weight: bold; margin-right: 8px;'>#{s['order']}</span><b style='color: #F8FAFC;'>{s['player_name']}</b></div>
                                    <div><span style='background: #1E293B; color: #94A3B8; padding: 2px 8px; border-radius: 4px; font-size: 12px;'>{s['position']} • {pos_desc}</span></div>
                                </div>
                                """, unsafe_allow_html=True)
                        with c_l_right:
                            for s in u_lu["starters"][5:]:
                                pos_desc = pos_names.get(s['position'], s['position'])
                                st.markdown(f"""
                                <div style='background: #0A1124; padding: 10px 14px; border-radius: 6px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #1E293B;'>
                                    <div><span style='background: #64748B; color: white; padding: 3px 8px; border-radius: 4px; font-weight: bold; margin-right: 8px;'>#{s['order']}</span><b style='color: #F8FAFC;'>{s['player_name']}</b></div>
                                    <div><span style='background: #1E293B; color: #94A3B8; padding: 2px 8px; border-radius: 4px; font-size: 12px;'>{s['position']} • {pos_desc}</span></div>
                                </div>
                                """, unsafe_allow_html=True)

                        st.markdown("##### 📅 Partidos Disputados con esta Alineación Exacta")
                        g_tbl = pd.DataFrame([{
                            "Fecha": gm["game_date"],
                            "Rival": gm["opposing_team"],
                            "Marcador": gm["score"],
                            "Resultado": "Victoria" if gm["won"] else "Derrota"
                        } for gm in u_lu["games"]])
                        st.dataframe(g_tbl, use_container_width=True, hide_index=True)

            with subtab_card:
                st.markdown("#### 🏟️ Explorador de Tarjeta de Juego (Dugout Scorecard)")
                st.markdown("Selecciona un partido del calendario para visualizar el orden al bate completo del 1ro al 9no bate.")

                game_options = {}
                for g in lineups_games:
                    symbol = "✅ Victoria" if g["won"] else "❌ Derrota"
                    label = f"📅 {g['game_date']} | vs {g['opposing_team']} ({symbol} {g['score_str']})"
                    game_options[label] = g

                selected_game_label = st.selectbox("Seleccionar Partido del Calendario", list(game_options.keys()), key="lineup_game_picker")
                selected_game = game_options[selected_game_label]

                opp_name = selected_game['opposing_team']
                st.markdown(f"""
                <div style='background-color: #0D152B; padding: 16px; border-radius: 10px; border-left: 6px solid {'#10b981' if selected_game['won'] else '#ef4444'}; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center;'>
                    <div style='display: flex; align-items: center; gap: 14px;'>
                        <img src='{track_meta.get("logo_url", "")}' width='50' style='vertical-align: middle;'>
                        <div>
                            <h3 style='margin: 0; color: #ffffff;'>🦁 {track_meta.get("name", track_abbrev)}</h3>
                            <p style='margin: 4px 0 0 0; color: #94a3b8;'>📅 Fecha: <b>{selected_game['game_date']}</b> | Marcador Final: <b>{selected_game['full_score_str']}</b> ({selected_game['result_str']})</p>
                        </div>
                    </div>
                    <div style='text-align: center;'>
                        <span style='font-size: 13px; color: #38BDF8; font-weight: 700;'>vs {opp_name}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                col_order_left, col_order_right = st.columns(2)
                starters_sorted = sorted(selected_game["starters"], key=lambda x: x["order"])

                with col_order_left:
                    for s in starters_sorted[:5]:
                        badge_color = "#38BDF8" if s['order'] <= 3 else ("#F59E0B" if s['order'] == 4 else "#8B5CF6")
                        st.markdown(f"""
                        <div style='background: #0A1124; padding: 12px 16px; border-radius: 8px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #1E293B;'>
                            <div style='display: flex; align-items: center; gap: 10px;'>
                                <span style='background: {badge_color}; color: white; padding: 4px 10px; border-radius: 6px; font-weight: bold; font-size: 14px;'>#{s['order']}</span>
                                <img src='{s.get("headshot_url", "")}' style='width: 34px; height: 34px; border-radius: 50%; object-fit: cover; background: #070B19;'>
                                <span style='font-size: 15px; font-weight: 600; color: #f8fafc;'>{s['player_name']}</span>
                            </div>
                            <div>
                                <span style='background: #1E293B; color: #e2e8f0; padding: 4px 8px; border-radius: 4px; font-size: 12px;'>{s['position']}</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                with col_order_right:
                    for s in starters_sorted[5:]:
                        st.markdown(f"""
                        <div style='background: #0A1124; padding: 12px 16px; border-radius: 8px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #1E293B;'>
                            <div style='display: flex; align-items: center; gap: 10px;'>
                                <span style='background: #64748B; color: white; padding: 4px 10px; border-radius: 6px; font-weight: bold; font-size: 14px;'>#{s['order']}</span>
                                <img src='{s.get("headshot_url", "")}' style='width: 34px; height: 34px; border-radius: 50%; object-fit: cover; background: #070B19;'>
                                <span style='font-size: 15px; font-weight: 600; color: #f8fafc;'>{s['player_name']}</span>
                            </div>
                            <div>
                                <span style='background: #1E293B; color: #e2e8f0; padding: 4px 8px; border-radius: 4px; font-size: 12px;'>{s['position']}</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

    # =========================================================================
    # TAB 3: MATRIZ DE CALOR & APORTE POR TURNO
    # =========================================================================
    with tab_slots:
        st.subheader("📊 Matriz de Calor & Rendimiento por Turno al Bate")
        st.markdown("Evalúa la versatilidad de cada bateador en el orden ofensivo y cómo impacta su presencia en un turno específico sobre el récord de victorias del equipo.")

        sel_slot_team = st.selectbox("🏟️ Franquicia a Analizar:", list(team_options.keys()), index=0, key="slot_team_sel")
        slot_abbrev = team_options[sel_slot_team]
        slot_games = loader.get_team_season_lineups(season=season, team_abbrev=slot_abbrev)

        if not slot_games:
            st.info("No hay datos de partidos disponibles para esta franquicia.")
        else:
            # Flatten starters
            starters_flat = []
            for g in slot_games:
                g_date = g["game_date"]
                opp = g["opposing_team"]
                won = g["won"]
                score_str = g["score_str"]
                for s in g["starters"]:
                    starters_flat.append({
                        "Jugador": s["player_name"],
                        "Turno_Num": s["order"],
                        "Turno": f"{s['order']}º Bate",
                        "Posicion": s["position"],
                        "game_date": g_date,
                        "opposing_team": opp,
                        "Marcador": score_str,
                        "won": 1 if won else 0,
                        "lost": 0 if won else 1,
                        "AVG": s.get("AVG", ".000"),
                        "OPS": s.get("OPS", ".000"),
                        "HR": s.get("HR", 0),
                        "RBI": s.get("RBI", 0),
                    })

            df_starters = pd.DataFrame(starters_flat)

            subtab_matrix, subtab_player = st.tabs([
                "📊 Matriz de Calor (Turnos 1 al 9)",
                "👤 Impacto y Récord por Jugador Titular"
            ])

            # ---- MATRIZ DE CALOR ----
            with subtab_matrix:
                st.markdown("#### 📊 Distribución de Titularidades en el Orden al Bate (1ro al 9no)")
                st.markdown("Muestra el mapa de frecuencia con el número de veces que cada pelotero inició en cada posición ofensiva.")

                pivot_matrix = df_starters.pivot_table(index="Jugador", columns="Turno_Num", aggfunc="size", fill_value=0)
                col_map = {i: f"{i}º Bate" for i in range(1, 10)}
                pivot_matrix = pivot_matrix.rename(columns=col_map)
                ordered_cols = [f"{i}º Bate" for i in range(1, 10) if f"{i}º Bate" in pivot_matrix.columns]
                pivot_matrix = pivot_matrix[ordered_cols]
                pivot_matrix["Total Titular"] = pivot_matrix.sum(axis=1)
                pivot_matrix = pivot_matrix.sort_values(by="Total Titular", ascending=False)

                top_players = pivot_matrix.head(15).iloc[::-1]

                fig_heat = px.imshow(
                    top_players[ordered_cols].values,
                    x=ordered_cols,
                    y=top_players.index.tolist(),
                    color_continuous_scale="Blues",
                    text_auto=True,
                    labels=dict(x="Turno al Bate", y="Jugador", color="Juegos Titular")
                )
                fig_heat.update_layout(
                    paper_bgcolor="#070C1A",
                    plot_bgcolor="#0D152B",
                    font=dict(color="#E2E8F0", family="Outfit, sans-serif"),
                    height=500,
                    margin=dict(l=10, r=10, t=10, b=10),
                    xaxis_title="Turno en el Orden al Bate",
                    yaxis_title=""
                )
                st.plotly_chart(fig_heat, use_container_width=True)

                st.markdown("#### 📋 Tabla Completa de Titularidades por Turno")
                st.dataframe(pivot_matrix, use_container_width=True)

            # ---- IMPACTO POR JUGADOR ----
            with subtab_player:
                st.markdown("#### 👤 Análisis de Titularidad y Récord por Jugador")
                st.markdown("Selecciona un jugador para ver en qué turnos alineó, el récord de victorias/derrotas del equipo y su rendimiento.")

                all_starters_list = sorted(df_starters["Jugador"].unique().tolist())
                sel_player = st.selectbox("Seleccionar Jugador Titular:", all_starters_list, key="player_slot_sel")

                df_p_lu = df_starters[df_starters["Jugador"] == sel_player]

                tot_p_games = len(df_p_lu)
                tot_p_w = int(df_p_lu["won"].sum())
                tot_p_l = int(df_p_lu["lost"].sum())
                pct_p = tot_p_w / tot_p_games if tot_p_games > 0 else 0

                pk1, pk2, pk3 = st.columns(3)
                with pk1:
                    st.metric(f"Titularidades con {sel_player}", f"{tot_p_games} JJ")
                with pk2:
                    st.metric("Récord del Equipo", f"{tot_p_w} - {tot_p_l}")
                with pk3:
                    st.metric("% Efectividad", f".{int(pct_p*1000):03d} PCT")

                st.markdown("##### 🔢 Desglose por Turno al Bate")
                p_turnos = df_p_lu.groupby("Turno").agg(
                    Titularidades=("won", "count"),
                    Victorias=("won", "sum"),
                    Derrotas=("lost", "sum")
                ).reset_index()
                p_turnos["% Victorias"] = (p_turnos["Victorias"] / p_turnos["Titularidades"]).apply(lambda x: f".{int(x*1000):03d}")
                p_turnos = p_turnos.sort_values(by="Titularidades", ascending=False)
                st.dataframe(p_turnos, use_container_width=True, hide_index=True)

                st.markdown("##### 📅 Historial de Partidos como Titular")
                disp_p_games = df_p_lu[["game_date", "opposing_team", "Marcador", "Turno", "Posicion", "won"]].copy()
                disp_p_games["Resultado"] = disp_p_games["won"].apply(lambda x: "Victoria" if x == 1 else "Derrota")
                disp_p_games = disp_p_games.rename(columns={
                    "game_date": "Fecha", "opposing_team": "Rival", "Turno": "Turno al Bate", "Posicion": "Posición Defensiva"
                })[["Fecha", "Rival", "Marcador", "Turno al Bate", "Posición Defensiva", "Resultado"]]

                st.dataframe(disp_p_games, use_container_width=True, hide_index=True)
