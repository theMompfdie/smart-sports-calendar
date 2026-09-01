CREATE TABLE media_assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_key TEXT NOT NULL,
    version INTEGER NOT NULL CHECK (version >= 1),
    owner_type TEXT NOT NULL
        CHECK (owner_type IN ('project', 'sport', 'competition', 'participant')),
    project_key TEXT,
    sport_id INTEGER,
    competition_id INTEGER,
    participant_id INTEGER,
    variant TEXT NOT NULL,
    mime_type TEXT NOT NULL CHECK (mime_type = 'image/png'),
    width INTEGER NOT NULL CHECK (width > 0),
    height INTEGER NOT NULL CHECK (height > 0),
    byte_size INTEGER NOT NULL CHECK (byte_size > 0),
    sha256 TEXT NOT NULL
        CHECK (
            length(sha256) = 64
            AND sha256 = lower(sha256)
            AND sha256 NOT GLOB '*[^0-9a-f]*'
        ),
    storage_path TEXT NOT NULL
        CHECK (
            length(storage_path) BETWEEN 1 AND 255
            AND storage_path = trim(storage_path)
            AND storage_path NOT LIKE '/%'
            AND storage_path NOT LIKE '\%'
            AND instr(storage_path, '..') = 0
            AND instr(storage_path, '\') = 0
            AND instr(storage_path, ':') = 0
        ),
    source_reference TEXT NOT NULL
        CHECK (
            length(source_reference) BETWEEN 1 AND 1000
            AND source_reference = trim(source_reference)
        ),
    license_name TEXT
        CHECK (
            license_name IS NULL
            OR (
                length(license_name) BETWEEN 1 AND 200
                AND license_name = trim(license_name)
            )
        ),
    permission_reference TEXT
        CHECK (
            permission_reference IS NULL
            OR (
                length(permission_reference) BETWEEN 1 AND 1000
                AND permission_reference = trim(permission_reference)
            )
        ),
    attribution TEXT
        CHECK (
            attribution IS NULL
            OR (
                length(attribution) BETWEEN 1 AND 500
                AND attribution = trim(attribution)
            )
        ),
    is_approved INTEGER NOT NULL DEFAULT 0 CHECK (is_approved IN (0, 1)),
    approved_by TEXT
        CHECK (
            approved_by IS NULL
            OR (
                length(approved_by) BETWEEN 1 AND 200
                AND approved_by = trim(approved_by)
            )
        ),
    approved_at TEXT,
    is_active INTEGER NOT NULL DEFAULT 0 CHECK (is_active IN (0, 1)),
    deactivated_at TEXT,
    superseded_by_id INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    CONSTRAINT ck_media_assets_normalized_keys CHECK (
        length(asset_key) BETWEEN 1 AND 128
        AND asset_key = lower(trim(asset_key))
        AND asset_key GLOB '[a-z0-9]*'
        AND asset_key NOT GLOB '*[^a-z0-9_.-]*'
        AND length(variant) BETWEEN 1 AND 64
        AND variant = lower(trim(variant))
        AND variant GLOB '[a-z0-9]*'
        AND variant NOT GLOB '*[^a-z0-9_.-]*'
    ),
    CONSTRAINT ck_media_assets_owner_shape CHECK (
        (
            owner_type = 'project'
            AND project_key IS NOT NULL
            AND sport_id IS NULL
            AND competition_id IS NULL
            AND participant_id IS NULL
        )
        OR (
            owner_type = 'sport'
            AND project_key IS NULL
            AND sport_id IS NOT NULL
            AND competition_id IS NULL
            AND participant_id IS NULL
        )
        OR (
            owner_type = 'competition'
            AND project_key IS NULL
            AND sport_id IS NULL
            AND competition_id IS NOT NULL
            AND participant_id IS NULL
        )
        OR (
            owner_type = 'participant'
            AND project_key IS NULL
            AND sport_id IS NULL
            AND competition_id IS NULL
            AND participant_id IS NOT NULL
        )
    ),
    CONSTRAINT ck_media_assets_project_key CHECK (
        project_key IS NULL
        OR (
            length(project_key) BETWEEN 1 AND 128
            AND project_key = lower(trim(project_key))
            AND project_key GLOB '[a-z0-9]*'
            AND project_key NOT GLOB '*[^a-z0-9_.-]*'
        )
    ),
    CONSTRAINT ck_media_assets_rights_evidence CHECK (
        license_name IS NOT NULL OR permission_reference IS NOT NULL
    ),
    CONSTRAINT ck_media_assets_approval CHECK (
        (
            is_approved = 0
            AND approved_by IS NULL
            AND approved_at IS NULL
            AND is_active = 0
        )
        OR (
            is_approved = 1
            AND approved_by IS NOT NULL
            AND approved_at IS NOT NULL
        )
    ),

    CONSTRAINT fk_media_assets_sport
        FOREIGN KEY (sport_id) REFERENCES sports (id) ON DELETE RESTRICT,
    CONSTRAINT fk_media_assets_competition
        FOREIGN KEY (competition_id) REFERENCES competitions (id) ON DELETE RESTRICT,
    CONSTRAINT fk_media_assets_participant
        FOREIGN KEY (participant_id) REFERENCES participants (id) ON DELETE RESTRICT,
    CONSTRAINT fk_media_assets_superseded_by
        FOREIGN KEY (superseded_by_id) REFERENCES media_assets (id) ON DELETE RESTRICT,
    CONSTRAINT uq_media_assets_version UNIQUE (asset_key, version)
);

CREATE UNIQUE INDEX uq_media_assets_active_key
    ON media_assets (asset_key)
    WHERE is_active = 1;

CREATE INDEX idx_media_assets_owner_variant
    ON media_assets (
        owner_type,
        project_key,
        sport_id,
        competition_id,
        participant_id,
        variant,
        is_active
    );

CREATE INDEX idx_media_assets_sha256 ON media_assets (sha256);
