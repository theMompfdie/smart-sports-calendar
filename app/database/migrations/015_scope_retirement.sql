-- A durable routine-work gate, independent of historical source attribution.
CREATE TABLE scope_retirements (
    job_key TEXT PRIMARY KEY REFERENCES source_assignments(job_key),
    decision_json TEXT NOT NULL CHECK(json_valid(decision_json)),
    retired_at TEXT NOT NULL,
    reactivated_at TEXT
);
CREATE TABLE scope_retirement_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_key TEXT NOT NULL REFERENCES source_assignments(job_key),
    operation TEXT NOT NULL CHECK(operation IN ('deactivate','reactivate')),
    decision_json TEXT NOT NULL CHECK(json_valid(decision_json)),
    recorded_at TEXT NOT NULL
);

-- Retired identities cannot be moved or narrowed by startup configuration.
CREATE TRIGGER trg_retired_assignment_identity
BEFORE UPDATE ON source_assignments
WHEN EXISTS(SELECT 1 FROM scope_retirements r
            WHERE r.job_key=OLD.job_key AND r.reactivated_at IS NULL)
 AND (OLD.job_key IS NOT NEW.job_key OR OLD.source_id IS NOT NEW.source_id
   OR OLD.competition_id IS NOT NEW.competition_id
   OR OLD.season_id IS NOT NEW.season_id OR OLD.namespace IS NOT NEW.namespace
   OR OLD.stages_json IS NOT NEW.stages_json OR OLD.role IS NOT NEW.role
   OR OLD.is_enabled IS NOT NEW.is_enabled)
BEGIN SELECT RAISE(ABORT,'Reactivate retired scope before changing its grant'); END;
