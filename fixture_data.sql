-- =============================================
-- FIXTURE MUNDIAL 2026 - 48 equipos, 12 grupos
-- =============================================

-- EQUIPOS (confirmados o probables al 2026)
INSERT INTO teams (name, code, group_name) VALUES
-- Grupo A
('Estados Unidos', 'USA', 'A'),
('México', 'MEX', 'A'),
('Panamá', 'PAN', 'A'),
('Honduras', 'HON', 'A'),
-- Grupo B
('Argentina', 'ARG', 'B'),
('Ecuador', 'ECU', 'B'),
('Venezuela', 'VEN', 'B'),
('Jamaica', 'JAM', 'B'),
-- Grupo C
('Francia', 'FRA', 'C'),
('Alemania', 'GER', 'C'),
('Portugal', 'POR', 'C'),
('Georgia', 'GEO', 'C'),
-- Grupo D
('España', 'ESP', 'D'),
('Croacia', 'CRO', 'D'),
('Serbia', 'SRB', 'D'),
('Eslovaquia', 'SVK', 'D'),
-- Grupo E
('Brasil', 'BRA', 'E'),
('Uruguay', 'URU', 'E'),
('Colombia', 'COL', 'E'),
('Bolivia', 'BOL', 'E'),
-- Grupo F
('Inglaterra', 'ENG', 'F'),
('Países Bajos', 'NED', 'F'),
('Bélgica', 'BEL', 'F'),
('Escocia', 'SCO', 'F'),
-- Grupo G
('Marruecos', 'MAR', 'G'),
('Senegal', 'SEN', 'G'),
('Mali', 'MLI', 'G'),
('Sudáfrica', 'RSA', 'G'),
-- Grupo H
('Japón', 'JPN', 'H'),
('Australia', 'AUS', 'H'),
('Arabia Saudita', 'KSA', 'H'),
('Uzbekistán', 'UZB', 'H'),
-- Grupo I
('Portugal', 'POR', 'I'),
-- NOTE: This fixture is approximate. Official draw TBD.
-- These will be updated when the official draw is released.
('Turquía', 'TUR', 'I'),
('República Checa', 'CZE', 'I'),
('Albania', 'ALB', 'I'),
-- Grupo J
('Polonia', 'POL', 'J'),
('Rumania', 'ROU', 'J'),
('Austria', 'AUT', 'J'),
('Hungría', 'HUN', 'J'),
-- Grupo K
('Corea del Sur', 'KOR', 'K'),
('Irán', 'IRN', 'K'),
('Irak', 'IRQ', 'K'),
('Omán', 'OMA', 'K'),
-- Grupo L
('Canadá', 'CAN', 'L'),
('Costa Rica', 'CRC', 'L'),
('El Salvador', 'SLV', 'L'),
('Trinidad y Tobago', 'TRI', 'L')
ON CONFLICT DO NOTHING;

-- NOTA: El fixture completo de fechas y horarios se cargará
-- cuando FIFA publique el calendario oficial.
-- Los partidos de grupos se cargarán via panel admin.

-- Partidos de ejemplo (Grupo E - con Uruguay para el mercado UY)
-- INSERT INTO matches (match_number, phase, group_name, home_team_id, away_team_id, match_date, venue)
-- VALUES (1, 'group', 'E', ..., ..., '2026-06-12 18:00:00-05', 'MetLife Stadium');
