CREATE TABLE system_status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    status TEXT NOT NULL
);

CREATE TABLE data_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_key TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    base_url TEXT,
    is_active INTEGER NOT NULL DEFAULT 1
        CHECK (is_active IN (0, 1)),
    metadata_json TEXT
        CHECK (metadata_json IS NULL OR json_valid(metadata_json)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE sports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sport_key TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    icon TEXT,
    metadata_json TEXT
        CHECK (metadata_json IS NULL OR json_valid(metadata_json)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE competitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sport_id INTEGER NOT NULL,
    competition_key TEXT NOT NULL,
    name TEXT NOT NULL,
    short_name TEXT,
    country_code TEXT,
    competition_type TEXT,
    metadata_json TEXT
        CHECK (metadata_json IS NULL OR json_valid(metadata_json)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    CONSTRAINT fk_competitions_sport
        FOREIGN KEY (sport_id)
        REFERENCES sports (id)
        ON DELETE RESTRICT,

    CONSTRAINT uq_competitions_sport_key
        UNIQUE (sport_id, competition_key)
);

CREATE TABLE seasons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    competition_id INTEGER NOT NULL,
    season_key TEXT NOT NULL,
    name TEXT NOT NULL,
    start_date TEXT,
    end_date TEXT,
    is_current INTEGER NOT NULL DEFAULT 0
        CHECK (is_current IN (0, 1)),
    metadata_json TEXT
        CHECK (metadata_json IS NULL OR json_valid(metadata_json)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    CONSTRAINT fk_seasons_competition
        FOREIGN KEY (competition_id)
        REFERENCES competitions (id)
        ON DELETE CASCADE,

    CONSTRAINT uq_seasons_competition_key
        UNIQUE (competition_id, season_key)
);

CREATE TABLE participants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sport_id INTEGER NOT NULL,
    participant_key TEXT NOT NULL,
    participant_type TEXT NOT NULL,
    name TEXT NOT NULL,
    short_name TEXT,
    country_code TEXT,
    metadata_json TEXT
        CHECK (metadata_json IS NULL OR json_valid(metadata_json)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    CONSTRAINT fk_participants_sport
        FOREIGN KEY (sport_id)
        REFERENCES sports (id)
        ON DELETE RESTRICT,

    CONSTRAINT uq_participants_sport_key
        UNIQUE (sport_id, participant_key)
);

CREATE TABLE sports_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sport_id INTEGER NOT NULL,
    competition_id INTEGER,
    season_id INTEGER,
    parent_event_id INTEGER,
    event_key TEXT NOT NULL UNIQUE,
    event_type TEXT NOT NULL,
    title TEXT NOT NULL,
    stage TEXT,
    round_name TEXT,
    sequence_number INTEGER,
    start_time TEXT NOT NULL,
    end_time TEXT,
    timezone TEXT NOT NULL DEFAULT 'UTC',
    venue_name TEXT,
    city TEXT,
    country_code TEXT,
    status TEXT NOT NULL DEFAULT 'scheduled'
        CHECK (
            status IN (
                'scheduled',
                'confirmed',
                'live',
                'finished',
                'postponed',
                'cancelled',
                'suspended',
                'abandoned'
            )
        ),
    source_updated_at TEXT,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    cancelled_at TEXT,
    deleted_at TEXT,
    metadata_json TEXT
        CHECK (metadata_json IS NULL OR json_valid(metadata_json)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    CONSTRAINT fk_sports_events_sport
        FOREIGN KEY (sport_id)
        REFERENCES sports (id)
        ON DELETE RESTRICT,

    CONSTRAINT fk_sports_events_competition
        FOREIGN KEY (competition_id)
        REFERENCES competitions (id)
        ON DELETE SET NULL,

    CONSTRAINT fk_sports_events_season
        FOREIGN KEY (season_id)
        REFERENCES seasons (id)
        ON DELETE SET NULL,

    CONSTRAINT fk_sports_events_parent
        FOREIGN KEY (parent_event_id)
        REFERENCES sports_events (id)
        ON DELETE SET NULL,

    CONSTRAINT ck_sports_events_time_range
        CHECK (end_time IS NULL OR end_time >= start_time)
);

CREATE TABLE event_participants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL,
    participant_id INTEGER NOT NULL,
    role TEXT NOT NULL,
    position_number INTEGER,
    is_primary INTEGER NOT NULL DEFAULT 1
        CHECK (is_primary IN (0, 1)),
    metadata_json TEXT
        CHECK (metadata_json IS NULL OR json_valid(metadata_json)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    CONSTRAINT fk_event_participants_event
        FOREIGN KEY (event_id)
        REFERENCES sports_events (id)
        ON DELETE CASCADE,

    CONSTRAINT fk_event_participants_participant
        FOREIGN KEY (participant_id)
        REFERENCES participants (id)
        ON DELETE RESTRICT,

    CONSTRAINT uq_event_participants_role
        UNIQUE (event_id, participant_id, role)
);

CREATE TABLE source_mappings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL,
    object_type TEXT NOT NULL
        CHECK (
            object_type IN (
                'sport',
                'competition',
                'season',
                'participant',
                'event'
            )
        ),
    internal_id INTEGER NOT NULL,
    external_id TEXT NOT NULL,
    source_url TEXT,
    metadata_json TEXT
        CHECK (metadata_json IS NULL OR json_valid(metadata_json)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    CONSTRAINT fk_source_mappings_source
        FOREIGN KEY (source_id)
        REFERENCES data_sources (id)
        ON DELETE CASCADE,

    CONSTRAINT uq_source_mappings_external
        UNIQUE (source_id, object_type, external_id),

    CONSTRAINT uq_source_mappings_internal
        UNIQUE (source_id, object_type, internal_id)
);

CREATE TABLE event_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL,
    result_type TEXT NOT NULL,
    participant_id INTEGER,
    value_text TEXT,
    value_number REAL,
    position_number INTEGER,
    is_final INTEGER NOT NULL DEFAULT 0
        CHECK (is_final IN (0, 1)),
    metadata_json TEXT
        CHECK (metadata_json IS NULL OR json_valid(metadata_json)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    CONSTRAINT fk_event_results_event
        FOREIGN KEY (event_id)
        REFERENCES sports_events (id)
        ON DELETE CASCADE,

    CONSTRAINT fk_event_results_participant
        FOREIGN KEY (participant_id)
        REFERENCES participants (id)
        ON DELETE SET NULL
);

CREATE TABLE event_statistics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL,
    participant_id INTEGER,
    source_id INTEGER,
    statistic_key TEXT NOT NULL,
    statistic_name TEXT,
    value_number REAL,
    value_text TEXT,
    unit TEXT,
    period TEXT,
    recorded_at TEXT,
    metadata_json TEXT
        CHECK (metadata_json IS NULL OR json_valid(metadata_json)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    CONSTRAINT fk_event_statistics_event
        FOREIGN KEY (event_id)
        REFERENCES sports_events (id)
        ON DELETE CASCADE,

    CONSTRAINT fk_event_statistics_participant
        FOREIGN KEY (participant_id)
        REFERENCES participants (id)
        ON DELETE SET NULL,

    CONSTRAINT fk_event_statistics_source
        FOREIGN KEY (source_id)
        REFERENCES data_sources (id)
        ON DELETE SET NULL
);

CREATE TABLE bookmakers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bookmaker_key TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    source_id INTEGER,
    website_url TEXT,
    is_active INTEGER NOT NULL DEFAULT 1
        CHECK (is_active IN (0, 1)),
    metadata_json TEXT
        CHECK (metadata_json IS NULL OR json_valid(metadata_json)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    CONSTRAINT fk_bookmakers_source
        FOREIGN KEY (source_id)
        REFERENCES data_sources (id)
        ON DELETE SET NULL
);

CREATE TABLE betting_markets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL,
    bookmaker_id INTEGER NOT NULL,
    market_key TEXT NOT NULL,
    name TEXT NOT NULL,
    line_value REAL,
    is_live INTEGER NOT NULL DEFAULT 0
        CHECK (is_live IN (0, 1)),
    status TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'suspended', 'closed', 'settled')),
    metadata_json TEXT
        CHECK (metadata_json IS NULL OR json_valid(metadata_json)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    CONSTRAINT fk_betting_markets_event
        FOREIGN KEY (event_id)
        REFERENCES sports_events (id)
        ON DELETE CASCADE,

    CONSTRAINT fk_betting_markets_bookmaker
        FOREIGN KEY (bookmaker_id)
        REFERENCES bookmakers (id)
        ON DELETE CASCADE
);

