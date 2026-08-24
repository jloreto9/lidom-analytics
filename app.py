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
from views.versus import render_versus_view
from views.game_center import render_game_center_view
from views.spray_charts import render_spray_charts_view

# Aplicar estilos base globales
apply_custom_css(accent_color="#0055B8")

import os
import base64

# ----------------- SIDEBAR ----------------- #
with st.sidebar:
    png_path = os.path.join(os.path.dirname(__file__), "assets", "lidom_logo.png")
    if os.path.exists(png_path):
        with open(png_path, "rb") as f:
            png_b64 = base64.b64encode(f.read()).decode("utf-8")
        logo_img_tag = f'<img src="data:image/png;base64,{png_b64}" style="width: 85px; height: auto; max-height: 100px; object-fit: contain; margin-bottom: 12px; filter: drop-shadow(0px 4px 14px rgba(0,0,0,0.6));">'
    else:
        logo_img_tag = '<img src="https://img.mlbstatic.com/mlb-images/image/private/t_16x9/t_w1024/mlb/j79k5ddwnz4hgweev3x2.jpg" style="width: 85px; height: auto; object-fit: contain; margin-bottom: 12px;">'

    st.markdown(f"""
    <div style="text-align: center; padding: 10px 0 15px 0;">
        {logo_img_tag}
        <h2 style="margin: 0; color: #FFFFFF; font-size: 1.45rem; font-weight: 800; letter-spacing: -0.01em;">LIDOM 360</h2>
        <p style="margin: 2px 0 0 0; color: #38BDF8; font-size: 0.8rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase;">SABERMETRICS PLATFORM</p>
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
            "⚔️ Matchup 360 (Versus)",
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

    with st.expander("📚 Fuentes de Datos & Créditos"):
        st.markdown("""
        <div style="font-size: 0.78rem; color: #94A3B8; line-height: 1.5;">
            • <b>MLB Stats API:</b> Play-by-play oficial, boxscores, rosters y tracking en vivo (LIDOM League ID: 131, Sport ID: 17).<br>
            • <b>Tom Tango (The Book / RE24):</b> Matriz de expectativa de carreras (Run Expectancy) y modelos de Win Expectancy (WE) / WPA.<br>
            • <b>Baseball Info Solutions (BIS):</b> Calibración determinística de dureza de contacto (Batted Ball Hard/Med/Soft).<br>
            • <b>LIDOM:</b> Liga de Béisbol Profesional de la República Dominicana.
        </div>
        """, unsafe_allow_html=True)

    st.markdown("""
    <div style="text-align: center; color: #64748B; font-size: 0.75rem; margin-top: 10px;">
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
elif menu == "⚔️ Matchup 360 (Versus)":
    render_versus_view(season=season)
elif menu == "⚡ Game Center & WPA":
    render_game_center_view(season=season)
elif menu == "🎯 Spray Charts (Dureza BIS)":
    render_spray_charts_view(season=season)
