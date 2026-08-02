CREATE TABLE season_participants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    season_id INTEGER NOT NULL,
    participant_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    CONSTRAINT fk_season_participants_season
        FOREIGN KEY (season_id)
        REFERENCES seasons (id)
        ON DELETE CASCADE,

    CONSTRAINT fk_season_participants_participant
        FOREIGN KEY (participant_id)
        REFERENCES participants (id)
        ON DELETE RESTRICT,

    CONSTRAINT uq_season_participants_membership
        UNIQUE (season_id, participant_id)
);

CREATE INDEX idx_season_participants_season
    ON season_participants (season_id);

CREATE INDEX idx_season_participants_participant
    ON season_participants (participant_id);
