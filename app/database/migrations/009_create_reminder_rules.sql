CREATE TABLE reminder_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scope TEXT NOT NULL
        CHECK (scope IN (
            'global',
            'competition',
            'participant',
            'competition_participant',
            'event'
        )),
    competition_id INTEGER,
    participant_id INTEGER,
    event_id INTEGER,
    action TEXT
        CHECK (action IS NULL OR action IN ('enable', 'suppress')),
    preferred_lead_minutes INTEGER
        CHECK (
            preferred_lead_minutes IS NULL
            OR preferred_lead_minutes >= 0
        ),
    minimum_lead_minutes INTEGER
        CHECK (
            minimum_lead_minutes IS NULL
            OR minimum_lead_minutes >= 0
        ),
    maximum_lead_minutes INTEGER
        CHECK (
            maximum_lead_minutes IS NULL
            OR maximum_lead_minutes >= 0
        ),
    quiet_start TEXT
        CHECK (
            quiet_start IS NULL
            OR (
                quiet_start GLOB '[0-2][0-9]:[0-5][0-9]'
                AND CAST(substr(quiet_start, 1, 2) AS INTEGER) <= 23
            )
        ),
    quiet_end TEXT
        CHECK (
            quiet_end IS NULL
            OR (
                quiet_end GLOB '[0-2][0-9]:[0-5][0-9]'
                AND CAST(substr(quiet_end, 1, 2) AS INTEGER) <= 23
            )
        ),
    timezone TEXT
        CHECK (
            timezone IS NULL
            OR (
                length(timezone) BETWEEN 1 AND 100
                AND timezone = trim(timezone)
            )
        ),
    is_active INTEGER NOT NULL DEFAULT 1
        CHECK (is_active IN (0, 1)),
    operator_note TEXT
        CHECK (
            operator_note IS NULL
            OR (
                length(operator_note) BETWEEN 1 AND 500
                AND operator_note = trim(operator_note)
            )
        ),
    deleted_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    CONSTRAINT ck_reminder_rules_scope_shape CHECK (
        (
            scope = 'global'
            AND competition_id IS NULL
            AND participant_id IS NULL
            AND event_id IS NULL
        )
        OR (
            scope = 'competition'
            AND competition_id IS NOT NULL
            AND participant_id IS NULL
            AND event_id IS NULL
        )
        OR (
            scope = 'participant'
            AND competition_id IS NULL
            AND participant_id IS NOT NULL
            AND event_id IS NULL
        )
        OR (
            scope = 'competition_participant'
            AND competition_id IS NOT NULL
            AND participant_id IS NOT NULL
            AND event_id IS NULL
        )
        OR (
            scope = 'event'
            AND competition_id IS NULL
            AND participant_id IS NULL
            AND event_id IS NOT NULL
        )
    ),
    CONSTRAINT ck_reminder_rules_policy_present CHECK (
        action IS NOT NULL
        OR preferred_lead_minutes IS NOT NULL
        OR minimum_lead_minutes IS NOT NULL
        OR maximum_lead_minutes IS NOT NULL
        OR quiet_start IS NOT NULL
        OR quiet_end IS NOT NULL
        OR timezone IS NOT NULL
    ),
    CONSTRAINT ck_reminder_rules_quiet_pair CHECK (
        (quiet_start IS NULL) = (quiet_end IS NULL)
    ),
    CONSTRAINT ck_reminder_rules_minimum_preferred CHECK (
        minimum_lead_minutes IS NULL
        OR preferred_lead_minutes IS NULL
        OR minimum_lead_minutes <= preferred_lead_minutes
    ),
    CONSTRAINT ck_reminder_rules_preferred_maximum CHECK (
        preferred_lead_minutes IS NULL
        OR maximum_lead_minutes IS NULL
        OR preferred_lead_minutes <= maximum_lead_minutes
    ),
    CONSTRAINT ck_reminder_rules_minimum_maximum CHECK (
        minimum_lead_minutes IS NULL
        OR maximum_lead_minutes IS NULL
        OR minimum_lead_minutes <= maximum_lead_minutes
    ),
    CONSTRAINT ck_reminder_rules_deleted_inactive CHECK (
        deleted_at IS NULL OR is_active = 0
    ),

    CONSTRAINT fk_reminder_rules_competition
        FOREIGN KEY (competition_id)
        REFERENCES competitions (id)
        ON DELETE RESTRICT,

    CONSTRAINT fk_reminder_rules_participant
        FOREIGN KEY (participant_id)
        REFERENCES participants (id)
        ON DELETE RESTRICT,

    CONSTRAINT fk_reminder_rules_event
        FOREIGN KEY (event_id)
        REFERENCES sports_events (id)
        ON DELETE RESTRICT
);

CREATE UNIQUE INDEX uq_reminder_rules_global_current
    ON reminder_rules (scope)
    WHERE scope = 'global' AND deleted_at IS NULL;

CREATE UNIQUE INDEX uq_reminder_rules_competition_current
    ON reminder_rules (competition_id)
    WHERE scope = 'competition' AND deleted_at IS NULL;

CREATE UNIQUE INDEX uq_reminder_rules_participant_current
    ON reminder_rules (participant_id)
    WHERE scope = 'participant' AND deleted_at IS NULL;

CREATE UNIQUE INDEX uq_reminder_rules_competition_participant_current
    ON reminder_rules (competition_id, participant_id)
    WHERE scope = 'competition_participant' AND deleted_at IS NULL;

CREATE UNIQUE INDEX uq_reminder_rules_event_current
    ON reminder_rules (event_id)
    WHERE scope = 'event' AND deleted_at IS NULL;

CREATE INDEX idx_reminder_rules_active_scope
    ON reminder_rules (scope, is_active)
    WHERE deleted_at IS NULL;
