"""
views/pitching.py
-----------------
Módulo avanzado de Pitching Summary & Telemetría Sabermétrica para LIDOM 360,
inspirado en el diseño original de Thomas Nestico (@TJStats).

Soporta:
1. Búsqueda universal de lanzadores (LIDOM, México LMB, MLB/MiLB).
2. Arquitectura de triple rama:
   - 🇩🇴 LIDOM: Play-by-Play oficial (Carga por entrada, Leverage Index Tango RE24, Platoon splits).
   - 🇲🇽 México: LMB Verano (Decisiones oficiales W/L/SV/HLD, conteo P-S, CSW%, Whiff%).
   - ⚾ MLB / MiLB: Telemetría Statcast completa (Velo KDEs, Spin, IVB, HB, Whiff%, CSW%, Rolling Usage).
3. Tres modos temporales: Salida Individual, Temporada Completa y Rango de Fechas.
4. Generación y descarga de tarjetas HD (2400x2400 px a 300 DPI) con branding oficial de LIDOM 360.
"""

import os
import io
import datetime
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

from core.pitching_engine import (
    search_pitchers,
    get_pitcher_by_id,
    get_pitcher_game_logs,
    get_game_pitch_data,
    get_pitcher_season_statcast_df,
    get_lidom_pitcher_statcast_df,
    get_pitch_analysis_for_df,
    get_available_seasons as get_engine_seasons,
    LIDOM_TEAMS,
    LIDOM_ABBR,
)
from core.pitching_card import (
    build_pitching_summary_card,
    _get_pitch_color,
)
from core.teams import get_all_teams, get_team_by_id, get_team_color, get_team_logo
from utils.styles import render_header


