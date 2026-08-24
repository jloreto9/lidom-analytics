"""Vista de Analítica y Optimización de Lineups para LIDOM (Base Runs & Tango Theory)."""

import streamlit as st
import pandas as pd
import numpy as np
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
    """Renderiza la vista completa de Analítica y Optimización de Lineups."""
    st.markdown("""
    <div style="text-align: center; margin-bottom: 20px;">
        <h1 style="font-size: 2.2rem; font-weight: 800; background: linear-gradient(135deg, #FF3B56 0%, #38BDF8 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 5px;">
            📋 Laboratorio de Lineups & Optimización Sabermétrica
        </h1>
        <p style="color: #94A3B8; font-size: 0.95rem; max-width: 850px; margin: 0 auto;">
            Evaluación de órdenes al bate con modelos de <b>Base Runs</b> y la teoría de <b>Tom Tango (The Book)</b>. Optimiza la secuencia ofensiva para maximizar las carreras esperadas (<span style="color: #38BDF8;">R/G</span>) y el aprovechamiento de situaciones con corredores en base.
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

    # 2. Selector de Equipo y Modo
    team_options = {meta["name"]: meta["abbrev"] for meta in TEAMS.values()}
    col_t1, col_mode = st.columns([1, 1])

    with col_t1:
        sel_team_name = st.selectbox("🏟️ Seleccionar Franquicia LIDOM:", list(team_options.keys()), index=0)
        team_abbrev = team_options[sel_team_name]
        team_meta = get_team_by_abbrev(team_abbrev) or {}

    with col_mode:
        lineup_mode = st.radio(
            "⚙️ Modalidad de Alineación:",
            ["🚀 Alineación Titular Oficial (Preset)", "🛠️ Constructor Personalizado (Custom 1-9)"],
            horizontal=True,
        )

    # 3. Obtener Lineup Inicial
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
                def_p_name = player_names[(s - 1) % len(player_names)]
                picked_name = st.selectbox(f"Slot #{s}:", player_names, index=(s - 1) % len(player_names), key=f"slot_pick_{s}")
                p_match = pool_df[pool_df["Name"] == picked_name].iloc[0].to_dict()
                p_match["Slot"] = s
                p_match["Bats"] = "D" if s % 2 == 0 else "Z"
                p_match["Assigned_Pos"] = p_match.get("Pos", "UTIL")
                custom_rows.append(p_match)
        df_current_lineup = pd.DataFrame(custom_rows)

    # 4. Cálculo y Optimización Sabermétrica
    df_opt_lineup, curr_metrics, opt_metrics = engine.optimize_lineup(df_current_lineup)
    delta_runs_season = round(opt_metrics["runs_per_season"] - curr_metrics["runs_per_season"], 1)
    delta_runs_game = round(opt_metrics["runs_per_game"] - curr_metrics["runs_per_game"], 2)

    # 5. Tarjetas Hero de Rendimiento Ofensivo
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

    # 6. Tablero Comparativo: Alineación Actual vs. Alineación Óptima (Tango)
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
            bats_badge = "🟢 Batea: Ambidiestro" if bats == "A" else ("🔵 Batea: Zurdo" if bats == "Z" else "🔴 Batea: Derecho")
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

    # 7. Diagnóstico Táctico y Principios Sabermétricos de Tom Tango
    with st.expander("📖 ¿Por qué funciona la Teoría de Optimización de Lineups de Tom Tango?"):
        st.markdown("""
        Según los estudios de **Tom Tango, Mitchel Lichtman y Andrew Dolphin** en *The Book: Playing the Percentages in Baseball*:
        
        1. **El Mejor Bateador va en el Slot #2:** El bateador número 2 toma más turnos que el 3, 4 y 5 a lo largo de la temporada y llega al plato en la 1ra entrada con 0 o 1 out (situaciones de alto apalancamiento).
        2. **El Slot #1 requiere OBP Puro:** Su función principal es llegar a base sin outs para que los bateadores 2, 3 y 4 generen racimos de carreras.
        3. **El Slot #4 es para el Máximo Poder (ISO/SLG):** Es el turno que batea con mayor densidad histórica de corredores en base.
        4. **El Slot #3 está sobrevalorado tradicionalmente:** Suele batear en el 1er inning con 2 outs y bases limpias, por lo que es mejor colocar allí a un bateador de buen contacto antes que al mejor slugger.
        5. **El Slot #9 es el "Segundo Leadoff":** Tener a un bateador con buen OBP en el 9no puesto sirve de puente hacia el tope del orden (1-2-3).
        """)

    # 8. Gráficos Analíticos
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
