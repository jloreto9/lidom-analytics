"""Punto de entrada principal para LIDOM 360 — Plataforma Sabermétrica de Béisbol Dominicano."""

import streamlit as st

st.set_page_config(
    page_title="LIDOM 360 — Sabermetrics & Analytics",
    page_icon="⚾",
    layout="wide",
    initial_sidebar_state="expanded",
)

from utils.styles import apply_custom_css
from core.teams import get_all_teams
from views.home import render_home_view
from views.team_hub import render_team_hub_view
from views.leaderboards import render_leaderboards_view
from views.game_center import render_game_center_view
from views.spray_charts import render_spray_charts_view

# Aplicar estilos base globales
apply_custom_css(accent_color="#0055B8")

# ----------------- SIDEBAR ----------------- #
with st.sidebar:
    st.markdown("""
    <div style="text-align: center; padding: 10px 0 15px 0;">
        <img src="https://midfield.mlbstatic.com/v1/league/131/spots/240" style="width: 75px; height: 75px; object-fit: contain; margin-bottom: 8px; filter: drop-shadow(0px 4px 10px rgba(0,0,0,0.5));">
        <h2 style="margin: 0; color: #FFFFFF; font-size: 1.4rem;">LIDOM 360</h2>
        <p style="margin: 0; color: #38BDF8; font-size: 0.8rem; font-weight: 700; letter-spacing: 0.05em;">SABERMETRICS PLATFORM</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # Selector de Temporada
    season = st.selectbox(
        "📅 Temporada LIDOM:",
        [2025, 2024, 2023],
        index=0,
        format_func=lambda s: f"Temporada {s}-{s+1}",
    )

    st.markdown("### 🧭 Navegación")
    menu = st.radio(
        "Módulos:",
        [
            "🏠 Standings & Proyecciones",
            "🏟️ Team Hub (Franquicias)",
            "👑 Líderes Individuales",
            "⚡ Game Center & WPA",
            "🎯 Spray Charts (Dureza BIS)",
        ],
        index=0,
        label_visibility="collapsed",
    )

    st.markdown("---")

    st.markdown("### 🏆 Franquicias LIDOM")
    for team in get_all_teams():
        st.markdown(f"""
        <div style="display: flex; align-items: center; justify-content: space-between; padding: 4px 8px; margin-bottom: 4px; background: rgba(255,255,255,0.03); border-radius: 6px; border-left: 3px solid {team['primary_color']};">
            <span style="font-size: 0.85rem; color: #FFFFFF; font-weight: 600;">{team['short_name']}</span>
            <span style="font-size: 0.75rem; color: #94A3B8; font-weight: 700;">{team['abbrev']}</span>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #64748B; font-size: 0.75rem;">
        Desarrollado por <b>Jorge Leonardo Loreto</b><br>
        AI Data Scientist & Baseball Sabermetrician<br>
        <i>MLB Stats API &copy; 2026</i>
    </div>
    """, unsafe_allow_html=True)

# ----------------- ROUTING DE VISTAS ----------------- #
if menu == "🏠 Standings & Proyecciones":
    render_home_view(season=season)
elif menu == "🏟️ Team Hub (Franquicias)":
    render_team_hub_view(season=season)
elif menu == "👑 Líderes Individuales":
    render_leaderboards_view(season=season)
elif menu == "⚡ Game Center & WPA":
    render_game_center_view(season=season)
elif menu == "🎯 Spray Charts (Dureza BIS)":
    render_spray_charts_view(season=season)
