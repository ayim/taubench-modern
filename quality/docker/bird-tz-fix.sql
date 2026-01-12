-- The pg_dump from Bird Bench dev dataset are in UTC+8 timezone. When this data is loaded and
-- we query it with the UTC timezone, the timestamp values (ignoring tz) are 8 hours less than
-- we expect them to be which causes queries to fail. Rather than account for specific timezones
-- at query time, we shift all timestamp columns forward 8hours to make them appear in the UTC+8
-- date and time values when using the UTC timezone (which we are doing with Ibis internally).
DO $$
 DECLARE r record;
 BEGIN
   FOR r IN
     SELECT table_schema, table_name, column_name
     FROM information_schema.columns
     WHERE data_type = 'timestamp with time zone'
       AND table_schema IN ('public')
   LOOP
     EXECUTE format(
       'UPDATE %I.%I SET %I = %I + interval ''8 hours'' WHERE %I IS NOT NULL',
       r.table_schema, r.table_name, r.column_name, r.column_name, r.column_name
     );
   END LOOP;
 END $$;
