ALTER TABLE agent
DROP COLUMN status;

ALTER TABLE file_owners
ADD COLUMN embedding_status VARCHAR(255) DEFAULT NULL;
UPDATE file_owners
SET embedding_status = 'success'
WHERE embedded = true;