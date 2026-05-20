-- =============================================
-- PENCA TUYA MUNDIAL 2026 - Schema Supabase
-- =============================================

-- Tabla de usuarios de la penca
CREATE TABLE IF NOT EXISTS penca_users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE NOT NULL,
  username TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  full_name TEXT,
  total_points INTEGER DEFAULT 0,
  purchase_points INTEGER DEFAULT 0,
  prediction_points INTEGER DEFAULT 0,
  subscribed_newsletter BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Tabla de equipos
CREATE TABLE IF NOT EXISTS teams (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  code TEXT NOT NULL, -- 3-letter code e.g. URU, ARG, BRA
  group_name TEXT, -- A, B, C, D, E, F, G, H, I, J, K, L (12 groups for 2026)
  flag_url TEXT,
  eliminated BOOLEAN DEFAULT FALSE
);

-- Tabla de partidos
CREATE TABLE IF NOT EXISTS matches (
  id SERIAL PRIMARY KEY,
  match_number INTEGER,
  phase TEXT NOT NULL, -- 'group', 'r16', 'qf', 'sf', 'third', 'final'
  group_name TEXT, -- only for group phase
  home_team_id INTEGER REFERENCES teams(id),
  away_team_id INTEGER REFERENCES teams(id),
  home_team_placeholder TEXT, -- for knockouts before teams are known (e.g. "Ganador Grupo A")
  away_team_placeholder TEXT,
  match_date TIMESTAMPTZ,
  venue TEXT,
  -- Resultado final
  home_score INTEGER,
  away_score INTEGER,
  -- Para eliminatorias: si hay empate, cómo se resolvió
  extra_time BOOLEAN DEFAULT FALSE,
  penalties BOOLEAN DEFAULT FALSE,
  penalty_winner_id INTEGER REFERENCES teams(id), -- who won on penalties/ET
  -- Estado
  status TEXT DEFAULT 'scheduled', -- 'scheduled', 'live', 'finished', 'cancelled'
  predictions_locked BOOLEAN DEFAULT FALSE, -- true when match starts
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Tabla de predicciones
CREATE TABLE IF NOT EXISTS predictions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES penca_users(id) ON DELETE CASCADE,
  match_id INTEGER REFERENCES matches(id) ON DELETE CASCADE,
  -- Predicción del usuario
  predicted_home_score INTEGER NOT NULL,
  predicted_away_score INTEGER NOT NULL,
  -- Para eliminatorias: predicción de resolución si hay empate
  predicted_extra_time BOOLEAN DEFAULT FALSE,
  predicted_penalties BOOLEAN DEFAULT FALSE,
  predicted_penalty_winner_id INTEGER REFERENCES teams(id),
  -- Puntos obtenidos (calculados al cargar resultado)
  points_earned INTEGER,
  points_calculated BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(user_id, match_id)
);

