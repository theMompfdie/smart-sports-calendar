CREATE TABLE fixture_reconciliation_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL,
    event_id INTEGER NOT NULL,
    external_id TEXT NOT NULL,
    missing_observation_count INTEGER NOT NULL DEFAULT 0
        CHECK (missing_observation_count >= 0),
    first_missing_at TEXT,
    last_missing_at TEXT,
    last_observation_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    CONSTRAINT fk_fixture_reconciliation_source
        FOREIGN KEY (source_id)
        REFERENCES data_sources (id)
        ON DELETE CASCADE,

    CONSTRAINT fk_fixture_reconciliation_event
        FOREIGN KEY (event_id)
        REFERENCES sports_events (id)
        ON DELETE CASCADE,

    CONSTRAINT uq_fixture_reconciliation_event
        UNIQUE (source_id, event_id),

    CONSTRAINT uq_fixture_reconciliation_external
        UNIQUE (source_id, external_id)
);

CREATE INDEX idx_fixture_reconciliation_missing
    ON fixture_reconciliation_state (
        source_id,
        missing_observation_count,
        last_missing_at
    );
