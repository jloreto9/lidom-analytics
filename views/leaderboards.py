"""Vista de Líderes Individuales (Leaderboards) Tradicionales y Sabermétricos de LIDOM."""

import streamlit as st
import pandas as pd
import plotly.express as px

from core.data_loader import LIDOMDataLoader
from core.teams import get_team_by_abbrev
from utils.styles import render_header


def render_leaderboards_view(season: int = 2024) -> None:
    """Renderiza las tablas de líderes de bateo y pitcheo de LIDOM."""
    render_header(
        title="Líderes de Bateo y Pitcheo",
        subtitle="Rankings oficiales y métricas sabermétricas avanzadas (wOBA, wRC+, WPA, FIP, WHIP)",
        badge_text="LÍDERES LIDOM",
        season=season,
    )

    loader = LIDOMDataLoader()

    tab_batting, tab_pitching, tab_scatter = st.tabs([
        "🏏 Líderes de Bateo",
        "⚾ Líderes de Pitcheo",
        "📈 Correlaciones y Cuadrantes",
    ])

    with tab_batting:
        df_hit = loader.get_hitting_leaderboard(season=season)

        col_f1, col_f2 = st.columns([2, 2])
        with col_f1:
            stat_sort = st.selectbox(
                "Ordenar por Métrica:",
                ["AVG", "OPS", "wOBA", "wRC+", "HR", "RBI", "H", "SB", "WPA", "Hard%"],
                index=2,
            )
        with col_f2:
            team_filter = st.multiselect(
                "Filtrar por Equipo:",
                ["LIC", "AGU", "ESC", "GIG", "EST", "TOR"],
                default=[],
            )

        if team_filter:
            df_hit = df_hit[df_hit["team"].isin(team_filter)]

        # Ordenar DataFrame
        if stat_sort in ["AVG", "OBP", "SLG", "OPS", "wOBA"]:
            df_hit["_sort_key"] = df_hit[stat_sort].apply(lambda x: float(f"0{x}"))
            df_hit = df_hit.sort_values(by="_sort_key", ascending=False).drop(columns=["_sort_key"])
        else:
            df_hit = df_hit.sort_values(by=stat_sort, ascending=False)

        # Top 3 Tarjetas Visuales
        if not df_hit.empty:
            cols = st.columns(min(3, len(df_hit)))
            for i, c in enumerate(cols):
                p_row = df_hit.iloc[i]
                with c:
                    st.metric(
                        label=f"#{i+1} {p_row['name']} ({p_row['team']})",
                        value=f"{p_row[stat_sort]}",
                        delta=f"{p_row['pos']} | {p_row['G']} JJ",
                    )

        st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)
        st.dataframe(
            df_hit[["name", "team", "pos", "G", "AB", "R", "H", "2B", "3B", "HR", "RBI", "BB", "SO", "SB", "AVG", "OBP", "SLG", "OPS", "wOBA", "wRC+", "WPA", "Hard%"]].rename(columns={"name": "Bateador", "team": "EQ", "pos": "POS"}),
            use_container_width=True,
            hide_index=True,
        )

    with tab_pitching:
        df_pitch = loader.get_pitching_leaderboard(season=season)

        col_p1, col_p2 = st.columns([2, 2])
        with col_p1:
            pitch_sort = st.selectbox(
                "Ordenar Lanzadores por:",
                ["ERA", "WHIP", "FIP", "SO", "W", "WPA", "K/9", "IP"],
                index=0,
            )
        with col_p2:
            role_filter = st.selectbox("Filtrar por Rol:", ["Todos", "Abridores (SP)", "Relevistas/Cerradores (RP/CL)"], index=0)

        if role_filter == "Abridores (SP)":
            df_pitch = df_pitch[df_pitch["role"] == "SP"]
        elif role_filter == "Relevistas/Cerradores (RP/CL)":
            df_pitch = df_pitch[df_pitch["role"].isin(["RP", "CL"])]

        # Ordenar (ERA, WHIP, FIP menor es mejor)
        if pitch_sort in ["ERA", "WHIP", "FIP"]:
            df_pitch["_sort_key"] = df_pitch[pitch_sort].astype(float)
            df_pitch = df_pitch.sort_values(by="_sort_key", ascending=True).drop(columns=["_sort_key"])
        else:
            df_pitch = df_pitch.sort_values(by=pitch_sort, ascending=False)

        if not df_pitch.empty:
            cols = st.columns(min(3, len(df_pitch)))
            for i, c in enumerate(cols):
                p_row = df_pitch.iloc[i]
                with c:
                    st.metric(
                        label=f"#{i+1} {p_row['name']} ({p_row['team']})",
                        value=f"{p_row[pitch_sort]}",
                        delta=f"{p_row['role']} | {p_row['IP']} IP",
                    )

        st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)
        st.dataframe(
            df_pitch[["name", "team", "role", "G", "GS", "W", "L", "IP", "H", "ER", "BB", "SO", "ERA", "WHIP", "FIP", "K/9", "WPA"]].rename(columns={"name": "Lanzador", "team": "EQ", "role": "Rol"}),
            use_container_width=True,
            hide_index=True,
        )

    with tab_scatter:
        st.subheader("📊 Cuadrantes y Eficiencia Sabermétrica")
        df_hit_all = loader.get_hitting_leaderboard(season=season).copy()
        df_hit_all["wOBA_num"] = df_hit_all["wOBA"].apply(lambda x: float(f"0{x}"))

        fig = px.scatter(
            df_hit_all,
            x="wOBA_num",
            y="WPA",
            text="name",
            color="team",
            size="HR",
            hover_data=["OPS", "wRC+", "Hard%"],
            title="Impacto Ofensivo: wOBA (Habilidad Pura) vs WPA (Valor en Contexto de Victoria)",
            color_discrete_map={
                "LIC": "#002D62", "AGU": "#FFCC00", "ESC": "#CC0000",
                "GIG": "#5B1E31", "EST": "#005A36", "TOR": "#EA5B0C",
            },
        )
        fig.update_traces(textposition="top center", marker=dict(size=14, line=dict(width=1, color="#FFFFFF")))
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(13, 21, 43, 0.4)",
            font=dict(color="#FFFFFF", family="Inter"),
            xaxis=dict(title="wOBA (Weighted On-Base Average)", gridcolor="rgba(255,255,255,0.06)"),
            yaxis=dict(title="WPA (Win Probability Added)", gridcolor="rgba(255,255,255,0.06)"),
            legend=dict(title="Equipo"),
            margin=dict(l=10, r=10, t=50, b=10),
            height=450,
        )
        st.plotly_chart(fig, use_container_width=True)
