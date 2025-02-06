PRAGMA foreign_keys = OFF;

DROP FUNCTION IF EXISTS v2_check_user_access;

DROP TABLE IF EXISTS v2_memory;
DROP TABLE IF EXISTS v2_file_owner;
DROP TABLE IF EXISTS v2_scoped_storage;
DROP TABLE IF EXISTS v2_thread_message;
DROP TABLE IF EXISTS v2_thread;
DROP TABLE IF EXISTS v2_agent_run_steps;
DROP TABLE IF EXISTS v2_agent_runs;
DROP TABLE IF EXISTS v2_agent;
DROP TABLE IF EXISTS v2_user;

PRAGMA foreign_keys = ON;
