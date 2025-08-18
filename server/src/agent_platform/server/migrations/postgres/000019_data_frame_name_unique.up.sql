-- add a unique constraint on the thread_id and name columns
CREATE UNIQUE INDEX IF NOT EXISTS idx_data_frames_thread_id_name ON v2.data_frames(thread_id, name);