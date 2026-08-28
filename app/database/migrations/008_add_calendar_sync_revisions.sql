ALTER TABLE sports_events
ADD COLUMN sync_revision INTEGER NOT NULL DEFAULT 1
    CHECK (sync_revision >= 1);

ALTER TABLE calendar_event_mappings
ADD COLUMN last_synced_revision INTEGER NOT NULL DEFAULT 0
    CHECK (last_synced_revision >= 0);

CREATE INDEX idx_calendar_mappings_synced_revision
    ON calendar_event_mappings (sync_status, last_synced_revision);

CREATE TRIGGER trg_sports_events_sync_revision
AFTER UPDATE OF
    sport_id,
    competition_id,
    season_id,
    parent_event_id,
    title,
    stage,
    round_name,
    start_time,
    end_time,
    timezone,
    venue_name,
    city,
    country_code,
    status,
    deleted_at
ON sports_events
FOR EACH ROW
WHEN
    OLD.sport_id IS NOT NEW.sport_id
    OR OLD.competition_id IS NOT NEW.competition_id
    OR OLD.season_id IS NOT NEW.season_id
    OR OLD.parent_event_id IS NOT NEW.parent_event_id
    OR OLD.title IS NOT NEW.title
    OR OLD.stage IS NOT NEW.stage
    OR OLD.round_name IS NOT NEW.round_name
    OR OLD.start_time IS NOT NEW.start_time
    OR OLD.end_time IS NOT NEW.end_time
    OR OLD.timezone IS NOT NEW.timezone
    OR OLD.venue_name IS NOT NEW.venue_name
    OR OLD.city IS NOT NEW.city
    OR OLD.country_code IS NOT NEW.country_code
    OR OLD.status IS NOT NEW.status
    OR OLD.deleted_at IS NOT NEW.deleted_at
BEGIN
    UPDATE sports_events
    SET sync_revision = sync_revision + 1
    WHERE id = NEW.id;
END;

CREATE TRIGGER trg_parent_event_title_sync_revision
AFTER UPDATE OF title ON sports_events
FOR EACH ROW
WHEN OLD.title IS NOT NEW.title
BEGIN
    UPDATE sports_events
    SET sync_revision = sync_revision + 1
    WHERE parent_event_id = NEW.id;
END;

CREATE TRIGGER trg_event_participants_insert_sync_revision
AFTER INSERT ON event_participants
FOR EACH ROW
BEGIN
    UPDATE sports_events
    SET sync_revision = sync_revision + 1
    WHERE id = NEW.event_id;
END;

CREATE TRIGGER trg_event_participants_update_sync_revision
AFTER UPDATE OF event_id, participant_id, role, position_number
ON event_participants
FOR EACH ROW
WHEN
    OLD.event_id IS NOT NEW.event_id
    OR OLD.participant_id IS NOT NEW.participant_id
    OR OLD.role IS NOT NEW.role
    OR OLD.position_number IS NOT NEW.position_number
BEGIN
    UPDATE sports_events
    SET sync_revision = sync_revision + 1
    WHERE id IN (OLD.event_id, NEW.event_id);
END;

CREATE TRIGGER trg_event_participants_delete_sync_revision
AFTER DELETE ON event_participants
FOR EACH ROW
BEGIN
    UPDATE sports_events
    SET sync_revision = sync_revision + 1
    WHERE id = OLD.event_id;
END;

CREATE TRIGGER trg_event_results_insert_sync_revision
AFTER INSERT ON event_results
FOR EACH ROW
BEGIN
    UPDATE sports_events
    SET sync_revision = sync_revision + 1
    WHERE id = NEW.event_id;
END;

CREATE TRIGGER trg_event_results_update_sync_revision
AFTER UPDATE OF
    event_id,
    result_type,
    participant_id,
    value_text,
    value_number,
    position_number,
    is_final
ON event_results
FOR EACH ROW
WHEN
    OLD.event_id IS NOT NEW.event_id
    OR OLD.result_type IS NOT NEW.result_type
    OR OLD.participant_id IS NOT NEW.participant_id
    OR OLD.value_text IS NOT NEW.value_text
    OR OLD.value_number IS NOT NEW.value_number
    OR OLD.position_number IS NOT NEW.position_number
    OR OLD.is_final IS NOT NEW.is_final
BEGIN
    UPDATE sports_events
    SET sync_revision = sync_revision + 1
    WHERE id IN (OLD.event_id, NEW.event_id);
END;

CREATE TRIGGER trg_event_results_delete_sync_revision
AFTER DELETE ON event_results
FOR EACH ROW
BEGIN
    UPDATE sports_events
    SET sync_revision = sync_revision + 1
    WHERE id = OLD.event_id;
END;

CREATE TRIGGER trg_event_statistics_insert_sync_revision
AFTER INSERT ON event_statistics
FOR EACH ROW
BEGIN
    UPDATE sports_events
    SET sync_revision = sync_revision + 1
    WHERE id = NEW.event_id;
END;

