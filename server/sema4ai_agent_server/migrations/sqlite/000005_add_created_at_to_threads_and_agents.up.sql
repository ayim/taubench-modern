ALTER TABLE agent ADD COLUMN created_at DATETIME DEFAULT (datetime('now'));
ALTER TABLE thread ADD COLUMN created_at DATETIME DEFAULT (datetime('now'));