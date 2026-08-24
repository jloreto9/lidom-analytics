"""Vista Spray Charts: Gráficos de dispersión espacial de batazos con calibración BIS en LIDOM."""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

from core.data_loader import LIDOMDataLoader
from core.teams import get_all_teams
from utils.styles import render_header


def render_spray_charts_view(season: int = 2024) -> None:
    """Renderiza el módulo de Spray Charts calibrados con dureza BIS."""
    render_header(
        title="Spray Charts & Calidad de Contacto (BIS)",
        subtitle="Dispersión espacial de batazos en diamante interactivo con filtros de dureza (Hard, Medium, Soft)",
        badge_text="LIDOM SPRAY",
        season=season,
    )

    loader = LIDOMDataLoader()
    df_spray = loader.get_batted_balls_sample()

    # Filtros superiores
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        team_choice = st.selectbox(
            "Filtrar por Franquicia:",
            ["Todas"] + [t["name"] for t in get_all_teams()],
            index=0,
        )
    with col_f2:
        batters_list = ["Todos"] + sorted(list(df_spray["batter"].unique()))
        batter_choice = st.selectbox("Filtrar por Bateador:", batters_list, index=0)
    with col_f3:
        hardness_choice = st.multiselect(
            "Dureza BIS:",
            ["Hard", "Medium", "Soft"],
            default=["Hard", "Medium", "Soft"],
        )

    # Aplicar filtros
    filtered_df = df_spray.copy()
    if team_choice != "Todas":
        selected_team_meta = next(t for t in get_all_teams() if t["name"] == team_choice)
        filtered_df = filtered_df[filtered_df["team_id"] == selected_team_meta["id"]]
    if batter_choice != "Todos":
        filtered_df = filtered_df[filtered_df["batter"] == batter_choice]
    if hardness_choice:
        filtered_df = filtered_df[filtered_df["hardness"].isin(hardness_choice)]

    # Métricas de Calidad de Contacto
    total_balls = len(filtered_df)
    hard_count = (filtered_df["hardness"] == "Hard").sum()
    med_count = (filtered_df["hardness"] == "Medium").sum()
    soft_count = (filtered_df["hardness"] == "Soft").sum()

    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    with col_m1:
        st.metric(label="Total de Contactos", value=total_balls)
    with col_m2:
        st.metric(label="🔥 Hard Contact %", value=f"{(hard_count/total_balls*100):.1f}%" if total_balls > 0 else "0.0%", delta="≥ 95 mph / BIS")
    with col_m3:
        st.metric(label="⚡ Medium %", value=f"{(med_count/total_balls*100):.1f}%" if total_balls > 0 else "0.0%")
    with col_m4:
        st.metric(label="🍂 Soft %", value=f"{(soft_count/total_balls*100):.1f}%" if total_balls > 0 else "0.0%")

    st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)

    # Construir el campo de béisbol en Plotly
    fig = go.Figure()

    # 1. Líneas de foul (Home en 125, 205)
    home_x, home_y = 125, 205
    left_foul_x, left_foul_y = 125 - 110, 205 - 110
    right_foul_x, right_foul_y = 125 + 110, 205 - 110

    fig.add_trace(go.Scatter(
        x=[left_foul_x, home_x, right_foul_x],
        y=[left_foul_y, home_y, right_foul_y],
        mode="lines",
        line=dict(color="rgba(255, 255, 255, 0.4)", width=2),
        showlegend=False,
        hoverinfo="skip",
    ))

    # 2. Diamante del Infield (Home -> 1B -> 2B -> 3B -> Home)
    infield_x = [125, 125 + 28, 125, 125 - 28, 125]
    infield_y = [205, 205 - 28, 205 - 56, 205 - 28, 205]
    fig.add_trace(go.Scatter(
        x=infield_x,
        y=infield_y,
        mode="lines",
        line=dict(color="rgba(255, 255, 255, 0.5)", width=2),
        fill="toself",
        fillcolor="rgba(196, 154, 69, 0.15)",
        showlegend=False,
        hoverinfo="skip",
    ))

    # 3. Arco de la cerca del Outfield
    angles = np.linspace(-45, 45, 60)
    rads = np.radians(angles)
    fence_r = 160.0
    fence_x = 125 + fence_r * np.sin(rads)
    fence_y = 205 - fence_r * np.cos(rads)

    fig.add_trace(go.Scatter(
        x=fence_x,
        y=fence_y,
        mode="lines",
        line=dict(color="rgba(255, 255, 255, 0.4)", width=2, dash="dash"),
        showlegend=False,
        hoverinfo="skip",
    ))

    # 4. Trazas de batazos por Dureza BIS
    color_map = {"Hard": "#EF4444", "Medium": "#F59E0B", "Soft": "#38BDF8"}

    for h_type in ["Hard", "Medium", "Soft"]:
        df_sub = filtered_df[filtered_df["hardness"] == h_type]
        if not df_sub.empty:
            fig.add_trace(go.Scatter(
                x=df_sub["hc_x"],
                y=df_sub["hc_y"],
                mode="markers",
                name=f"Dureza {h_type} ({len(df_sub)})",
                marker=dict(
                    color=color_map.get(h_type, "#FFFFFF"),
                    size=10,
                    line=dict(width=1, color="#FFFFFF"),
                    opacity=0.85,
                ),
                text=[
                    f"<b>{r['batter']}</b><br>Resultado: {r['event']}<br>Tipo: {r['trajectory']}<br>Vel. Salida: {r['launch_speed']} mph<br>Distancia: {r['distance']} ft<br>Dureza: {r['hardness']}"
                    for _, r in df_sub.iterrows()
                ],
                hoverinfo="text",
            ))

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(13, 21, 43, 0.6)",
        font=dict(color="#FFFFFF", family="Inter"),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[0, 250]),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[230, 20], scaleanchor="x", scaleratio=1),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=10, r=10, t=20, b=10),
        height=520,
    )

    st.plotly_chart(fig, use_container_width=True)

    # Tabla resumen de batazos
    st.subheader("📋 Registro de Batazos y Calibración BIS")
    st.dataframe(
        filtered_df[["batter", "event", "trajectory", "hardness", "launch_speed", "distance"]].rename(columns={
            "batter": "Bateador",
            "event": "Resultado",
            "trajectory": "Trayectoria",
            "hardness": "Dureza BIS",
            "launch_speed": "EV (mph)",
            "distance": "Distancia (ft)",
        }),
        use_container_width=True,
        hide_index=True,
    )
