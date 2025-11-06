ALTER TABLE v2."file_owner"
    ADD COLUMN scenario_id UUID;

ALTER TABLE v2."file_owner"
    ADD CONSTRAINT fk_file_owner_scenario_id_v2
        FOREIGN KEY (scenario_id)
        REFERENCES v2."scenarios"(scenario_id)
        ON DELETE CASCADE;

ALTER TABLE v2."file_owner"
    ADD CONSTRAINT unique_file_ref_scenario_v2
        UNIQUE (file_ref, scenario_id);

CREATE INDEX IF NOT EXISTS idx_file_owner_scenario_id_v2
    ON v2."file_owner"(scenario_id);
