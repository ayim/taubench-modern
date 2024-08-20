ALTER TABLE file_owners
DROP CONSTRAINT IF EXISTS unique_file_ref_assistant;

ALTER TABLE file_owners
DROP CONSTRAINT IF EXISTS unique_file_ref_thread;

ALTER TABLE file_owners DROP COLUMN IF EXISTS file_ref;
ALTER TABLE file_owners DROP COLUMN IF EXISTS file_path_expiration;

ALTER TABLE file_owners ADD CONSTRAINT file_owners_file_path_key UNIQUE (file_path);