-- Tabla de puntos por compras
CREATE TABLE IF NOT EXISTS purchase_points (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES penca_users(id) ON DELETE CASCADE,
  email TEXT NOT NULL, -- email used in purchase (must match penca email)
  order_id TEXT, -- ID del pedido en Luna Growth / tuyauy.com
  order_amount NUMERIC,
  points_granted INTEGER DEFAULT 10, -- equivalent to un partido embocado exacto
  description TEXT DEFAULT 'Compra en TUYA',
  granted_by TEXT DEFAULT 'admin', -- admin or webhook
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Vista del ranking
CREATE OR REPLACE VIEW ranking AS
SELECT
  u.id,
  u.username,
  u.full_name,
  u.email,
  u.prediction_points,
  u.purchase_points,
  u.total_points,
  COUNT(p.id) FILTER (WHERE p.points_calculated = TRUE) AS predictions_made,
  COUNT(p.id) FILTER (WHERE p.points_earned = 10) AS exact_results,
  COUNT(p.id) FILTER (WHERE p.points_earned = 7) AS exact_draws,
  COUNT(p.id) FILTER (WHERE p.points_earned = 5) AS exact_differences,
  COUNT(p.id) FILTER (WHERE p.points_earned = 3) AS correct_winners,
  RANK() OVER (ORDER BY u.total_points DESC, u.prediction_points DESC) AS position
FROM penca_users u
LEFT JOIN predictions p ON p.user_id = u.id
GROUP BY u.id, u.username, u.full_name, u.email, u.prediction_points, u.purchase_points, u.total_points
ORDER BY u.total_points DESC, u.prediction_points DESC;

-- Función para recalcular puntos de un partido
CREATE OR REPLACE FUNCTION calculate_match_points(match_id_param INTEGER)
RETURNS void AS $$
DECLARE
  m matches%ROWTYPE;
  p predictions%ROWTYPE;
  pts INTEGER;
  is_knockout BOOLEAN;
BEGIN
  -- Obtener el partido
  SELECT * INTO m FROM matches WHERE id = match_id_param;
  
  IF m.status != 'finished' THEN
    RETURN;
  END IF;
  
  is_knockout := m.phase IN ('r16', 'qf', 'sf', 'third', 'final');
  
  -- Recorrer todas las predicciones para este partido
  FOR p IN SELECT * FROM predictions WHERE match_id = match_id_param LOOP
    pts := 0;
    
    -- Resultado exacto (10 pts)
    IF p.predicted_home_score = m.home_score AND p.predicted_away_score = m.away_score THEN
      -- Para eliminatorias, también checar resolución si hubo ET/penales
      IF is_knockout AND m.extra_time THEN
        IF p.predicted_extra_time = TRUE AND p.predicted_penalties = m.penalties THEN
          IF NOT m.penalties OR p.predicted_penalty_winner_id = m.penalty_winner_id THEN
            pts := 10;
          ELSE
            pts := 7; -- marcador exacto pero no acertó penales
          END IF;
        ELSE
          pts := 7; -- marcador exacto pero no acertó ET/penales
        END IF;
      ELSE
        pts := 10;
      END IF;
    
    -- Empate correcto pero marcador diferente (7 pts) - solo grupos
    ELSIF NOT is_knockout 
      AND p.predicted_home_score = p.predicted_away_score 
      AND m.home_score = m.away_score 
      AND (p.predicted_home_score != m.home_score OR p.predicted_away_score != m.away_score) THEN
      pts := 7;
    
    -- Diferencia de goles exacta (5 pts)
    ELSIF (p.predicted_home_score - p.predicted_away_score) = (m.home_score - m.away_score) 
      AND (p.predicted_home_score != m.home_score OR p.predicted_away_score != m.away_score) THEN
      pts := 5;
    
    -- Ganador correcto pero diferencia equivocada (3 pts)
    ELSIF (
      (p.predicted_home_score > p.predicted_away_score AND m.home_score > m.away_score) OR
      (p.predicted_home_score < p.predicted_away_score AND m.home_score < m.away_score)
    ) THEN
      pts := 3;
    
    ELSE
      pts := 0;
    END IF;
    
    -- Actualizar predicción
    UPDATE predictions 
    SET points_earned = pts, points_calculated = TRUE, updated_at = NOW()
    WHERE id = p.id;
    
    -- Actualizar puntos del usuario
    UPDATE penca_users
    SET 
      prediction_points = (
        SELECT COALESCE(SUM(points_earned), 0) 
        FROM predictions 
        WHERE user_id = p.user_id AND points_calculated = TRUE
      ),
      total_points = (
        SELECT COALESCE(SUM(points_earned), 0) 
        FROM predictions 
        WHERE user_id = p.user_id AND points_calculated = TRUE
      ) + (
        SELECT COALESCE(SUM(points_granted), 0) 
        FROM purchase_points 
        WHERE user_id = p.user_id
      ),
      updated_at = NOW()
    WHERE id = p.user_id;
    
  END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Función para actualizar purchase_points totales del usuario
CREATE OR REPLACE FUNCTION update_user_purchase_points(user_id_param UUID)
RETURNS void AS $$
BEGIN
  UPDATE penca_users
  SET 
    purchase_points = (
      SELECT COALESCE(SUM(points_granted), 0) 
      FROM purchase_points 
      WHERE user_id = user_id_param
    ),
    total_points = (
      SELECT COALESCE(SUM(points_earned), 0) 
      FROM predictions 
      WHERE user_id = user_id_param AND points_calculated = TRUE
    ) + (
      SELECT COALESCE(SUM(points_granted), 0) 
      FROM purchase_points 
      WHERE user_id = user_id_param
    ),
    updated_at = NOW()
  WHERE id = user_id_param;
END;
$$ LANGUAGE plpgsql;

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_predictions_user_id ON predictions(user_id);
CREATE INDEX IF NOT EXISTS idx_predictions_match_id ON predictions(match_id);
CREATE INDEX IF NOT EXISTS idx_matches_phase ON matches(phase);
CREATE INDEX IF NOT EXISTS idx_matches_status ON matches(status);
CREATE INDEX IF NOT EXISTS idx_purchase_points_user_id ON purchase_points(user_id);
CREATE INDEX IF NOT EXISTS idx_purchase_points_email ON purchase_points(email);

-- Row Level Security (básico)
ALTER TABLE penca_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE predictions ENABLE ROW LEVEL SECURITY;
ALTER TABLE purchase_points ENABLE ROW LEVEL SECURITY;
