ALTER TABLE file_owners ADD COLUMN file_ref TEXT;
UPDATE file_owners SET file_ref = file_path;

ALTER TABLE file_owners ADD COLUMN file_path_expiration TIMESTAMP WITH TIME ZONE;

ALTER TABLE file_owners ADD CONSTRAINT unique_file_ref_assistant UNIQUE (file_ref, assistant_id);
ALTER TABLE file_owners ADD CONSTRAINT unique_file_ref_thread UNIQUE (file_ref, thread_id);
ALTER TABLE file_owners DROP CONSTRAINT IF EXISTS file_owners_file_path_key;