-- ====================================================================
-- ESQUEMA DE BASE DE DATOS SUPABASE / POSTGRESQL - LIDOM 360 ANALYTICS
-- Disenado por Jorge Leonardo Loreto | AI Data Scientist & Sabermetrician
-- Cubre: Equipos, Jugadores, Calendario/Juegos, Boxscores, PBP y WPA
-- ====================================================================

-- 1. EXTENSIONES
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 2. TABLA DE EQUIPOS (FRANQUICIAS LIDOM)
CREATE TABLE IF NOT EXISTS lidom_teams (
    id INT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    short_name VARCHAR(50) NOT NULL,
    abbrev VARCHAR(10) NOT NULL UNIQUE,
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

-- 3. TABLA DE JUGADORES (ROSTER & BIOGRAFIA)
CREATE TABLE IF NOT EXISTS lidom_players (
    id INT PRIMARY KEY,
    full_name VARCHAR(150) NOT NULL,
    team_id INT REFERENCES lidom_teams(id) ON DELETE SET NULL,
    primary_position VARCHAR(10),
    jersey_number VARCHAR(10),
    bat_side VARCHAR(5),
    pitch_hand VARCHAR(5),
    birth_date DATE,
    birth_country VARCHAR(100),
    headshot_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 4. TABLA DE JUEGOS Y CALENDARIO
CREATE TABLE IF NOT EXISTS lidom_games (
    id INT PRIMARY KEY,
    season INT NOT NULL,
    game_date DATE NOT NULL,
    game_datetime TIMESTAMP WITH TIME ZONE,
    game_type VARCHAR(10) NOT NULL,
    status VARCHAR(50) NOT NULL,
    detailed_state VARCHAR(100),
    home_team_id INT REFERENCES lidom_teams(id) NOT NULL,
    away_team_id INT REFERENCES lidom_teams(id) NOT NULL,
    home_score INT DEFAULT 0,
    away_score INT DEFAULT 0,
    venue_name VARCHAR(150),
    is_extra BOOLEAN DEFAULT FALSE,
    total_innings INT DEFAULT 9,
    linescore JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 5. TABLA DE ESTADISTICAS DE BATEO (BOXSCORE INDIVIDUAL POR JUEGO)
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

-- 6. TABLA DE ESTADISTICAS DE PITCHEO (BOXSCORE INDIVIDUAL POR JUEGO)
CREATE TABLE IF NOT EXISTS lidom_pitching_stats (
    id BIGSERIAL PRIMARY KEY,
    game_id INT REFERENCES lidom_games(id) ON DELETE CASCADE NOT NULL,
    player_id INT REFERENCES lidom_players(id) NOT NULL,
    team_id INT REFERENCES lidom_teams(id) NOT NULL,
    season INT NOT NULL,
    role VARCHAR(10),
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
    half_inning VARCHAR(10) NOT NULL,
    outs INT NOT NULL,
    batter_id INT,
    batter_name VARCHAR(150),
    pitcher_id INT,
    pitcher_name VARCHAR(150),
    batting_team_id INT,
    fielding_team_id INT,
    event VARCHAR(100),
    event_type VARCHAR(100),
    description TEXT,
    score_home INT DEFAULT 0,
    score_away INT DEFAULT 0,
    base_state INT DEFAULT 0,
    we_before NUMERIC(6,4),
    we_after NUMERIC(6,4),
    wpa_batter NUMERIC(6,4),
    wpa_pitcher NUMERIC(6,4),
    leverage_index NUMERIC(5,2),
    hc_x NUMERIC(6,2),
    hc_y NUMERIC(6,2),
    distance NUMERIC(6,2),
    launch_speed NUMERIC(5,2),
    trajectory VARCHAR(50),
    hardness VARCHAR(20),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- ====================================================================
-- INDICES DE ALTO RENDIMIENTO
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
-- POBLAR INICIALMENTE LOS 6 EQUIPOS CANONICOS DE LIDOM
-- ====================================================================
INSERT INTO lidom_teams (id, name, short_name, abbrev, city, stadium, primary_color, secondary_color, accent_color, text_color, logo_url, founded, championships)
VALUES
    (672, 'Tigres del Licey', 'Licey', 'LIC', 'Santo Domingo', 'Estadio Quisqueya Juan Marichal', '#002D62', '#FFFFFF', '#0055B8', '#FFFFFF', 'https://midfield.mlbstatic.com/v1/team/672/spots/120', 1907, 24),
    (667, 'Aguilas Cibaenas', 'Aguilas', 'AGU', 'Santiago de los Caballeros', 'Estadio Cibao', '#FFCC00', '#111111', '#FFAA00', '#000000', 'https://midfield.mlbstatic.com/v1/team/667/spots/120', 1933, 22),
    (671, 'Leones del Escogido', 'Escogido', 'ESC', 'Santo Domingo', 'Estadio Quisqueya Juan Marichal', '#CC0000', '#FFFFFF', '#E60000', '#FFFFFF', 'https://midfield.mlbstatic.com/v1/team/671/spots/120', 1921, 16),
    (670, 'Gigantes del Cibao', 'Gigantes', 'GIG', 'San Francisco de Macoris', 'Estadio Julian Javier', '#5B1E31', '#D29B38', '#7E2A44', '#FFFFFF', 'https://midfield.mlbstatic.com/v1/team/670/spots/120', 1996, 2),
    (669, 'Estrellas Orientales', 'Estrellas', 'EST', 'San Pedro de Macoris', 'Estadio Tetelo Vargas', '#005A36', '#C49A45', '#007A48', '#FFFFFF', 'https://midfield.mlbstatic.com/v1/team/669/spots/120', 1910, 3),
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
-- POLITICAS DE SEGURIDAD (ROW LEVEL SECURITY - RLS)
-- Permite lectura publica a Streamlit y escritura para pipelines
-- ====================================================================
ALTER TABLE lidom_teams ENABLE ROW LEVEL SECURITY;
ALTER TABLE lidom_players ENABLE ROW LEVEL SECURITY;
ALTER TABLE lidom_games ENABLE ROW LEVEL SECURITY;
ALTER TABLE lidom_batting_stats ENABLE ROW LEVEL SECURITY;
ALTER TABLE lidom_pitching_stats ENABLE ROW LEVEL SECURITY;
ALTER TABLE lidom_plays ENABLE ROW LEVEL SECURITY;

-- 1. Politicas para lidom_teams
DROP POLICY IF EXISTS "Lectura publica lidom_teams" ON lidom_teams;
CREATE POLICY "Lectura publica lidom_teams" ON lidom_teams FOR SELECT USING (true);
DROP POLICY IF EXISTS "Escritura lidom_teams" ON lidom_teams;
CREATE POLICY "Escritura lidom_teams" ON lidom_teams FOR ALL USING (true) WITH CHECK (true);

-- 2. Politicas para lidom_players
DROP POLICY IF EXISTS "Lectura publica lidom_players" ON lidom_players;
CREATE POLICY "Lectura publica lidom_players" ON lidom_players FOR SELECT USING (true);
DROP POLICY IF EXISTS "Escritura lidom_players" ON lidom_players;
CREATE POLICY "Escritura lidom_players" ON lidom_players FOR ALL USING (true) WITH CHECK (true);

-- 3. Politicas para lidom_games
DROP POLICY IF EXISTS "Lectura publica lidom_games" ON lidom_games;
CREATE POLICY "Lectura publica lidom_games" ON lidom_games FOR SELECT USING (true);
DROP POLICY IF EXISTS "Escritura lidom_games" ON lidom_games;
CREATE POLICY "Escritura lidom_games" ON lidom_games FOR ALL USING (true) WITH CHECK (true);

-- 4. Politicas para lidom_batting_stats
DROP POLICY IF EXISTS "Lectura publica lidom_batting_stats" ON lidom_batting_stats;
CREATE POLICY "Lectura publica lidom_batting_stats" ON lidom_batting_stats FOR SELECT USING (true);
DROP POLICY IF EXISTS "Escritura lidom_batting_stats" ON lidom_batting_stats;
CREATE POLICY "Escritura lidom_batting_stats" ON lidom_batting_stats FOR ALL USING (true) WITH CHECK (true);

-- 5. Politicas para lidom_pitching_stats
DROP POLICY IF EXISTS "Lectura publica lidom_pitching_stats" ON lidom_pitching_stats;
CREATE POLICY "Lectura publica lidom_pitching_stats" ON lidom_pitching_stats FOR SELECT USING (true);
DROP POLICY IF EXISTS "Escritura lidom_pitching_stats" ON lidom_pitching_stats;
CREATE POLICY "Escritura lidom_pitching_stats" ON lidom_pitching_stats FOR ALL USING (true) WITH CHECK (true);

-- 6. Politicas para lidom_plays
DROP POLICY IF EXISTS "Lectura publica lidom_plays" ON lidom_plays;
CREATE POLICY "Lectura publica lidom_plays" ON lidom_plays FOR SELECT USING (true);
DROP POLICY IF EXISTS "Escritura lidom_plays" ON lidom_plays;
CREATE POLICY "Escritura lidom_plays" ON lidom_plays FOR ALL USING (true) WITH CHECK (true);
