CREATE TABLE source_assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_key TEXT NOT NULL UNIQUE,
    source_id INTEGER NOT NULL,
    competition_id INTEGER NOT NULL,
    season_id INTEGER NOT NULL,
    role TEXT NOT NULL
        CHECK (role IN ('authoritative', 'bootstrap', 'verification', 'disabled')),
    interval_seconds INTEGER NOT NULL
        CHECK (interval_seconds > 0),
    is_enabled INTEGER NOT NULL DEFAULT 1
        CHECK (is_enabled IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    CONSTRAINT fk_source_assignments_source
        FOREIGN KEY (source_id)
        REFERENCES data_sources (id)
        ON DELETE RESTRICT,

    CONSTRAINT fk_source_assignments_competition
        FOREIGN KEY (competition_id)
        REFERENCES competitions (id)
        ON DELETE RESTRICT,

    CONSTRAINT fk_source_assignments_season
        FOREIGN KEY (season_id)
        REFERENCES seasons (id)
        ON DELETE RESTRICT,

    CONSTRAINT uq_source_assignments_source_scope
        UNIQUE (source_id, competition_id, season_id)
);

CREATE UNIQUE INDEX uq_source_assignments_authority
    ON source_assignments (competition_id, season_id)
    WHERE role = 'authoritative' AND is_enabled = 1;

CREATE INDEX idx_source_assignments_scope
    ON source_assignments (competition_id, season_id, is_enabled);
