"""Vista Game Center: Matchups H2H, Boxscores y Gráfico Interactivo de Win Expectancy."""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from core.data_loader import LIDOMDataLoader
from core.teams import get_team_by_id
from utils.styles import render_header


def render_game_center_view(season: int = 2024) -> None:
    """Renderiza el centro de partidos y gráficos de Win Probability Added en vivo."""
    render_header(
        title="Game Center & Win Expectancy",
        subtitle="Boxscores interactivos, curvas de probabilidad de victoria y jugadas de alto apalancamiento",
        badge_text="LIDOM MATCHUP",
    )

    loader = LIDOMDataLoader()
    games = loader.get_schedule_games(season=season)

    # Selector de Partido
    game_options = [
        f"{g['date']} — {g['away_name']} ({g['away_score']}) @ {g['home_name']} ({g['home_score']})"
        for g in games
    ]
    selected_idx = st.selectbox("Selecciona un Partido de la Temporada:", range(len(game_options)), format_func=lambda x: game_options[x], index=0)
    selected_game = games[selected_idx]

    # Banner del Matchup
    h_meta = get_team_by_id(selected_game["home_id"])
    a_meta = get_team_by_id(selected_game["away_id"])

    h_col = h_meta["primary_color"] if h_meta else "#002D62"
    a_col = a_meta["primary_color"] if a_meta else "#FFCC00"

    banner_html = f"""
    <div style="background: linear-gradient(90deg, {a_col}44 0%, rgba(13, 21, 43, 0.95) 50%, {h_col}44 100%);
                border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 16px; padding: 25px 30px; margin-bottom: 25px;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <!-- Visitante -->
            <div style="display: flex; align-items: center; gap: 16px; flex: 1;">
                <img src="{selected_game['away_logo']}" style="width: 55px; height: 55px; object-fit: contain;">
                <div>
                    <div style="font-size: 0.8rem; color: #94A3B8; font-weight: 700;">VISITANTE</div>
                    <div style="font-size: 1.5rem; font-weight: 800; color: #FFFFFF;">{selected_game['away_name']}</div>
                </div>
            </div>
            <!-- Score Central -->
            <div style="text-align: center; padding: 0 20px;">
                <div style="font-size: 0.75rem; color: #38BDF8; font-weight: 800; text-transform: uppercase; letter-spacing: 0.05em;">{selected_game['status']} — {selected_game['date']}</div>
                <div style="font-size: 2.8rem; font-weight: 900; color: #FFFFFF; font-family: 'Outfit', sans-serif;">
                    {selected_game['away_score']} - {selected_game['home_score']}
                </div>
                <div style="font-size: 0.8rem; color: #94A3B8;">📍 {selected_game['venue']}</div>
            </div>
            <!-- Local -->
            <div style="display: flex; align-items: center; gap: 16px; justify-content: flex-end; flex: 1; text-align: right;">
                <div>
                    <div style="font-size: 0.8rem; color: #94A3B8; font-weight: 700;">LOCAL</div>
                    <div style="font-size: 1.5rem; font-weight: 800; color: #FFFFFF;">{selected_game['home_name']}</div>
                </div>
                <img src="{selected_game['home_logo']}" style="width: 55px; height: 55px; object-fit: contain;">
            </div>
        </div>
    </div>
    """
    st.markdown(banner_html, unsafe_allow_html=True)

    # Cargar Jugadas y Win Expectancy
    plays = loader.get_game_play_by_play(selected_game["game_pk"])
    df_plays = pd.DataFrame(plays)

    # Gráfico de Win Expectancy
    st.subheader("📈 Curva de Probabilidad de Victoria (Win Expectancy)")

    fig = go.Figure()
    # Línea base 50%
    fig.add_hline(y=0.50, line_dash="dash", line_color="rgba(255,255,255,0.2)", annotation_text="50% Empate")

    # Curva de Probabilidad Local
    fig.add_trace(go.Scatter(
        x=df_plays.index + 1,
        y=df_plays["we_home"],
        mode="lines+markers",
        name=f"Probabilidad {selected_game['home_name']}",
        line=dict(color=h_col if h_col != "#FFFFFF" else "#38BDF8", width=3, shape="spline"),
        marker=dict(size=6, color="#FFFFFF"),
        text=[f"Inning {r['inning']} ({r['half']})<br>{r['batter']} vs {r['pitcher']}<br><b>{r['event']}</b>: {r['description']}<br>WE Local: {r['we_home']*100:.1f}%<br>WPA: {r['wpa']:+.3f} | LI: {r['leverage']:.2f}" for _, r in df_plays.iterrows()],
        hoverinfo="text",
    ))

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(13, 21, 43, 0.4)",
        font=dict(color="#FFFFFF", family="Inter"),
        yaxis=dict(
            title=f"Probabilidad de Victoria — {selected_game['home_name']}",
            tickformat=".0%",
            range=[0, 1],
            gridcolor="rgba(255,255,255,0.06)",
        ),
        xaxis=dict(
            title="Secuencia de Jugadas (Play-by-Play)",
            gridcolor="rgba(255,255,255,0.06)",
        ),
        margin=dict(l=10, r=10, t=20, b=10),
        height=380,
    )
    st.plotly_chart(fig, use_container_width=True)

    # Jugadas Clave de Mayor Apalancamiento (Leverage Index)
    st.subheader("🔥 Jugadas Clave de Mayor Impacto (High Leverage)")
    top_plays = df_plays.sort_values(by="leverage", ascending=False).head(3)

    col_k1, col_k2, col_k3 = st.columns(3)
    for i, c in enumerate([col_k1, col_k2, col_k3]):
        if i < len(top_plays):
            p_row = top_plays.iloc[i]
            with c:
                st.metric(
                    label=f"Inning {p_row['inning']} ({p_row['half']}) — LI: {p_row['leverage']:.2f}",
                    value=f"{p_row['event']}",
                    delta=f"WPA: {p_row['wpa']:+.3f}",
                )
                st.caption(f"*{p_row['batter']} vs {p_row['pitcher']} — {p_row['description']}*")

    st.markdown("---")

    # Tabla Completa Play-by-Play
    st.subheader("📋 Registro Detallado de Jugadas (Play-by-Play)")
    st.dataframe(
        df_plays[["inning", "half", "outs", "batter", "pitcher", "event", "description", "score_away", "score_home", "we_home", "wpa", "leverage"]].rename(columns={
            "inning": "INN",
            "half": "Mitad",
            "outs": "Outs",
            "batter": "Bateador",
            "pitcher": "Lanzador",
            "event": "Evento",
            "description": "Descripción",
            "score_away": f"V ({selected_game['away_abbrev']})",
            "score_home": f"H ({selected_game['home_abbrev']})",
            "we_home": "WE Local",
            "wpa": "WPA",
            "leverage": "LI",
        }),
        use_container_width=True,
        hide_index=True,
    )
