# 🇩🇴 LIDOM 360 — Plataforma Sabermétrica & Analítica Integral

Plataforma analítica avanzada en **Streamlit** diseñada para la **Liga Dominicana de Béisbol Profesional (LIDOM)**, con cobertura exhaustiva para los 6 equipos de la pelota invernal dominicana.

---

## ⚾ Las 6 Franquicias LIDOM

| Franquicia | Team ID | Abreviatura | Colores | Sede / Estadio | Campeonatos |
|---|---|---|---|---|---|
| **Tigres del Licey** | `672` | `LIC` | `#002D62` / Blanco | Santo Domingo (Estadio Quisqueya Juan Marichal) | 24 |
| **Águilas Cibaeñas** | `667` | `AGU` | `#FFCC00` / Negro | Santiago de los Caballeros (Estadio Cibao) | 22 |
| **Leones del Escogido** | `671` | `ESC` | `#CC0000` / Blanco | Santo Domingo (Estadio Quisqueya Juan Marichal) | 16 |
| **Gigantes del Cibao** | `670` | `GIG` | `#5B1E31` / Oro | San Francisco de Macorís (Estadio Julián Javier) | 2 |
| **Estrellas Orientales** | `669` | `EST` | `#005A36` / Oro | San Pedro de Macorís (Estadio Tetelo Vargas) | 3 |
| **Toros del Este** | `668` | `TOR` | `#EA5B0C` / Negro | La Romana (Estadio Francisco Micheli) | 3 |

---

## 🚀 Características Principales

1. **Tabla de Posiciones y Power Rankings ELO**:
   - Standings oficiales con diferencial de carreras, % de victoria, racha y logotipos de franquicias integrados.
   - Power Rankings basados en algoritmo ELO dinámico calibrado con ventaja de localía ($+24$ pts) y multiplicador de margen de victoria.
2. **Simulaciones Monte Carlo (5,000 iteraciones)**:
   - Proyección estocástica de avance al **Round Robin** (Top 4), clasificación a la **Serie Final** y probabilidades de **Campeonato**.
3. **Team Hub Dinámico con Theming Contextual**:
   - Adaptación dinámica de los acentos visuales y CSS según la franquicia seleccionada.
   - Roster, estadísticas colectivas, rotación de abridores y métricas de **Bullpen e Inherited Runners (IR / IRS / IRS%)**.
4. **Líderes Individuales Sabermétricos (Leaderboards)**:
   - Métricas avanzadas: `wOBA`, `wRC+`, `WPA`, `FIP`, `WHIP`, `K/9`, `Hard Contact %`.
   - Gráficos interactivos de cuadrantes y dispersión de impacto ofensivo (`wOBA vs WPA`).
5. **⚔️ Matchup 360 (Versus / Comparador Head-to-Head)**:
   - Comparador cara a cara de peloteros (Bateadores vs Bateadores, Lanzadores vs Lanzadores) con fotos/headshots oficiales de MLB ID.
   - **Radar Polar 360° en Plotly (Dark Navy)** con percentiles normalizados 0-100 en 8 dimensiones clave.
   - **Tabla comparativa H2H 360°** estructurada por categorías (*Sabermetría & Valor*, *Estadísticas de Rate*, *Volumen & Conteo*) con badges de ventaja.
   - **Veredicto Sabermétrico Automático** y exportación directa de **Tarjeta Gráfica Matchup (PNG)** en alta resolución.
6. **Game Center & Win Expectancy en Vivo**:
   - Boxscores interactivos y curva de **Win Expectancy (WE)** jugada por jugada.
   - Matriz **RE24 Tango** y cálculo de **Leverage Index (LI)** para detectar jugadas clave de alto apalancamiento (*Clutch*).
7. **Spray Charts con Calibración BIS**:
   - Dispersión espacial de batazos sobre diamante interactivo en Plotly.
   - Filtros de calidad de contacto **BIS** (*Hard*, *Medium*, *Soft*).

---

## 📚 Fuentes de Datos & Metodología Sabermétrica (Créditos)

