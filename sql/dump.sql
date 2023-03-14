CREATE TABLE IF NOT EXISTS games (
    id SERIAL PRIMARY KEY,
    round VARCHAR(20),
    team1 VARCHAR(50),
    team1score INTEGER,
    team2 VARCHAR(50),
    team2score INTEGER,
    overunder FLOAT,
    starttime TIMESTAMP,
    started BOOLEAN,
    half VARCHAR(10),
    time_remaining VARCHAR(20),
    finished BOOLEAN
);

CREATE TABLE IF NOT EXISTS players (
    id SERIAL PRIMARY KEY,
    handle VARCHAR(100) NOT NULL,
    pw VARCHAR(200) NOT NULL,
    phone_number VARCHAR(20),
    confirmed BOOLEAN
);

CREATE TABLE IF NOT EXISTS picks (
    game_id INTEGER REFERENCES games (id),
    player_id INTEGER REFERENCES players (id),
    over_picked BOOLEAN,
    correct BOOLEAN
);