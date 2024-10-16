BEGIN;
-- Step 1: Add the new 'advanced_config' column
ALTER TABLE agent
ADD COLUMN advanced_config JSONB;
-- Step 2: Populate 'advanced_config' with data from 'architecture' and 'reasoning'
UPDATE agent
SET advanced_config = jsonb_build_object(
        'architecture',
        architecture,
        'reasoning',
        reasoning
    );
-- Step 3: Set 'advanced_config' as NOT NULL if necessary
ALTER TABLE agent
ALTER COLUMN advanced_config
SET NOT NULL;
-- Step 4: Remove the old 'architecture' and 'reasoning' columns
ALTER TABLE agent DROP COLUMN architecture,
    DROP COLUMN reasoning;
COMMIT;