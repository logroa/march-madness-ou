CREATE TABLE IF NOT EXISTS teams (
    id SERIAL PRIMARY KEY,
    team_name VARCHAR(100),
    seed INTEGER,
    team_pic VARCHAR(200)
);

CREATE TABLE IF NOT EXISTS games (
    id INTEGER PRIMARY KEY,
    round VARCHAR(20),
    date_played VARCHAR(20),
    team1 INTEGER REFERENCES teams (id),
    team1score INTEGER,
    team2 INTEGER REFERENCES teams (id),
    team2score INTEGER,
    overunder FLOAT,
    started BOOLEAN,
    finished BOOLEAN
);

CREATE TABLE IF NOT EXISTS players (
    id SERIAL PRIMARY KEY,
    handle VARCHAR(100) NOT NULL,
    pw VARCHAR(200) NOT NULL,
    phone_number VARCHAR(20),
    confirmed BOOLEAN,
    paid BOOLEAN
);

CREATE TABLE IF NOT EXISTS picks (
    game_id INTEGER REFERENCES games (id),
    player_id INTEGER REFERENCES players (id),
    over_picked BOOLEAN,
    correct BOOLEAN
);

CREATE TABLE IF NOT EXISTS comments (
    game_id INTEGER REFERENCES games (id),
    player_id INTEGER REFERENCES players (id),
    comment_text VARCHAR (200),
    posted_at TIMESTAMP
);