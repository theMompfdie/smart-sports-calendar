CREATE TABLE manual_review_appointments (
    namespace TEXT NOT NULL REFERENCES manual_import_profiles(namespace),
    task_id TEXT NOT NULL,
    calendar_id TEXT NOT NULL,
    generation INTEGER NOT NULL DEFAULT 1,
    task_json TEXT NOT NULL,
    projected_start TEXT NOT NULL,
    desired_hash TEXT NOT NULL,
    applied_hash TEXT,
    event_id TEXT,
    transaction_id TEXT NOT NULL,
    retired INTEGER NOT NULL DEFAULT 0 CHECK(retired IN (0,1)),
    PRIMARY KEY(namespace,task_id,calendar_id)
);