CREATE TABLE betting_outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_id INTEGER NOT NULL,
    outcome_key TEXT NOT NULL,
    name TEXT NOT NULL,
    participant_id INTEGER,
    line_value REAL,
    metadata_json TEXT
        CHECK (metadata_json IS NULL OR json_valid(metadata_json)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    CONSTRAINT fk_betting_outcomes_market
        FOREIGN KEY (market_id)
        REFERENCES betting_markets (id)
        ON DELETE CASCADE,

    CONSTRAINT fk_betting_outcomes_participant
        FOREIGN KEY (participant_id)
        REFERENCES participants (id)
        ON DELETE SET NULL,

    CONSTRAINT uq_betting_outcomes_market_key
        UNIQUE (market_id, outcome_key)
);

CREATE TABLE betting_odds_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    outcome_id INTEGER NOT NULL,
    odds_decimal REAL NOT NULL
        CHECK (odds_decimal > 1.0),
    implied_probability REAL
        CHECK (
            implied_probability IS NULL
            OR implied_probability BETWEEN 0.0 AND 1.0
        ),
    captured_at TEXT NOT NULL,
    valid_until TEXT,
    source_url TEXT,
    metadata_json TEXT
        CHECK (metadata_json IS NULL OR json_valid(metadata_json)),
    created_at TEXT NOT NULL,

    CONSTRAINT fk_betting_odds_snapshots_outcome
        FOREIGN KEY (outcome_id)
        REFERENCES betting_outcomes (id)
        ON DELETE CASCADE,

    CONSTRAINT uq_betting_odds_snapshot
        UNIQUE (outcome_id, captured_at)
);

