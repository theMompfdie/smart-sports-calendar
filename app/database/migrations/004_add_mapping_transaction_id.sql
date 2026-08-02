ALTER TABLE calendar_event_mappings
RENAME TO calendar_event_mappings_legacy;

CREATE TABLE calendar_event_mappings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL,
    calendar_id TEXT NOT NULL,
    transaction_id TEXT NOT NULL,
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

    CONSTRAINT uq_calendar_event_mapping_transaction
        UNIQUE (transaction_id),

    CONSTRAINT uq_calendar_event_mapping_outlook
        UNIQUE (calendar_id, outlook_event_id)
);

INSERT INTO calendar_event_mappings (
    id,
    event_id,
    calendar_id,
    transaction_id,
    outlook_event_id,
    outlook_change_key,
    content_hash,
    sync_status,
    sync_attempts,
    last_synced_at,
    last_sync_error,
    created_at,
    updated_at
)
SELECT
    id,
    event_id,
    calendar_id,
    lower(
        hex(randomblob(4))
        || '-'
        || hex(randomblob(2))
        || '-4'
        || substr(hex(randomblob(2)), 2)
        || '-'
        || substr('89ab', abs(random()) % 4 + 1, 1)
        || substr(hex(randomblob(2)), 2)
        || '-'
        || hex(randomblob(6))
    ),
    outlook_event_id,
    outlook_change_key,
    content_hash,
    sync_status,
    sync_attempts,
    last_synced_at,
    last_sync_error,
    created_at,
    updated_at
FROM calendar_event_mappings_legacy;

DROP TABLE calendar_event_mappings_legacy;

CREATE INDEX idx_calendar_mappings_sync_status
    ON calendar_event_mappings (sync_status);