CREATE TRIGGER trg_event_statistics_update_sync_revision
AFTER UPDATE OF
    event_id,
    participant_id,
    statistic_key,
    statistic_name,
    value_number,
    value_text,
    unit,
    period,
    recorded_at
ON event_statistics
FOR EACH ROW
WHEN
    OLD.event_id IS NOT NEW.event_id
    OR OLD.participant_id IS NOT NEW.participant_id
    OR OLD.statistic_key IS NOT NEW.statistic_key
    OR OLD.statistic_name IS NOT NEW.statistic_name
    OR OLD.value_number IS NOT NEW.value_number
    OR OLD.value_text IS NOT NEW.value_text
    OR OLD.unit IS NOT NEW.unit
    OR OLD.period IS NOT NEW.period
    OR OLD.recorded_at IS NOT NEW.recorded_at
BEGIN
    UPDATE sports_events
    SET sync_revision = sync_revision + 1
    WHERE id IN (OLD.event_id, NEW.event_id);
END;

CREATE TRIGGER trg_event_statistics_delete_sync_revision
AFTER DELETE ON event_statistics
FOR EACH ROW
BEGIN
    UPDATE sports_events
    SET sync_revision = sync_revision + 1
    WHERE id = OLD.event_id;
END;

CREATE TRIGGER trg_participants_name_sync_revision
AFTER UPDATE OF name ON participants
FOR EACH ROW
WHEN OLD.name IS NOT NEW.name
BEGIN
    UPDATE sports_events
    SET sync_revision = sync_revision + 1
    WHERE id IN (
        SELECT event_id
        FROM event_participants
        WHERE participant_id = NEW.id
    );
END;

CREATE TRIGGER trg_sports_name_sync_revision
AFTER UPDATE OF name ON sports
FOR EACH ROW
WHEN OLD.name IS NOT NEW.name
BEGIN
    UPDATE sports_events
    SET sync_revision = sync_revision + 1
    WHERE sport_id = NEW.id;
END;

CREATE TRIGGER trg_competitions_name_sync_revision
AFTER UPDATE OF name ON competitions
FOR EACH ROW
WHEN OLD.name IS NOT NEW.name
BEGIN
    UPDATE sports_events
    SET sync_revision = sync_revision + 1
    WHERE competition_id = NEW.id;
END;

CREATE TRIGGER trg_seasons_name_sync_revision
AFTER UPDATE OF name ON seasons
FOR EACH ROW
WHEN OLD.name IS NOT NEW.name
BEGIN
    UPDATE sports_events
    SET sync_revision = sync_revision + 1
    WHERE season_id = NEW.id;
END;

CREATE TRIGGER trg_data_sources_attribution_sync_revision
AFTER UPDATE OF metadata_json, is_active ON data_sources
FOR EACH ROW
WHEN
    OLD.metadata_json IS NOT NEW.metadata_json
    OR OLD.is_active IS NOT NEW.is_active
BEGIN
    UPDATE sports_events
    SET sync_revision = sync_revision + 1
    WHERE EXISTS (
        SELECT 1
        FROM source_assignments AS assignment
        WHERE assignment.source_id = NEW.id
          AND assignment.competition_id = sports_events.competition_id
          AND assignment.season_id = sports_events.season_id
          AND assignment.role = 'authoritative'
          AND assignment.is_enabled = 1
    );
END;

CREATE TRIGGER trg_source_assignments_insert_sync_revision
AFTER INSERT ON source_assignments
FOR EACH ROW
WHEN NEW.role = 'authoritative' AND NEW.is_enabled = 1
BEGIN
    UPDATE sports_events
    SET sync_revision = sync_revision + 1
    WHERE competition_id = NEW.competition_id
      AND season_id = NEW.season_id;
END;

CREATE TRIGGER trg_source_assignments_update_sync_revision
AFTER UPDATE OF source_id, competition_id, season_id, role, is_enabled
ON source_assignments
FOR EACH ROW
WHEN
    OLD.source_id IS NOT NEW.source_id
    OR OLD.competition_id IS NOT NEW.competition_id
    OR OLD.season_id IS NOT NEW.season_id
    OR OLD.role IS NOT NEW.role
    OR OLD.is_enabled IS NOT NEW.is_enabled
BEGIN
    UPDATE sports_events
    SET sync_revision = sync_revision + 1
    WHERE (
        OLD.role = 'authoritative'
        AND OLD.is_enabled = 1
        AND competition_id = OLD.competition_id
        AND season_id = OLD.season_id
    ) OR (
        NEW.role = 'authoritative'
        AND NEW.is_enabled = 1
        AND competition_id = NEW.competition_id
        AND season_id = NEW.season_id
    );
END;

CREATE TRIGGER trg_source_assignments_delete_sync_revision
AFTER DELETE ON source_assignments
FOR EACH ROW
WHEN OLD.role = 'authoritative' AND OLD.is_enabled = 1
BEGIN
    UPDATE sports_events
    SET sync_revision = sync_revision + 1
    WHERE competition_id = OLD.competition_id
      AND season_id = OLD.season_id;
END;
