ALTER TABLE sync_runs
ADD COLUMN items_unchanged INTEGER NOT NULL DEFAULT 0
    CHECK (items_unchanged >= 0);

ALTER TABLE sync_runs
ADD COLUMN items_cancelled INTEGER NOT NULL DEFAULT 0
    CHECK (items_cancelled >= 0);