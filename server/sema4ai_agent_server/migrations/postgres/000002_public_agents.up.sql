ALTER TABLE agent
ADD COLUMN public BOOLEAN NOT NULL DEFAULT false;

UPDATE agent
SET public = true;