Esta plataforma se fundamenta en fuentes oficiales de datos y marcos de referencia sabermétricos de vanguardia:

* **[MLB Stats API](https://statsapi.mlb.com/):**
  - Fuente oficial de ingestión de play-by-play, boxscores, estadísticas tradicionales/avanzadas, rosters y coordenadas espaciales para LIDOM (`sportId=17`, `leagueId=131`).
  - Headshots oficiales de alta resolución vinculados al `person.id` de MLB.
* **[Tom Tango / The Book (RE24 & WPA)](http://www.tangotiger.net/):**
  - Matriz de Expectativa de Carreras de 24 estados (Base-Out Run Expectancy Matrix) y modelo estocástico de Probabilidad de Victoria (Win Expectancy & Win Probability Added).
* **[Baseball Info Solutions (BIS)](https://www.sportsinfosolutions.com/):**
  - Modelo determinístico de clasificación de dureza de contacto en batazos (*Hard*, *Medium*, *Soft*) calibrado por velocidad de salida y tipo de trayectoria.
* **[Liga de Béisbol Profesional de la República Dominicana (LIDOM)](https://lidom.com/):**
  - Calendarios, estructuras de postemporada (Serie Regular, Round Robin de 18 juegos, Serie Final) e identidades visuales de las 6 franquicias.

---

## 🛠️ Estructura del Proyecto

```
lidom-analytics/
├── .streamlit/
│   └── config.toml             # Tema Dark Navy (#070B19) y variables de interfaz
├── core/
│   ├── api_client.py           # Ingesta resiliente de MLB Stats API (sportId=17, leagueId=131)
│   ├── data_loader.py          # Agregador de datos con caché y pool de matchup
│   ├── wpa_engine.py           # Matriz RE24, cálculo de Win Expectancy y WPA por jugada
│   ├── elo_engine.py           # Algoritmo ELO y simulación Monte Carlo (5,000 runs)
│   ├── situational.py          # Splits situacionales (Clutch, RISP, Bases Llenas, Por Inning)
│   ├── bullpen.py              # Rendimiento de relevistas, corredores heredados (IR/IRS) y gmLI
│   ├── bis_hardness.py         # Modelo determinístico de dureza de contacto (Batted Ball)
│   ├── supabase_client.py      # Persistencia y queries a PostgreSQL Supabase
│   └── teams.py                # Metadatos, colores y logos oficiales de los 6 equipos
├── views/
│   ├── home.py                 # Standings con logos, ELO y simulación Monte Carlo
│   ├── team_hub.py             # Dashboard por franquicia con theming dinámico
│   ├── leaderboards.py         # Tabla de líderes de bateo y pitcheo
│   ├── versus.py               # Matchup 360 (Radar polar, H2H y descarga PNG)
│   ├── game_center.py          # Matchups H2H y curva de Win Expectancy
│   └── spray_charts.py         # Dispersión de batazos en diamante Plotly
├── utils/
│   └── styles.py               # Inyección CSS Glassmorphism y logos Base64
├── tests/
│   └── test_core.py            # Suite de pruebas unitarias (9 tests)
├── app.py                      # Punto de entrada principal en Streamlit
├── refresh_data.py             # Script CLI de ingesta y precarga de datos
└── requirements.txt            # Dependencias del proyecto
```

---

## 📦 Instalación y Ejecución

```bash
# 1. Clonar o navegar al directorio
cd lidom-analytics

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Ejecutar la aplicación en Streamlit
streamlit run app.py
```

### Ejecutar Pruebas Unitarias
```bash
python -m unittest tests/test_core.py
```

### Ingesta de Datos CLI
```bash
python refresh_data.py --season 2024
```

---

## 👤 Autor
**Jorge Leonardo Loreto**  
*AI Data Scientist & Baseball Sabermetrician*  
Santo Domingo, República Dominicana  
[🌐 Portafolio](https://jloreto9.github.io/jloreto9/) · [LinkedIn](https://www.linkedin.com/in/jorgeloreto/)
