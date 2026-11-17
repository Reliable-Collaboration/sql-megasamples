-- The bulk loader preallocates WAL ahead of the current segment. Lowering max_wal_size and
-- checkpointing alone leaves those future segments untouched. Generate a little real WAL and
-- rotate through the allocated segments, then let PostgreSQL reclaim them at a checkpoint.
-- Run only in the builder's private cluster, after restarting with the smaller WAL bounds.
CREATE TABLE public.megasamples_wal_packaging_probe (i integer);
DO $$
DECLARE
    segments integer;
    i integer;
BEGIN
    SELECT count(*) + 2 INTO segments FROM pg_ls_waldir() WHERE name ~ '^[0-9A-F]{24}$';
    FOR i IN 1..segments LOOP
        INSERT INTO public.megasamples_wal_packaging_probe VALUES (i);
        PERFORM pg_switch_wal();
    END LOOP;
END $$;
DROP TABLE public.megasamples_wal_packaging_probe;
CHECKPOINT;
DO $$
BEGIN
    IF (SELECT sum(size) FROM pg_ls_waldir() WHERE name ~ '^[0-9A-F]{24}$') > 128 * 1024 * 1024 THEN
        RAISE EXCEPTION 'bulk-load WAL was not reclaimed before image packaging';
    END IF;
END $$;