def render_pitching_view(season: int = 2026) -> None:
    """Renderiza la suite completa de Pitching Summary & Telemetría en LIDOM 360."""
    render_header(
        title="Pitching Summary & Telemetría",
        subtitle="Suite sabermétrica avanzada inspirada en Thomas Nestico (@TJStats) • Repertorio, decisiones y telemetría",
        badge_text="TELEMETRÍA NESTICO",
        season=season,
    )

    # ── Estado de Sesión ────────────────────────────────────────────────────────
    if "selected_pitcher" not in st.session_state:
        st.session_state["selected_pitcher"] = None
    if "active_branch" not in st.session_state:
        st.session_state["active_branch"] = "lidom"
    if "pitcher_season" not in st.session_state:
        st.session_state["pitcher_season"] = 2026
    if "time_mode" not in st.session_state:
        st.session_state["time_mode"] = "season"
    if "pitcher_phase" not in st.session_state:
        st.session_state["pitcher_phase"] = "all"
    if "selected_game_pk" not in st.session_state:
        st.session_state["selected_game_pk"] = None
    if "range_dates" not in st.session_state:
        st.session_state["range_dates"] = (
            datetime.date(2026, 4, 1),
            datetime.date(2026, 10, 31)
        )

    # ── Panel Superior de Controles y Rama ─────────────────────────────────────
    col_branch, col_season, col_phase, col_mode = st.columns([1.8, 1.2, 1.5, 1.5])

    with col_branch:
        branch_opts = {
            "🇩🇴 LIDOM": "lidom",
            "🇲🇽 México (LMB)": "mexico",
            "⚾ MLB / MiLB": "mlb"
        }
        active_label = [k for k, v in branch_opts.items() if v == st.session_state["active_branch"]]
        active_label = active_label[0] if active_label else "🇩🇴 LIDOM"
        sel_branch_label = st.selectbox(
            "Liga / Ámbito:",
            list(branch_opts.keys()),
            index=list(branch_opts.keys()).index(active_label),
            key="sb_branch_select"
        )
        active_branch = branch_opts[sel_branch_label]
        st.session_state["active_branch"] = active_branch

    with col_season:
        available_seasons = get_engine_seasons()
        cur_season = st.session_state["pitcher_season"]
        s_idx = available_seasons.index(cur_season) if cur_season in available_seasons else 0
        sel_season = st.selectbox(
            "Temporada:",
            available_seasons,
            index=s_idx,
            key="sb_season_select",
            format_func=lambda s: f"Temporada {s}"
        )
        season_int = int(sel_season)
        st.session_state["pitcher_season"] = season_int

    with col_phase:
        phase_map = {
            "Todas las Fases": "all",
            "Serie Regular": "R",
            "Round Robin": "W" if active_branch == "lidom" else "L",
            "Serie Final": "F",
        }
        cur_phase = st.session_state["pitcher_phase"]
        p_label_cur = [k for k, v in phase_map.items() if v == cur_phase]
        p_label_cur = p_label_cur[0] if p_label_cur else "Todas las Fases"
        sel_phase_label = st.selectbox(
            "Fase:",
            list(phase_map.keys()),
            index=list(phase_map.keys()).index(p_label_cur),
            key="sb_phase_select"
        )
        selected_phase = phase_map[sel_phase_label]
        st.session_state["pitcher_phase"] = selected_phase

    with col_mode:
        mode_map = {
            "Temporada": "season",
            "Salida Individual": "game",
            "Rango de Fechas": "range"
        }
        cur_mode = st.session_state["time_mode"]
        m_label_cur = [k for k, v in mode_map.items() if v == cur_mode]
        m_label_cur = m_label_cur[0] if m_label_cur else "Temporada"
        sel_mode_label = st.selectbox(
            "Alcance:",
            list(mode_map.keys()),
            index=list(mode_map.keys()).index(m_label_cur),
            key="sb_mode_select"
        )
        time_mode = mode_map[sel_mode_label]
        st.session_state["time_mode"] = time_mode

    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

    # ── Buscador de Lanzadores ──────────────────────────────────────────────────
    col_search, col_p_sel = st.columns([2, 3])

    with col_search:
        search_query = st.text_input(
            "🔍 Buscar Lanzador (Nombre o Apellido):",
            placeholder="Ej: César Valdez, Framber Valdez, Junior Guerra...",
            key="input_pitcher_search",
        )

    with col_p_sel:
        search_res = []
        if search_query and len(search_query.strip()) >= 2:
            with st.spinner("Buscando lanzador..."):
                search_res = search_pitchers(search_query)
        else:
            # Lista de lanzadores sugeridos
            default_p_ids = [
                491624,  # César Valdez (Licey)
                467657,  # Esmil Rogers (Toros)
                467655,  # Radhamés Liz (Licey/Toros)
                448855,  # Raúl Valdés (Toros)
                446454,  # Jairo Asencio (Licey)
                628711,  # Enny Romero (Águilas)
                642547,  # Framber Valdez (Astros / LIDOM)
                661563,  # Luis Gil (Yankees / Licey)
                642547,  # Freddy Peralta (Brewers / Toros)
                656302,  # Cristopher Sánchez (Phillies / Toros)
                678394,  # Brayan Bello (Red Sox / Toros)
                666374,  # Ronel Blanco (Astros / Estrellas)
                622491,  # Luis Castillo (Mariners / Águilas)
                622075,  # Erick Leal (LIDOM / LMB)
                457918,  # Junior Guerra (LMB)
                544150,  # Albert Suárez (Orioles)
            ]
            for pid in default_p_ids:
                p_obj = get_pitcher_by_id(pid)
                if p_obj:
                    search_res.append(p_obj)

        pitcher_opts = {
            f"{p['name']} ({p.get('team_name', 'Agente Libre')} • {p.get('pitch_hand', 'R')}HP)": p
            for p in search_res
        }

        if pitcher_opts:
            sel_p_name = st.selectbox(
                "Seleccionar Lanzador:",
                list(pitcher_opts.keys()),
                key="select_pitcher_box"
            )
            selected_pitcher = pitcher_opts[sel_p_name]
            st.session_state["selected_pitcher"] = selected_pitcher
        else:
            st.warning("No se encontraron lanzadores con ese nombre.")
            selected_pitcher = st.session_state.get("selected_pitcher")

    if not selected_pitcher:
        st.info("👈 Por favor selecciona o busca un lanzador en el panel superior para comenzar.")
        return

    p_id = selected_pitcher["id"]
    p_name = selected_pitcher["name"]

    # ── Tarjeta de Presentación del Lanzador ────────────────────────────────────
    col_bio_img, col_bio_txt = st.columns([1, 5])
    with col_bio_img:
        st.markdown(
            f"""
            <div style="text-align: center; background: rgba(13, 21, 43, 0.7); border-radius: 12px; padding: 10px; border: 1px solid rgba(255,255,255,0.08);">
                <img src="{selected_pitcher.get('photo_url', '')}" style="width: 110px; height: auto; border-radius: 50%; filter: drop-shadow(0 4px 10px rgba(0,0,0,0.5));">
            </div>
            """,
            unsafe_allow_html=True
        )

    with col_bio_txt:
        p_hand = selected_pitcher.get('pitch_hand', 'R')
        team_display = selected_pitcher.get('team_name', 'LIDOM')
        st.markdown(f"""
        <div style="padding-left: 10px;">
            <h2 style="margin: 0; color: #FFFFFF; font-size: 1.8rem; font-weight: 800;">{p_name}</h2>
            <p style="margin: 4px 0 8px 0; color: #38BDF8; font-size: 0.95rem; font-weight: 700;">
                {p_hand}HP • {selected_pitcher.get('height', "6' 2\"")} / {selected_pitcher.get('weight', 200)} lbs • Edad: {selected_pitcher.get('age', 28)}
            </p>
            <div style="display: flex; gap: 8px; align-items: center;">
                <span class="badge-pill" style="background: rgba(0, 85, 184, 0.25); color: #38BDF8; border: 1px solid #0055B8;">
                    {team_display}
                </span>
                <span class="badge-pill" style="background: rgba(255, 255, 255, 0.05); color: #94A3B8;">
                    MLB ID: {p_id}
                </span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # ── Carga de Salidas (Game Logs) ─────────────────────────────────────────────
    with st.spinner(f"Cargando historial de salidas de {p_name}..."):
        game_logs = get_pitcher_game_logs(
            p_id,
            season=season_int,
            is_lidom=(active_branch == "lidom"),
            branch=active_branch,
            phase=selected_phase,
        )

    effective_season = season_int
    fallback_used = False
    if not game_logs and selected_phase == "all":
        fallback_candidates = [s for s in available_seasons if s != season_int]
        for fallback_s in fallback_candidates:
            test_logs = get_pitcher_game_logs(
                p_id,
                season=fallback_s,
                is_lidom=(active_branch == "lidom"),
                branch=active_branch,
                phase="all"
            )
            if test_logs:
                effective_season = fallback_s
                game_logs = test_logs
                fallback_used = True
                if not (active_branch == "lidom" and season_int == 2026):
                    st.session_state["pitcher_season"] = fallback_s
                break

    if fallback_used and active_branch == "lidom" and season_int == 2026:
        st.info(
            f"ℹ️ La temporada 2026-2027 de la LIDOM comienza en octubre de 2026 (aún sin salidas disputadas). "
            f"Mostrando la última actuación en LIDOM (Temporada {effective_season}). "
            f"Para ver lo que hizo este año 2026 en verano, puedes consultar las ramas de **🇲🇽 México** o **⚾ MLB / MiLB**."
        )

    # ── Configuración de Modo Temporal ──────────────────────────────────────────
    selected_game_summary = {}
    current_game_pk = None

    if time_mode == "game":
        if game_logs:
            opts_dict = {
                f"{g.get('date', '')} vs {g.get('opponent', '')} ({g.get('ip', 0)} IP, {g.get('so', 0)} K, {g.get('pitches', 0)} P)": g
                for g in game_logs
            }
            selected_label = st.selectbox("Seleccionar Salida:", list(opts_dict.keys()), key="select_game_log")
            selected_game_summary = opts_dict[selected_label]
            current_game_pk = selected_game_summary.get("game_pk")
            st.session_state["selected_game_pk"] = current_game_pk
        else:
            st.warning(f"No se encontraron salidas registradas para la temporada {effective_season}.")
    elif time_mode == "range":
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            s_date = st.date_input("Fecha Inicio:", datetime.date(effective_season, 4, 1))
        with col_d2:
            e_date = st.date_input("Fecha Fin:", datetime.date(effective_season, 10, 31))
        st.session_state["range_dates"] = (s_date, e_date)

    # ── Extracción Analítica de Pitcheos ────────────────────────────────────────
    pitch_analysis = {}
    df_statcast_season = pd.DataFrame()

    if active_branch == "lidom":
        with st.spinner("Consultando telemetría TrackMan en LIDOM..."):
            df_statcast_season = get_lidom_pitcher_statcast_df(
                p_id,
                season=effective_season,
                mode=time_mode,
                game_pk=current_game_pk,
                phase=selected_phase,
                start_date=str(st.session_state["range_dates"][0]) if time_mode == "range" else None,
                end_date=str(st.session_state["range_dates"][1]) if time_mode == "range" else None,
            )
            if not df_statcast_season.empty and len(df_statcast_season[df_statcast_season["release_speed"].notna()]) >= 5:
                pitch_analysis = get_pitch_analysis_for_df(df_statcast_season)
            elif time_mode == "game" and current_game_pk:
                pitch_analysis = get_game_pitch_data(current_game_pk, p_id, is_lidom=True)
    elif active_branch == "mexico":
        if time_mode == "game" and current_game_pk:
            with st.spinner("Analizando pitcheo a pitcheo de la salida LMB..."):
                pitch_analysis = get_game_pitch_data(current_game_pk, p_id, is_lidom=False)
    elif active_branch == "mlb":
        if time_mode == "game" and current_game_pk:
            with st.spinner("Analizando salida MLB..."):
                pitch_analysis = get_game_pitch_data(current_game_pk, p_id, is_lidom=False)
                df_statcast_season = get_pitcher_season_statcast_df(
                    p_id, season=effective_season, mode="game", game_pk=current_game_pk
                )
        else:
            with st.spinner("Descargando lanzamientos Statcast MLB..."):
                df_statcast_season = get_pitcher_season_statcast_df(p_id, season=effective_season)
                if time_mode == "range" and not df_statcast_season.empty and "game_date" in df_statcast_season.columns:
                    s_str = str(st.session_state["range_dates"][0])
                    e_str = str(st.session_state["range_dates"][1])
                    df_statcast_season = df_statcast_season[(df_statcast_season["game_date"] >= s_str) & (df_statcast_season["game_date"] <= e_str)]
                pitch_analysis = get_pitch_analysis_for_df(df_statcast_season)

    # ── KPIs Resumidos ──────────────────────────────────────────────────────────
    if game_logs:
        tot_outs = sum(_ip_str_to_outs(g.get("ip", "0.0")) for g in game_logs)
        tot_ip = f"{tot_outs // 3}.{tot_outs % 3}"
        float_ip = tot_outs / 3.0
        tot_er = sum(int(g.get("er", 0)) for g in game_logs)
        tot_h = sum(int(g.get("h", 0)) for g in game_logs)
        tot_bb = sum(int(g.get("bb", 0)) for g in game_logs)
        tot_so = sum(int(g.get("so", 0)) for g in game_logs)
        tot_pitches = sum(int(g.get("pitches", 0)) for g in game_logs)

        era_kpi = f"{(tot_er * 9.0 / float_ip):.2f}" if float_ip > 0 else "0.00"
        whip_kpi = f"{((tot_bb + tot_h) / float_ip):.2f}" if float_ip > 0 else "0.00"

        c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
        c1.metric("Entradas (IP)", tot_ip)
        c2.metric("Salidas (G)", len(game_logs))
        c3.metric("Efectividad (ERA)", era_kpi)
        c4.metric("WHIP", whip_kpi)
        c5.metric("Ponches (SO)", tot_so)
        c6.metric("Boletos (BB)", tot_bb)
        c7.metric("Total Pitcheos", tot_pitches)

    has_lidom_sc = (active_branch == "lidom" and not df_statcast_season.empty and len(df_statcast_season[df_statcast_season["release_speed"].notna()]) >= 5)
    selected_card_type = "pbp"

    if has_lidom_sc:
        st.success(
            f"📡 **Telemetría Statcast (TrackMan LIDOM) Activa**: {len(df_statcast_season)} pitcheos capturados por radar en Quisqueya, Cibao o Tetelo Vargas."
        )
        card_choice = st.radio(
            "Seleccionar Formato de Tarjeta HD para LIDOM:",
            ["📡 Resumen Statcast (TrackMan / Nestico)", "📋 Bitácora PBP & Control (Salidas)"],
            horizontal=True,
            key=f"lidom_card_choice_{p_id}_{effective_season}"
        )
        selected_card_type = "statcast" if "Statcast" in card_choice else "pbp"
    elif active_branch == "lidom":
        st.info(
            "ℹ️ No se registraron lanzamientos con radar TrackMan en la API pública para esta selección en LIDOM (los estadios Quisqueya, Cibao y Tetelo Vargas cuentan con radar activo). Desplegando **Bitácora PBP & Control**."
        )
        selected_card_type = "pbp"
    elif active_branch == "mlb":
        selected_card_type = "statcast"
    else:
        selected_card_type = "pbp"

    st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)

    # ── Pestañas de Visualización y Tarjetas HD ─────────────────────────────────
    tab_summary, tab_splits, tab_card = st.tabs([
        "📊 Bitácora de Salidas & Métricas",
        "🎯 Splits, Quiebres & Strike Zone",
        "🖼️ Tarjeta HD Nestico (Descargar)",
    ])

    with tab_summary:
        if (has_lidom_sc or active_branch == "mlb") and not df_statcast_season.empty:
            st.markdown("### 📡 Métricas Sabermétricas de Repertorio (Statcast / TrackMan)")
            sc_table = pitch_analysis.get("statcast_table", [])
            if sc_table:
                st.dataframe(pd.DataFrame(sc_table), use_container_width=True, hide_index=True)

        if game_logs:
            st.markdown("### 📋 Historial de Salidas en la Temporada")
            df_logs = pd.DataFrame(game_logs)
            cols_show = [c for c in ["date", "opponent", "role", "decision", "ip", "h", "r", "er", "bb", "so", "pitches", "era", "league"] if c in df_logs.columns]
            df_disp = df_logs[cols_show].rename(columns={
                "date": "Fecha",
                "opponent": "Rival",
                "role": "Rol",
                "decision": "Dec.",
                "ip": "IP",
                "h": "H",
                "r": "C",
                "er": "CL",
                "bb": "BB",
                "so": "K",
                "pitches": "Pitcheos",
                "era": "ERA",
                "league": "Liga",
            })
            st.dataframe(df_disp, use_container_width=True, hide_index=True)
        else:
            st.info("No se encontraron registros de salidas en este período.")

    with tab_splits:
        if (has_lidom_sc or active_branch == "mlb") and not df_statcast_season.empty and "pfx_x" in df_statcast_season.columns and "pfx_z" in df_statcast_season.columns:
            st.markdown("### 🔄 Mapa de Quiebres (Short-Form Pitch Breaks)")
            fig_breaks = go.Figure()
            for pt in df_statcast_season["pitch_name"].unique():
                sub_df = df_statcast_season[df_statcast_season["pitch_name"] == pt]
                fig_breaks.add_trace(go.Scatter(
                    x=sub_df["pfx_x"],
                    y=sub_df["pfx_z"],
                    mode="markers",
                    name=str(pt),
                    marker=dict(size=8, opacity=0.75),
                    hovertemplate="%{x:.1f} in HB, %{y:.1f} in iVB<extra>" + str(pt) + "</extra>"
                ))
            fig_breaks.add_hline(y=0, line_dash="dash", line_color="#94A3B8")
            fig_breaks.add_vline(x=0, line_dash="dash", line_color="#94A3B8")
            fig_breaks.update_layout(
                xaxis_title="Horizontal Break (in) [← Guante | Brazo →]",
                yaxis_title="Induced Vertical Break (in)",
                xaxis=dict(range=[-25, 25]),
                yaxis=dict(range=[-25, 25]),
                paper_bgcolor="#070B19",
                plot_bgcolor="#0D152B",
                font=dict(color="#F8FAFC"),
                margin=dict(l=20, r=20, t=30, b=20),
                height=450,
            )
            st.plotly_chart(fig_breaks, use_container_width=True)

        st.markdown("### ⚖️ Destinos del Pitcheo & Apalancamiento")
        pbp_table = pitch_analysis.get("pbp_table", [])
        if pbp_table:
            st.dataframe(pd.DataFrame(pbp_table), use_container_width=True, hide_index=True)

        splits_platoon = pitch_analysis.get("splits_platoon", {})
        if splits_platoon:
            col_l, col_r = st.columns(2)
            with col_l:
                st.markdown("#### vs Bateadores Zurdos (LHB)")
                st.json(splits_platoon.get("LHB", {}))
            with col_r:
                st.markdown("#### vs Bateadores Derechos (RHB)")
                st.json(splits_platoon.get("RHB", {}))

    with tab_card:
        st.markdown("### 🖼️ Tarjeta Panorámica HD Nestico (@TJStats)")
        st.markdown(
            "*Tarjeta gráfica sabermétrica generada en Matplotlib a **2400 x 2400 px y 300 DPI**, "
            "optimizada para difusión ejecutiva, redes sociales y reportes de scouting.*"
        )

        with st.spinner("Renderizando tarjeta gráfica en alta resolución..."):
            card_bytes = build_pitching_summary_card(
                pitcher_info=selected_pitcher,
                game_summary=selected_game_summary,
                analysis=pitch_analysis,
                branch=active_branch,
                is_lidom=(active_branch == "lidom"),
                is_mexico=(active_branch == "mexico"),
                mode=time_mode,
                game_logs=game_logs,
                start_date=str(st.session_state["range_dates"][0]) if time_mode == "range" else None,
                end_date=str(st.session_state["range_dates"][1]) if time_mode == "range" else None,
                season=effective_season,
                df_statcast=df_statcast_season,
                phase=selected_phase,
                card_type=selected_card_type,
            )

        st.image(card_bytes, use_container_width=True)

        safe_name = "".join(c for c in p_name if c.isalnum() or c == "_")
        league_tag = "MEX" if active_branch == "mexico" else ("LIDOM" if active_branch == "lidom" else "MLB")
        file_label = f"PitchingSummary_{safe_name}_{league_tag}_{effective_season}_{time_mode}.png"

        st.download_button(
            label="📥 Descargar Tarjeta HD (PNG 300 DPI)",
            data=card_bytes,
            file_name=file_label,
            mime="image/png",
            use_container_width=True,
        )


def _ip_str_to_outs(ip_val: Any) -> int:
    try:
        s = str(ip_val).strip()
        if '.' in s:
            parts = s.split('.')
            return int(parts[0]) * 3 + int(parts[1])
        return int(float(s)) * 3
    except Exception:
        return 0
