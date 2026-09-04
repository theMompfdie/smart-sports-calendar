ALTER TABLE calendar_event_mappings
ADD COLUMN presentation_revision INTEGER NOT NULL DEFAULT 1
    CHECK (presentation_revision >= 1);

ALTER TABLE calendar_event_mappings
ADD COLUMN last_synced_presentation_revision INTEGER NOT NULL DEFAULT 0
    CHECK (last_synced_presentation_revision >= 0);

CREATE INDEX idx_calendar_mappings_presentation_revision
    ON calendar_event_mappings (
        sync_status,
        presentation_revision,
        last_synced_presentation_revision
    );
