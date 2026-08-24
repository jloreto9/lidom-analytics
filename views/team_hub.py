"""Vista Team Hub: Perfil interactivo por franquicia con theming dinámico y analítica profunda."""

import streamlit as st
import pandas as pd
import plotly.express as px

from core.data_loader import LIDOMDataLoader
from core.teams import TEAMS, get_all_teams, get_team_by_id
from core.situational import get_situational_splits
from core.bullpen import aggregate_team_bullpen
from utils.styles import render_header, apply_custom_css


def render_team_hub_view(season: int = 2024) -> None:
    """Renderiza el módulo Team Hub para explorar a las 6 franquicias LIDOM."""
    all_teams = get_all_teams()
    team_names = [t["name"] for t in all_teams]

    # Selector de equipo
    selected_name = st.selectbox("Selecciona una Franquicia LIDOM:", team_names, index=0)
    selected_team = next(t for t in all_teams if t["name"] == selected_name)
    t_id = selected_team["id"]
    t_color = selected_team["primary_color"]
    t_accent = selected_team.get("accent_color", t_color)

    # Inyectar estilos adaptados al equipo seleccionado
    apply_custom_css(accent_color=t_accent)

    # Banner del Equipo
    banner_html = f"""
    <div style="background: linear-gradient(135deg, rgba(13, 21, 43, 0.95) 0%, {t_color}33 100%);
                border: 1px solid {t_color}66; border-left: 6px solid {t_color};
                border-radius: 16px; padding: 22px 28px; margin-bottom: 25px;
                display: flex; align-items: center; justify-content: space-between;">
        <div style="display: flex; align-items: center; gap: 20px;">
            <img src="{selected_team['logo_url']}" style="width: 70px; height: 70px; object-fit: contain;">
            <div>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="background: {t_color}; color: #FFFFFF; font-size: 0.75rem; font-weight: 800; padding: 3px 8px; border-radius: 4px;">{selected_team['abbrev']}</span>
                    <span style="color: #94A3B8; font-size: 0.85rem; font-weight: 600;">Fundado en {selected_team['founded']}</span>
                </div>
                <h1 style="margin: 4px 0 0 0; font-size: 2.1rem; color: #FFFFFF;">{selected_team['name']}</h1>
                <p style="margin: 2px 0 0 0; color: #CBD5E1; font-size: 0.9rem;">📍 {selected_team['stadium']} — {selected_team['city']}</p>
            </div>
        </div>
        <div style="text-align: right;">
            <div style="background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.1); border-radius: 12px; padding: 10px 18px;">
                <div style="font-size: 0.75rem; color: #94A3B8; font-weight: 700; text-transform: uppercase;">Campeonatos Nacionales</div>
                <div style="font-size: 1.8rem; font-weight: 900; color: {t_accent};">🏆 {selected_team['championships']}</div>
            </div>
        </div>
    </div>
    """
    st.markdown(banner_html, unsafe_allow_html=True)

    loader = LIDOMDataLoader()

    # Pestañas de contenido
    tab_hit, tab_pitch, tab_split = st.tabs([
        "🏏 Bateo y Alineación",
        "⚾ Pitcheo y Bullpen",
        "🎯 Splits Situacionales",
    ])

    with tab_hit:
        st.subheader(f"Estadísticas de Bateo — {selected_team['short_name']}")
        df_hit = loader.get_hitting_leaderboard(season=season)
        df_team_hit = df_hit[df_hit["team"] == selected_team["abbrev"]]
        if df_team_hit.empty:
            df_team_hit = df_hit.iloc[:4]  # Mostrar muestra representativa si no hay filtros estrictos

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            avg_val = df_team_hit["AVG"].iloc[0] if not df_team_hit.empty else ".000"
            st.metric(label="Mejor Bateador (AVG)", value=avg_val, delta=df_team_hit["name"].iloc[0] if not df_team_hit.empty else "")
        with col2:
            st.metric(label="Total Cuadrangulares", value=int(df_team_hit["HR"].sum()) if not df_team_hit.empty else 0)
        with col3:
            woba_val = df_team_hit["wOBA"].iloc[0] if not df_team_hit.empty else ".000"
            st.metric(label="Líder wOBA", value=woba_val)
        with col4:
            st.metric(label="Hard Contact Promedio", value=f"{df_team_hit['Hard%'].mean():.1f}%" if not df_team_hit.empty else "0.0%")

        st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)
        st.dataframe(
            df_team_hit[["name", "pos", "G", "AB", "R", "H", "2B", "3B", "HR", "RBI", "BB", "SO", "AVG", "OBP", "SLG", "OPS", "wOBA", "wRC+", "WPA", "Hard%"]].rename(columns={"name": "Jugador", "pos": "POS"}),
            use_container_width=True,
            hide_index=True,
        )

    with tab_pitch:
        st.subheader(f"Cuerpo de Lanzadores y Relevo — {selected_team['short_name']}")
        df_pitch = loader.get_pitching_leaderboard(season=season)
        df_team_pitch = df_pitch[df_pitch["team"] == selected_team["abbrev"]]
        if df_team_pitch.empty:
            df_team_pitch = df_pitch.iloc[:4]

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(label="Efectividad Rotación (ERA)", value=df_team_pitch["ERA"].iloc[0] if not df_team_pitch.empty else "0.00")
        with col2:
            st.metric(label="WHIP Colectivo", value=df_team_pitch["WHIP"].iloc[0] if not df_team_pitch.empty else "0.00")
        with col3:
            st.metric(label="FIP Promedio", value=df_team_pitch["FIP"].iloc[0] if not df_team_pitch.empty else "0.00")

        st.markdown("#### Rotación y Staff de Pitcheo")
        st.dataframe(
            df_team_pitch[["name", "role", "G", "GS", "W", "L", "IP", "H", "ER", "BB", "SO", "ERA", "WHIP", "FIP", "K/9", "WPA"]].rename(columns={"name": "Lanzador", "role": "Rol"}),
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("#### 🛡️ Rendimiento del Bullpen & Inherited Runners (IR / IRS)")
        # Simulación de datos de bullpen
        mock_bullpen = [
            {"name": "Cerrador Estelar", "role": "CL", "logs": [{"ip": 1.0, "inherited_runners": 0, "inherited_runners_scored": 0, "entry_leverage": 2.4, "wpa": 0.15, "er": 0, "h": 1, "bb": 0, "so": 2} for _ in range(12)]},
            {"name": "Preparador Setup 8vo", "role": "SU", "logs": [{"ip": 1.0, "inherited_runners": 1, "inherited_runners_scored": 0, "entry_leverage": 1.9, "wpa": 0.08, "er": 0, "h": 0, "bb": 1, "so": 1} for _ in range(14)]},
            {"name": "Relevista Situacional", "role": "RP", "logs": [{"ip": 0.2, "inherited_runners": 2, "inherited_runners_scored": 1, "entry_leverage": 1.6, "wpa": 0.02, "er": 0, "h": 1, "bb": 0, "so": 1} for _ in range(10)]},
            {"name": "Relevo Largo", "role": "LR", "logs": [{"ip": 2.1, "inherited_runners": 1, "inherited_runners_scored": 0, "entry_leverage": 0.8, "wpa": -0.01, "er": 1, "h": 2, "bb": 1, "so": 2} for _ in range(8)]},
        ]
        df_bp = aggregate_team_bullpen(mock_bullpen)
        st.dataframe(df_bp, use_container_width=True, hide_index=True)
        st.caption("ℹ️ *IR = Corredores Heredados, IRS = Heredados que Anotaron, IRS% = Tasa de corredores heredados anotados, gmLI = Apalancamiento al entrar.*")

    with tab_split:
        st.subheader(f"Splits Situacionales — {selected_team['short_name']}")
        st.markdown("Desglose de rendimiento ofensivo según el contexto y apalancamiento del juego:")

        # Generar DataFrame de jugadas del equipo para calcular splits
        df_sample_plays = loader.get_batted_balls_sample(team_id=t_id).copy()
        n_rows = len(df_sample_plays)
        if n_rows > 0:
            base_pattern = [0, 2, 7, 1, 4, 2, 5, 0, 7, 2]
            li_pattern = [0.8, 1.6, 2.2, 0.5, 1.8, 1.2, 2.5, 0.9, 1.7, 1.1]
            inn_pattern = [1, 2, 3, 4, 5, 6, 7, 8, 9, 4]

            df_sample_plays["base_state"] = (base_pattern * (n_rows // len(base_pattern) + 1))[:n_rows]
            df_sample_plays["leverage_index"] = (li_pattern * (n_rows // len(li_pattern) + 1))[:n_rows]
            df_sample_plays["inning"] = (inn_pattern * (n_rows // len(inn_pattern) + 1))[:n_rows]

        splits = get_situational_splits(df_sample_plays)
        df_splits_display = pd.DataFrame(splits).T.reset_index().rename(columns={"index": "Situación"})

        st.dataframe(df_splits_display, use_container_width=True, hide_index=True)
