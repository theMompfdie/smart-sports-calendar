ALTER TABLE sync_runs
RENAME TO sync_runs_legacy;

CREATE TABLE sync_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_type TEXT NOT NULL
        CHECK (
            run_type IN (
                'import',
                'provider_import',
                'calendar_sync',
                'full_sync'
            )
        ),
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
    items_unchanged INTEGER NOT NULL DEFAULT 0
        CHECK (items_unchanged >= 0),
    items_cancelled INTEGER NOT NULL DEFAULT 0
        CHECK (items_cancelled >= 0),
    items_deleted INTEGER NOT NULL DEFAULT 0
        CHECK (items_deleted >= 0),
    items_deferred INTEGER NOT NULL DEFAULT 0
        CHECK (items_deferred >= 0),
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

INSERT INTO sync_runs (
    id,
    run_type,
    source_id,
    started_at,
    finished_at,
    status,
    items_processed,
    items_created,
    items_updated,
    items_unchanged,
    items_cancelled,
    items_deleted,
    items_deferred,
    items_failed,
    error_message,
    metadata_json
)
SELECT
    id,
    run_type,
    source_id,
    started_at,
    finished_at,
    status,
    items_processed,
    items_created,
    items_updated,
    items_unchanged,
    items_cancelled,
    items_deleted,
    0,
    items_failed,
    error_message,
    metadata_json
FROM sync_runs_legacy;

DROP TABLE sync_runs_legacy;

CREATE INDEX idx_sync_runs_started_at
    ON sync_runs (started_at DESC);
