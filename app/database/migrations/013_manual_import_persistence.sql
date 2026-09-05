-- Preserve all legacy assignments as broad grants and retain their IDs.
DROP TRIGGER trg_data_sources_attribution_sync_revision;
CREATE TABLE source_assignments_next (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_key TEXT NOT NULL UNIQUE,
    source_id INTEGER NOT NULL REFERENCES data_sources(id) ON DELETE RESTRICT,
    competition_id INTEGER NOT NULL REFERENCES competitions(id) ON DELETE RESTRICT,
    season_id INTEGER NOT NULL REFERENCES seasons(id) ON DELETE RESTRICT,
    role TEXT NOT NULL CHECK(role IN ('authoritative','bootstrap','verification','disabled')),
    interval_seconds INTEGER,
    is_enabled INTEGER NOT NULL DEFAULT 1 CHECK(is_enabled IN (0,1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    namespace TEXT UNIQUE,
    stages_json TEXT CHECK(stages_json IS NULL OR
        (json_valid(stages_json) AND json_type(stages_json) = 'array'
         AND json_array_length(stages_json) > 0)),
    CHECK((namespace IS NULL AND interval_seconds IS NOT NULL AND interval_seconds > 0) OR
          (namespace IS NOT NULL AND interval_seconds IS NULL
           AND role IN ('authoritative','disabled')))
);
INSERT INTO source_assignments_next
    (id,job_key,source_id,competition_id,season_id,role,interval_seconds,
     is_enabled,created_at,updated_at)
SELECT id,job_key,source_id,competition_id,season_id,role,interval_seconds,
       is_enabled,created_at,updated_at FROM source_assignments;
DROP TABLE source_assignments;
ALTER TABLE source_assignments_next RENAME TO source_assignments;
CREATE UNIQUE INDEX uq_source_assignments_automatic_scope
ON source_assignments(source_id,competition_id,season_id) WHERE namespace IS NULL;
CREATE INDEX idx_source_assignments_scope
ON source_assignments(competition_id,season_id,is_enabled);

CREATE TRIGGER trg_source_authority_insert
BEFORE INSERT ON source_assignments
BEGIN
    SELECT CASE WHEN NEW.stages_json IS NOT NULL AND (
        EXISTS(SELECT 1 FROM json_each(NEW.stages_json)
               WHERE type != 'text' OR length(value) = 0 OR trim(value) != value)
        OR (SELECT count(*) FROM json_each(NEW.stages_json)) !=
           (SELECT count(DISTINCT value) FROM json_each(NEW.stages_json))
    ) THEN RAISE(ABORT,'Invalid authority stages') END;
    SELECT CASE WHEN NEW.is_enabled = 1 AND NEW.role = 'authoritative'
      AND EXISTS(
        SELECT 1 FROM source_assignments AS existing
        WHERE existing.id != NEW.id AND existing.job_key != NEW.job_key
          AND existing.is_enabled = 1
          AND existing.role = 'authoritative'
          AND existing.competition_id = NEW.competition_id
          AND existing.season_id = NEW.season_id
          AND (existing.stages_json IS NULL OR NEW.stages_json IS NULL OR
               EXISTS(SELECT 1 FROM json_each(existing.stages_json) AS old_stage
                      JOIN json_each(NEW.stages_json) AS new_stage
                      ON old_stage.value = new_stage.value))
    ) THEN RAISE(ABORT,'Overlapping authoritative writers') END;
END;

CREATE TRIGGER trg_source_authority_update
BEFORE UPDATE ON source_assignments
BEGIN
    SELECT CASE WHEN NEW.stages_json IS NOT NULL AND (
        EXISTS(SELECT 1 FROM json_each(NEW.stages_json)
               WHERE type != 'text' OR length(value) = 0 OR trim(value) != value)
        OR (SELECT count(*) FROM json_each(NEW.stages_json)) !=
           (SELECT count(DISTINCT value) FROM json_each(NEW.stages_json))
    ) THEN RAISE(ABORT,'Invalid authority stages') END;
    SELECT CASE WHEN NEW.is_enabled = 1 AND NEW.role = 'authoritative'
      AND EXISTS(
        SELECT 1 FROM source_assignments AS existing
        WHERE existing.id != NEW.id AND existing.job_key != NEW.job_key
          AND existing.is_enabled = 1
          AND existing.role = 'authoritative'
          AND existing.competition_id = NEW.competition_id
          AND existing.season_id = NEW.season_id
          AND (existing.stages_json IS NULL OR NEW.stages_json IS NULL OR
               EXISTS(SELECT 1 FROM json_each(existing.stages_json) AS old_stage
                      JOIN json_each(NEW.stages_json) AS new_stage
                      ON old_stage.value = new_stage.value))
    ) THEN RAISE(ABORT,'Overlapping authoritative writers') END;
END;

CREATE TRIGGER trg_source_assignments_insert_sync_revision
AFTER INSERT ON source_assignments
BEGIN
    UPDATE sports_events SET sync_revision = sync_revision + 1
    WHERE (NEW.role = 'authoritative' AND NEW.is_enabled = 1
        AND competition_id = NEW.competition_id AND season_id = NEW.season_id
        AND (NEW.stages_json IS NULL OR stage IN
            (SELECT value FROM json_each(NEW.stages_json))));
END;

CREATE TRIGGER trg_source_assignments_delete_sync_revision
AFTER DELETE ON source_assignments
BEGIN
    UPDATE sports_events SET sync_revision = sync_revision + 1
    WHERE (OLD.role = 'authoritative' AND OLD.is_enabled = 1
        AND competition_id = OLD.competition_id AND season_id = OLD.season_id
        AND (OLD.stages_json IS NULL OR stage IN
            (SELECT value FROM json_each(OLD.stages_json))));
END;

CREATE TRIGGER trg_source_assignments_update_sync_revision
AFTER UPDATE ON source_assignments
WHEN OLD.source_id IS NOT NEW.source_id OR OLD.role IS NOT NEW.role
 OR OLD.is_enabled IS NOT NEW.is_enabled OR OLD.competition_id IS NOT NEW.competition_id
 OR OLD.season_id IS NOT NEW.season_id OR OLD.stages_json IS NOT NEW.stages_json
 OR OLD.namespace IS NOT NEW.namespace
BEGIN
    UPDATE sports_events SET sync_revision = sync_revision + 1
    WHERE (OLD.role = 'authoritative' AND OLD.is_enabled = 1
        AND competition_id = OLD.competition_id AND season_id = OLD.season_id
        AND (OLD.stages_json IS NULL OR stage IN
            (SELECT value FROM json_each(OLD.stages_json)))) OR (NEW.role = 'authoritative' AND NEW.is_enabled = 1
        AND competition_id = NEW.competition_id AND season_id = NEW.season_id
        AND (NEW.stages_json IS NULL OR stage IN
            (SELECT value FROM json_each(NEW.stages_json))));
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
          AND (assignment.stages_json IS NULL OR sports_events.stage IN
               (SELECT value FROM json_each(assignment.stages_json)))
    );
END;


CREATE TABLE manual_import_instance (
    id INTEGER PRIMARY KEY CHECK(id = 1),
    instance_id TEXT NOT NULL UNIQUE,
    instance_ref TEXT
);
INSERT INTO manual_import_instance(id,instance_id) VALUES(1,lower(hex(randomblob(16))));
CREATE TABLE manual_import_profiles (
    namespace TEXT PRIMARY KEY REFERENCES source_assignments(namespace),
    configuration_json TEXT NOT NULL CHECK(json_valid(configuration_json)),
    attribution TEXT,
    updated_at TEXT NOT NULL
);
CREATE TABLE import_batches (
    submission_id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    import_type TEXT NOT NULL CHECK(import_type = 'fixture_schedule'),
    schema_version INTEGER NOT NULL CHECK(schema_version = 1),
    payload BLOB NOT NULL,
    manifest_sha256 TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('RECEIVED','AWAITING_APPROVAL','REJECTED',
        'APPROVED','NEEDS_REVIEW','APPLIED','RETRYABLE_FAILURE')),
    preview_json TEXT,
    preview_sha256 TEXT,
    approval_payload BLOB,
    error_code TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX idx_import_batches_state ON import_batches(state,created_at,submission_id);
CREATE TRIGGER trg_import_batch_immutable BEFORE UPDATE OF
    submission_id,namespace,import_type,schema_version,payload,manifest_sha256
ON import_batches BEGIN SELECT RAISE(ABORT,'Immutable import payload'); END;
CREATE TABLE manual_import_receipts (
    submission_id TEXT PRIMARY KEY REFERENCES import_batches(submission_id),
    receipt_json TEXT NOT NULL CHECK(json_valid(receipt_json)),
    committed_at TEXT NOT NULL
);
CREATE TRIGGER trg_manual_receipt_immutable BEFORE UPDATE ON manual_import_receipts
BEGIN SELECT RAISE(ABORT,'Immutable import receipt'); END;
CREATE TABLE manual_review_plans (
    namespace TEXT PRIMARY KEY REFERENCES manual_import_profiles(namespace),
    submission_id TEXT NOT NULL REFERENCES manual_import_receipts(submission_id),
    plan_json TEXT NOT NULL CHECK(json_valid(plan_json)),
    updated_at TEXT NOT NULL
);
CREATE TRIGGER trg_manual_attribution_revision
AFTER UPDATE OF attribution ON manual_import_profiles
WHEN OLD.attribution IS NOT NEW.attribution
BEGIN
    UPDATE sports_events SET sync_revision = sync_revision + 1
    WHERE id IN (
        SELECT m.internal_id FROM source_mappings AS m
        JOIN data_sources AS source ON source.id = m.source_id
        WHERE source.source_key = 'manual' AND m.object_type = 'event'
          AND substr(m.external_id,1,length(NEW.namespace)+1) = NEW.namespace || ':'
    );
END;

CREATE TRIGGER trg_applied_batch_immutable BEFORE UPDATE ON import_batches
WHEN OLD.state = 'APPLIED'
BEGIN SELECT RAISE(ABORT,'Applied package is immutable'); END;
