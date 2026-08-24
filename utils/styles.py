"""Estilos CSS de alta gama, tarjetas Glassmorphism y componentes visuales para LIDOM 360."""

import streamlit as st
from typing import Optional


def apply_custom_css(accent_color: str = "#0055B8") -> None:
    """Inyecta el sistema de diseño Dark Navy Glassmorphism en la app de Streamlit."""
    custom_css = f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Outfit:wght@400;500;600;700;800;900&display=swap');

    /* Variables y Reset */
    :root {{
        --bg-dark: #070B19;
        --card-bg: #0D152B;
        --card-border: rgba(255, 255, 255, 0.08);
        --accent: {accent_color};
        --accent-glow: rgba(0, 85, 184, 0.25);
        --text-primary: #FFFFFF;
        --text-secondary: #94A3B8;
    }}

    html, body, [class*="css"] {{
        font-family: 'Inter', sans-serif;
    }}

    h1, h2, h3, h4, h5, h6 {{
        font-family: 'Outfit', sans-serif;
        font-weight: 700;
        letter-spacing: -0.02em;
    }}

    /* Main Container */
    .stApp {{
        background-color: var(--bg-dark);
        color: var(--text-primary);
    }}

    /* Sidebar Styling */
    section[data-testid="stSidebar"] {{
        background-color: #050813 !important;
        border-right: 1px solid rgba(255, 255, 255, 0.06);
    }}

    /* Glassmorphism Metric Cards */
    div[data-testid="stMetric"] {{
        background: linear-gradient(135deg, rgba(13, 21, 43, 0.85) 0%, rgba(13, 21, 43, 0.5) 100%);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid var(--card-border);
        border-radius: 12px;
        padding: 16px 20px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.35);
        transition: transform 0.2s ease, border-color 0.2s ease;
    }}

    div[data-testid="stMetric"]:hover {{
        transform: translateY(-2px);
        border-color: rgba(255, 255, 255, 0.18);
    }}

    div[data-testid="stMetric"] label {{
        color: var(--text-secondary) !important;
        font-size: 0.82rem !important;
        font-weight: 600 !important;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }}

    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {{
        font-family: 'Outfit', sans-serif;
        font-size: 1.85rem !important;
        font-weight: 800 !important;
        color: #FFFFFF !important;
    }}

    /* Tabs Styling */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 8px;
        background-color: rgba(13, 21, 43, 0.6);
        padding: 6px;
        border-radius: 10px;
        border: 1px solid rgba(255, 255, 255, 0.05);
    }}

    .stTabs [data-baseweb="tab"] {{
        height: 40px;
        white-space: pre-wrap;
        background-color: transparent;
        border-radius: 8px;
        color: var(--text-secondary);
        font-size: 0.9rem;
        font-weight: 600;
        padding: 0 16px;
    }}

    .stTabs [aria-selected="true"] {{
        background: linear-gradient(135deg, {accent_color} 0%, rgba(13, 21, 43, 0.9) 100%) !important;
        color: #FFFFFF !important;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.3);
    }}

    /* Dataframe Styling */
    div[data-testid="stDataFrame"] {{
        border: 1px solid var(--card-border);
        border-radius: 12px;
        overflow: hidden;
        background: var(--card-bg);
    }}

    /* Custom KPI Card */
    .kpi-card {{
        background: linear-gradient(135deg, rgba(13, 21, 43, 0.9) 0%, rgba(13, 21, 43, 0.6) 100%);
        border: 1px solid var(--card-border);
        border-radius: 14px;
        padding: 20px;
        margin-bottom: 15px;
    }}

    .badge-pill {{
        display: inline-block;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 0.04em;
        text-transform: uppercase;
    }}

    /* Header Banner */
    .hero-banner {{
        background: linear-gradient(135deg, rgba(13, 21, 43, 0.95) 0%, rgba(7, 11, 25, 0.95) 100%);
        border: 1px solid var(--card-border);
        border-radius: 16px;
        padding: 24px 30px;
        margin-bottom: 25px;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }}
    </style>
    """
    st.markdown(custom_css, unsafe_allow_html=True)


def render_header(title: str, subtitle: str, badge_text: str = "LIDOM 360", accent_color: str = "#0055B8") -> None:
    """Renderiza una cabecera heroica con branding estilizado."""
    header_html = f"""
    <div class="hero-banner" style="border-left: 4px solid {accent_color};">
        <div>
            <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 8px;">
                <span class="badge-pill" style="background: {accent_color}; color: #FFFFFF;">{badge_text}</span>
                <span style="color: #64748B; font-size: 0.8rem; font-weight: 600;">SABERMETRICS PLATFORM</span>
            </div>
            <h1 style="margin: 0; font-size: 2rem; color: #FFFFFF;">{title}</h1>
            <p style="margin: 4px 0 0 0; color: #94A3B8; font-size: 0.95rem;">{subtitle}</p>
        </div>
        <div style="text-align: right; display: flex; align-items: center; gap: 12px;">
            <div style="background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; padding: 8px 14px;">
                <div style="font-size: 0.7rem; color: #64748B; font-weight: 700; text-transform: uppercase;">Temporada</div>
                <div style="font-size: 1.1rem; font-weight: 800; color: #FFFFFF;">2024-2025</div>
            </div>
        </div>
    </div>
    """
    st.markdown(header_html, unsafe_allow_html=True)


def render_team_badge(team_name: str, abbrev: str, color: str, logo_url: str = "") -> str:
    """Retorna el snippet HTML para renderizar el badge de un equipo con su color."""
    logo_img = f'<img src="{logo_url}" style="width: 22px; height: 22px; object-fit: contain; vertical-align: middle; margin-right: 6px;">' if logo_url else ''
    return f"""
    <div style="display: inline-flex; align-items: center; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 8px; padding: 4px 10px; margin-right: 6px;">
        {logo_img}
        <span style="font-weight: 700; color: {color}; margin-right: 6px;">{abbrev}</span>
        <span style="color: #FFFFFF; font-size: 0.85rem;">{team_name}</span>
    </div>
    """
