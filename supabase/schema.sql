-- ====================================================================
-- ESQUEMA DE BASE DE DATOS SUPABASE / POSTGRESQL — LIDOM 360 ANALYTICS
-- Diseñado por Jorge Leonardo Loreto | AI Data Scientist & Sabermetrician
-- Cubre: Equipos, Jugadores, Calendario/Juegos, Boxscores, PBP y WPA
-- ====================================================================

-- 1. EXTENSIONES
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 2. TABLA DE EQUIPOS (FRANQUICIAS LIDOM)
CREATE TABLE IF NOT EXISTS lidom_teams (
    id INT PRIMARY KEY,                       -- ID oficial MLB (672: LIC, 667: AGU, 671: ESC, etc.)
    name VARCHAR(100) NOT NULL,              -- Nombre completo (Tigres del Licey)
    short_name VARCHAR(50) NOT NULL,         -- Nombre corto (Licey)
    abbrev VARCHAR(10) NOT NULL UNIQUE,      -- Abreviatura canónica (LIC, AGU, ESC, GIG, EST, TOR)
    city VARCHAR(100),
    stadium VARCHAR(150),
    primary_color VARCHAR(10) NOT NULL,
    secondary_color VARCHAR(10),
    accent_color VARCHAR(10),
    text_color VARCHAR(10),
    logo_url TEXT,
    founded INT,
    championships INT DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 3. TABLA DE JUGADORES (ROSTER & BIOGRAFÍA)
CREATE TABLE IF NOT EXISTS lidom_players (
    id INT PRIMARY KEY,                       -- ID oficial MLB / Chadwick (personId)
    full_name VARCHAR(150) NOT NULL,
    team_id INT REFERENCES lidom_teams(id) ON DELETE SET NULL,
    primary_position VARCHAR(10),            -- C, 1B, 2B, 3B, SS, LF, CF, RF, DH, SP, RP, CL
    jersey_number VARCHAR(10),
    bat_side VARCHAR(5),                     -- R, L, S
    pitch_hand VARCHAR(5),                   -- R, L
    birth_date DATE,
    birth_country VARCHAR(100),
    headshot_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 4. TABLA DE JUEGOS Y CALENDARIO
CREATE TABLE IF NOT EXISTS lidom_games (
    id INT PRIMARY KEY,                       -- game_pk oficial MLB Stats API
    season INT NOT NULL,                     -- Año inicial de temporada (2023, 2024, 2025)
    game_date DATE NOT NULL,
    game_datetime TIMESTAMP WITH TIME ZONE,
    game_type VARCHAR(10) NOT NULL,          -- R (Regular), W/L (Round Robin), F (Final)
    status VARCHAR(50) NOT NULL,             -- Final, In Progress, Scheduled, Postponed
    detailed_state VARCHAR(100),
    home_team_id INT REFERENCES lidom_teams(id) NOT NULL,
    away_team_id INT REFERENCES lidom_teams(id) NOT NULL,
    home_score INT DEFAULT 0,
    away_score INT DEFAULT 0,
    venue_name VARCHAR(150),
    is_extra BOOLEAN DEFAULT FALSE,
    total_innings INT DEFAULT 9,
    linescore JSONB,                         -- Desglose carrera por inning, hits, errores
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 5. TABLA DE ESTADÍSTICAS DE BATEO (BOXSCORE INDIVIDUAL POR JUEGO)
CREATE TABLE IF NOT EXISTS lidom_batting_stats (
    id BIGSERIAL PRIMARY KEY,
    game_id INT REFERENCES lidom_games(id) ON DELETE CASCADE NOT NULL,
    player_id INT REFERENCES lidom_players(id) NOT NULL,
    team_id INT REFERENCES lidom_teams(id) NOT NULL,
    season INT NOT NULL,
    batting_order INT,
    position VARCHAR(10),
    ab INT DEFAULT 0,
    r INT DEFAULT 0,
    h INT DEFAULT 0,
    doubles INT DEFAULT 0,
    triples INT DEFAULT 0,
    hr INT DEFAULT 0,
    rbi INT DEFAULT 0,
    bb INT DEFAULT 0,
    so INT DEFAULT 0,
    sb INT DEFAULT 0,
    cs INT DEFAULT 0,
    hbp INT DEFAULT 0,
    sf INT DEFAULT 0,
    sh INT DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    CONSTRAINT unique_game_batter UNIQUE (game_id, player_id)
);

-- 6. TABLA DE ESTADÍSTICAS DE PITCHEO (BOXSCORE INDIVIDUAL POR JUEGO)
CREATE TABLE IF NOT EXISTS lidom_pitching_stats (
    id BIGSERIAL PRIMARY KEY,
    game_id INT REFERENCES lidom_games(id) ON DELETE CASCADE NOT NULL,
    player_id INT REFERENCES lidom_players(id) NOT NULL,
    team_id INT REFERENCES lidom_teams(id) NOT NULL,
    season INT NOT NULL,
    role VARCHAR(10),                         -- SP, RP, CL
    is_starter BOOLEAN DEFAULT FALSE,
    ip_decimal NUMERIC(5,2) DEFAULT 0.0,
    h INT DEFAULT 0,
    r INT DEFAULT 0,
    er INT DEFAULT 0,
    bb INT DEFAULT 0,
    so INT DEFAULT 0,
    hr INT DEFAULT 0,
    hbp INT DEFAULT 0,
    wp INT DEFAULT 0,
    bk INT DEFAULT 0,
    w INT DEFAULT 0,
    l INT DEFAULT 0,
    sv INT DEFAULT 0,
    hold INT DEFAULT 0,
    blown_save INT DEFAULT 0,
    pitches_thrown INT DEFAULT 0,
    strikes INT DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    CONSTRAINT unique_game_pitcher UNIQUE (game_id, player_id)
);

-- 7. TABLA DE JUGADAS PLAY-BY-PLAY, SPRAY CHARTS Y WPA
CREATE TABLE IF NOT EXISTS lidom_plays (
    id BIGSERIAL PRIMARY KEY,
    game_id INT REFERENCES lidom_games(id) ON DELETE CASCADE NOT NULL,
    play_id VARCHAR(50),
    season INT NOT NULL,
    inning INT NOT NULL,
    half_inning VARCHAR(10) NOT NULL,        -- top, bottom
    outs INT NOT NULL,                       -- Outs antes del evento (0, 1, 2)
    batter_id INT REFERENCES lidom_players(id),
    batter_name VARCHAR(150),
    pitcher_id INT REFERENCES lidom_players(id),
    pitcher_name VARCHAR(150),
    batting_team_id INT REFERENCES lidom_teams(id),
    fielding_team_id INT REFERENCES lidom_teams(id),
    event VARCHAR(100),                      -- Single, Home Run, Strikeout, Walk, etc.
    event_type VARCHAR(100),
    description TEXT,
    score_home INT DEFAULT 0,
    score_away INT DEFAULT 0,
    base_state INT DEFAULT 0,                -- 0 (vacías) a 7 (llenas)
    we_before NUMERIC(6,4),                  -- Probabilidad de victoria local previa
    we_after NUMERIC(6,4),                   -- Probabilidad de victoria local posterior
    wpa_batter NUMERIC(6,4),                 -- WPA asignado al bateador
    wpa_pitcher NUMERIC(6,4),                -- WPA asignado al lanzador (-wpa_batter)
    leverage_index NUMERIC(5,2),             -- Apalancamiento situacional (LI)
    hc_x NUMERIC(6,2),                       -- Coordenada X del bateo (0-250)
    hc_y NUMERIC(6,2),                       -- Coordenada Y del bateo (0-250)
    distance NUMERIC(6,2),                   -- Distancia estimada en pies
    launch_speed NUMERIC(5,2),               -- Velocidad de salida (mph)
    trajectory VARCHAR(50),                  -- fly_ball, line_drive, ground_ball, popup
    hardness VARCHAR(20),                    -- Hard, Medium, Soft (Modelo BIS)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- ====================================================================
-- ÍNDICES DE ALTO RENDIMIENTO PARA CONSULTAS ANALÍTICAS
-- ====================================================================
CREATE INDEX IF NOT EXISTS idx_lidom_games_season_date ON lidom_games(season, game_date);
CREATE INDEX IF NOT EXISTS idx_lidom_games_type ON lidom_games(game_type);
CREATE INDEX IF NOT EXISTS idx_lidom_games_teams ON lidom_games(home_team_id, away_team_id);

CREATE INDEX IF NOT EXISTS idx_lidom_batting_season_team ON lidom_batting_stats(season, team_id);
CREATE INDEX IF NOT EXISTS idx_lidom_batting_player ON lidom_batting_stats(player_id);

CREATE INDEX IF NOT EXISTS idx_lidom_pitching_season_team ON lidom_pitching_stats(season, team_id);
CREATE INDEX IF NOT EXISTS idx_lidom_pitching_player ON lidom_pitching_stats(player_id);

CREATE INDEX IF NOT EXISTS idx_lidom_plays_game ON lidom_plays(game_id);
CREATE INDEX IF NOT EXISTS idx_lidom_plays_batter ON lidom_plays(batter_id, season);
CREATE INDEX IF NOT EXISTS idx_lidom_plays_pitcher ON lidom_plays(pitcher_id, season);
CREATE INDEX IF NOT EXISTS idx_lidom_plays_hardness ON lidom_plays(hardness);

-- ====================================================================
-- POBLAR INICIALMENTE LOS 6 EQUIPOS CANÓNICOS DE LIDOM
-- ====================================================================
INSERT INTO lidom_teams (id, name, short_name, abbrev, city, stadium, primary_color, secondary_color, accent_color, text_color, logo_url, founded, championships)
VALUES
    (672, 'Tigres del Licey', 'Licey', 'LIC', 'Santo Domingo', 'Estadio Quisqueya Juan Marichal', '#002D62', '#FFFFFF', '#0055B8', '#FFFFFF', 'https://midfield.mlbstatic.com/v1/team/672/spots/120', 1907, 24),
    (667, 'Águilas Cibaeñas', 'Águilas', 'AGU', 'Santiago de los Caballeros', 'Estadio Cibao', '#FFCC00', '#111111', '#FFAA00', '#000000', 'https://midfield.mlbstatic.com/v1/team/667/spots/120', 1933, 22),
    (671, 'Leones del Escogido', 'Escogido', 'ESC', 'Santo Domingo', 'Estadio Quisqueya Juan Marichal', '#CC0000', '#FFFFFF', '#E60000', '#FFFFFF', 'https://midfield.mlbstatic.com/v1/team/671/spots/120', 1921, 16),
    (670, 'Gigantes del Cibao', 'Gigantes', 'GIG', 'San Francisco de Macorís', 'Estadio Julián Javier', '#5B1E31', '#D29B38', '#7E2A44', '#FFFFFF', 'https://midfield.mlbstatic.com/v1/team/670/spots/120', 1996, 2),
    (669, 'Estrellas Orientales', 'Estrellas', 'EST', 'San Pedro de Macorís', 'Estadio Tetelo Vargas', '#005A36', '#C49A45', '#007A48', '#FFFFFF', 'https://midfield.mlbstatic.com/v1/team/669/spots/120', 1910, 3),
    (668, 'Toros del Este', 'Toros', 'TOR', 'La Romana', 'Estadio Francisco Micheli', '#EA5B0C', '#111111', '#FF6F1C', '#FFFFFF', 'https://midfield.mlbstatic.com/v1/team/668/spots/120', 1983, 3)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    short_name = EXCLUDED.short_name,
    abbrev = EXCLUDED.abbrev,
    city = EXCLUDED.city,
    stadium = EXCLUDED.stadium,
    primary_color = EXCLUDED.primary_color,
    secondary_color = EXCLUDED.secondary_color,
    accent_color = EXCLUDED.accent_color,
    text_color = EXCLUDED.text_color,
    logo_url = EXCLUDED.logo_url,
    founded = EXCLUDED.founded,
    championships = EXCLUDED.championships;

-- ====================================================================
-- POLÍTICAS DE ACCESO (ROW LEVEL SECURITY - RLS)
-- Permite lectura pública a usuarios anónimos (Streamlit App)
-- ====================================================================
ALTER TABLE lidom_teams ENABLE ROW LEVEL SECURITY;
ALTER TABLE lidom_players ENABLE ROW LEVEL SECURITY;
ALTER TABLE lidom_games ENABLE ROW LEVEL SECURITY;
ALTER TABLE lidom_batting_stats ENABLE ROW LEVEL SECURITY;
ALTER TABLE lidom_pitching_stats ENABLE ROW LEVEL SECURITY;
ALTER TABLE lidom_plays ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Lectura publica lidom_teams" ON lidom_teams FOR SELECT USING (true);
CREATE POLICY "Lectura publica lidom_players" ON lidom_players FOR SELECT USING (true);
CREATE POLICY "Lectura publica lidom_games" ON lidom_games FOR SELECT USING (true);
CREATE POLICY "Lectura publica lidom_batting_stats" ON lidom_batting_stats FOR SELECT USING (true);
CREATE POLICY "Lectura publica lidom_pitching_stats" ON lidom_pitching_stats FOR SELECT USING (true);
CREATE POLICY "Lectura publica lidom_plays" ON lidom_plays FOR SELECT USING (true);
