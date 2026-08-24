"""Vista Principal / Home: Standings, Power Rankings ELO y Proyecciones Monte Carlo de LIDOM."""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from core.data_loader import LIDOMDataLoader
from core.elo_engine import EloEngine
from core.teams import get_all_teams
from utils.styles import render_header


def render_home_view(season: int = 2024) -> None:
    """Renderiza el dashboard principal de LIDOM."""
    render_header(
        title="LIDOM 360 Analytics",
        subtitle="Analítica avanzada, Power Rankings ELO y Modelos Predictivos para la pelota invernal dominicana",
        badge_text="LIDOM REGULAR",
        season=season,
    )

    loader = LIDOMDataLoader()
    elo_engine = EloEngine()

    # Cargar datos
    df_standings = loader.get_standings_df(season=season)
    power_rankings = elo_engine.get_power_rankings()

    # Métricas clave de la Liga
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        leader_team = df_standings.iloc[0]["Equipo"] if not df_standings.empty else "N/D"
        st.metric(label="Líder del Torneo", value=leader_team, delta="1er Lugar")
    with col2:
        top_elo = power_rankings[0]["name"] if power_rankings else "N/D"
        st.metric(label="Líder ELO", value=top_elo, delta=f"{power_rankings[0]['elo']} pts" if power_rankings else "")
    with col3:
        total_runs = int(df_standings["CA"].sum()) if not df_standings.empty else 0
        st.metric(label="Carreras Anotadas (Liga)", value=f"{total_runs:,}")
    with col4:
        st.metric(label="Simulaciones Monte Carlo", value="5,000", delta="Playoffs & Final")

    st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)

    # Layout de 2 columnas: Standings vs ELO
    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.subheader("📊 Tabla de Posiciones (Standings)")
        display_cols = ["Logo", "Equipo", "G", "W", "L", "PCT", "GB", "CA", "CP", "DIFF", "Racha"]
        st.dataframe(
            df_standings[display_cols],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Logo": st.column_config.ImageColumn(
                    "Logo",
                    help="Logo oficial de la franquicia",
                    width="small",
                ),
                "Equipo": st.column_config.TextColumn("Equipo", width="medium"),
                "G": st.column_config.NumberColumn("G", help="Juegos Jugados", format="%d"),
                "W": st.column_config.NumberColumn("W", help="Victorias", format="%d"),
                "L": st.column_config.NumberColumn("L", help="Derrotas", format="%d"),
                "PCT": st.column_config.TextColumn("PCT", help="Porcentaje de Victoria"),
                "GB": st.column_config.TextColumn("GB", help="Juegos de Ventaja"),
                "CA": st.column_config.NumberColumn("CA", help="Carreras Anotadas", format="%d"),
                "CP": st.column_config.NumberColumn("CP", help="Carreras Permitidas", format="%d"),
                "DIFF": st.column_config.TextColumn("DIFF", help="Diferencial de Carreras"),
                "Racha": st.column_config.TextColumn("Racha", help="Racha Actual"),
            },
        )

        st.caption("ℹ️ *Top 4 clasifican al Round Robin (Todos contra Todos). DIFF = Diferencial de Carreras.*")

    with col_right:
        st.subheader("⚡ Power Rankings ELO")
        df_elo = pd.DataFrame(power_rankings)
        fig_elo = px.bar(
            df_elo,
            x="elo",
            y="short_name",
            orientation="h",
            text="elo",
            color="short_name",
            color_discrete_map={r["short_name"]: r["primary_color"] for r in power_rankings},
        )
        fig_elo.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(13, 21, 43, 0.4)",
            font=dict(color="#FFFFFF", family="Inter"),
            xaxis=dict(title="Rating ELO", gridcolor="rgba(255,255,255,0.06)", range=[1440, 1560]),
            yaxis=dict(title="", autorange="reversed"),
            showlegend=False,
            margin=dict(l=10, r=20, t=10, b=10),
            height=280,
        )
        fig_elo.update_traces(texttemplate='%{text:.1f}', textposition='outside')
        st.plotly_chart(fig_elo, use_container_width=True)

    st.markdown("---")

    # Sección Monte Carlo
    st.subheader("🎲 Proyecciones Monte Carlo (5,000 Simulaciones)")
    st.markdown("Proyecciones de avance al **Round Robin**, clasificación a la **Serie Final** y probabilidad de **Campeonato**.")

    # Convertir standings a diccionario para alimentar simulación
    standings_dict = {}
    for _, row in df_standings.iterrows():
        standings_dict[int(row["team_id"])] = {"wins": int(row["W"]), "games": int(row["G"])}

    mc_results = elo_engine.run_monte_carlo_simulation(current_standings=standings_dict, iterations=5000)
    df_mc = pd.DataFrame(mc_results["projections"])

    # Gráfico agrupado de probabilidades
    fig_mc = go.Figure()
    fig_mc.add_trace(go.Bar(
        name="Clasifica Round Robin (Top 4)",
        x=df_mc["short_name"],
        y=df_mc["round_robin_pct"],
        marker_color="#38BDF8",
        text=df_mc["round_robin_pct"].apply(lambda v: f"{v:.1f}%"),
        textposition="auto",
    ))
    fig_mc.add_trace(go.Bar(
        name="Llega a la Serie Final",
        x=df_mc["short_name"],
        y=df_mc["finals_pct"],
        marker_color="#F59E0B",
        text=df_mc["finals_pct"].apply(lambda v: f"{v:.1f}%"),
        textposition="auto",
    ))
    fig_mc.add_trace(go.Bar(
        name="Probabilidad de Campeón",
        x=df_mc["short_name"],
        y=df_mc["champion_pct"],
        marker_color="#10B981",
        text=df_mc["champion_pct"].apply(lambda v: f"{v:.1f}%"),
        textposition="auto",
    ))

    fig_mc.update_layout(
        barmode="group",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(13, 21, 43, 0.4)",
        font=dict(color="#FFFFFF", family="Inter"),
        yaxis=dict(title="Probabilidad (%)", gridcolor="rgba(255,255,255,0.06)", range=[0, 105]),
        xaxis=dict(title=""),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=10, r=10, t=30, b=10),
        height=360,
    )
    st.plotly_chart(fig_mc, use_container_width=True)

    # Tabla resumen
    st.dataframe(
        df_mc[["name", "round_robin_pct", "finals_pct", "champion_pct"]].rename(columns={
            "name": "Equipo",
            "round_robin_pct": "P(Round Robin)",
            "finals_pct": "P(Serie Final)",
            "champion_pct": "P(Campeón)",
        }),
        use_container_width=True,
        hide_index=True,
    )
