CREATE TABLE calendar_event_asset_attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    calendar_event_mapping_id INTEGER NOT NULL,
    slot TEXT NOT NULL
        CHECK (slot IN ('competition', 'home', 'away', 'final')),
    desired_asset_id INTEGER,
    desired_sha256 TEXT,
    synchronized_asset_id INTEGER,
    synchronized_sha256 TEXT,
    content_id TEXT,
    outlook_attachment_id TEXT,
    pending_asset_id INTEGER,
    pending_sha256 TEXT,
    pending_content_id TEXT,
    pending_outlook_attachment_id TEXT,
    obsolete_outlook_attachment_id TEXT,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (
            status IN (
                'pending',
                'uploaded',
                'synced',
                'failed',
                'cleanup_pending',
                'event_deleted'
            )
        ),
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    last_attempt_at TEXT,
    last_synced_at TEXT,
    last_error TEXT
        CHECK (
            last_error IS NULL
            OR (
                length(last_error) BETWEEN 1 AND 500
                AND last_error = trim(last_error)
            )
        ),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    CONSTRAINT ck_event_asset_desired_pair CHECK (
        (desired_asset_id IS NULL AND desired_sha256 IS NULL)
        OR (desired_asset_id IS NOT NULL AND desired_sha256 IS NOT NULL)
    ),
    CONSTRAINT ck_event_asset_synchronized_shape CHECK (
        (
            synchronized_asset_id IS NULL
            AND synchronized_sha256 IS NULL
            AND content_id IS NULL
            AND outlook_attachment_id IS NULL
        )
        OR (
            synchronized_asset_id IS NOT NULL
            AND synchronized_sha256 IS NOT NULL
            AND content_id IS NOT NULL
            AND outlook_attachment_id IS NOT NULL
        )
    ),
    CONSTRAINT ck_event_asset_pending_shape CHECK (
        (
            pending_asset_id IS NULL
            AND pending_sha256 IS NULL
            AND pending_content_id IS NULL
            AND pending_outlook_attachment_id IS NULL
        )
        OR (
            pending_asset_id IS NOT NULL
            AND pending_sha256 IS NOT NULL
            AND pending_content_id IS NOT NULL
        )
    ),
    CONSTRAINT ck_event_asset_hashes CHECK (
        (
            desired_sha256 IS NULL
            OR (
                length(desired_sha256) = 64
                AND desired_sha256 = lower(desired_sha256)
                AND desired_sha256 NOT GLOB '*[^0-9a-f]*'
            )
        )
        AND (
            synchronized_sha256 IS NULL
            OR (
                length(synchronized_sha256) = 64
                AND synchronized_sha256 = lower(synchronized_sha256)
                AND synchronized_sha256 NOT GLOB '*[^0-9a-f]*'
            )
        )
        AND (
            pending_sha256 IS NULL
            OR (
                length(pending_sha256) = 64
                AND pending_sha256 = lower(pending_sha256)
                AND pending_sha256 NOT GLOB '*[^0-9a-f]*'
            )
        )
    ),
    CONSTRAINT ck_event_asset_remote_ids CHECK (
        (content_id IS NULL OR length(content_id) BETWEEN 1 AND 255)
        AND (
            outlook_attachment_id IS NULL
            OR length(outlook_attachment_id) BETWEEN 1 AND 1000
        )
        AND (
            pending_content_id IS NULL
            OR length(pending_content_id) BETWEEN 1 AND 255
        )
        AND (
            pending_outlook_attachment_id IS NULL
            OR length(pending_outlook_attachment_id) BETWEEN 1 AND 1000
        )
        AND (
            obsolete_outlook_attachment_id IS NULL
            OR length(obsolete_outlook_attachment_id) BETWEEN 1 AND 1000
        )
    ),

    CONSTRAINT fk_event_asset_calendar_mapping
        FOREIGN KEY (calendar_event_mapping_id)
        REFERENCES calendar_event_mappings (id)
        ON DELETE CASCADE,
    CONSTRAINT fk_event_asset_desired
        FOREIGN KEY (desired_asset_id) REFERENCES media_assets (id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_event_asset_synchronized
        FOREIGN KEY (synchronized_asset_id) REFERENCES media_assets (id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_event_asset_pending
        FOREIGN KEY (pending_asset_id) REFERENCES media_assets (id)
        ON DELETE RESTRICT
);

CREATE UNIQUE INDEX uq_event_asset_slot
    ON calendar_event_asset_attachments (calendar_event_mapping_id, slot);

CREATE INDEX idx_event_asset_status
    ON calendar_event_asset_attachments (
        status,
        last_attempt_at,
        calendar_event_mapping_id
    );

CREATE INDEX idx_event_asset_desired
    ON calendar_event_asset_attachments (desired_asset_id, desired_sha256);

CREATE INDEX idx_event_asset_synchronized
    ON calendar_event_asset_attachments (
        synchronized_asset_id,
        synchronized_sha256
    );