CREATE TABLE calendar_event_mappings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL,
    calendar_id TEXT NOT NULL,
    outlook_event_id TEXT,
    outlook_change_key TEXT,
    content_hash TEXT,
    sync_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (
            sync_status IN (
                'pending',
                'synced',
                'failed',
                'delete_pending',
                'deleted'
            )
        ),
    sync_attempts INTEGER NOT NULL DEFAULT 0
        CHECK (sync_attempts >= 0),
    last_synced_at TEXT,
    last_sync_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    CONSTRAINT fk_calendar_event_mappings_event
        FOREIGN KEY (event_id)
        REFERENCES sports_events (id)
        ON DELETE CASCADE,

    CONSTRAINT uq_calendar_event_mapping_event
        UNIQUE (event_id, calendar_id),

    CONSTRAINT uq_calendar_event_mapping_outlook
        UNIQUE (calendar_id, outlook_event_id)
);

CREATE TABLE sync_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_type TEXT NOT NULL
        CHECK (run_type IN ('import', 'calendar_sync', 'full_sync')),
    source_id INTEGER,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL DEFAULT 'running'
        CHECK (
            status IN (
                'running',
                'completed',
                'completed_with_errors',
                'failed'
            )
        ),
    items_processed INTEGER NOT NULL DEFAULT 0
        CHECK (items_processed >= 0),
    items_created INTEGER NOT NULL DEFAULT 0
        CHECK (items_created >= 0),
    items_updated INTEGER NOT NULL DEFAULT 0
        CHECK (items_updated >= 0),
    items_deleted INTEGER NOT NULL DEFAULT 0
        CHECK (items_deleted >= 0),
    items_failed INTEGER NOT NULL DEFAULT 0
        CHECK (items_failed >= 0),
    error_message TEXT,
    metadata_json TEXT
        CHECK (metadata_json IS NULL OR json_valid(metadata_json)),

    CONSTRAINT fk_sync_runs_source
        FOREIGN KEY (source_id)
        REFERENCES data_sources (id)
        ON DELETE SET NULL,

    CONSTRAINT ck_sync_runs_time_range
        CHECK (finished_at IS NULL OR finished_at >= started_at)
);

CREATE INDEX idx_competitions_sport
    ON competitions (sport_id);

CREATE INDEX idx_seasons_competition
    ON seasons (competition_id);

CREATE INDEX idx_participants_sport
    ON participants (sport_id);

CREATE INDEX idx_sports_events_start_time
    ON sports_events (start_time);

CREATE INDEX idx_sports_events_status_start_time
    ON sports_events (status, start_time);

CREATE INDEX idx_sports_events_competition_season
    ON sports_events (competition_id, season_id);

CREATE INDEX idx_sports_events_parent
    ON sports_events (parent_event_id);

CREATE INDEX idx_event_participants_event_role
    ON event_participants (event_id, role);

CREATE INDEX idx_event_participants_participant
    ON event_participants (participant_id);

CREATE INDEX idx_source_mappings_internal_object
    ON source_mappings (object_type, internal_id);

CREATE INDEX idx_event_results_event
    ON event_results (event_id);

CREATE INDEX idx_event_statistics_event_key
    ON event_statistics (event_id, statistic_key);

CREATE INDEX idx_betting_markets_event
    ON betting_markets (event_id);

CREATE INDEX idx_betting_odds_captured_at
    ON betting_odds_snapshots (outcome_id, captured_at DESC);

CREATE INDEX idx_calendar_mappings_sync_status
    ON calendar_event_mappings (sync_status);

CREATE INDEX idx_sync_runs_started_at
    ON sync_runs (started_at DESC);