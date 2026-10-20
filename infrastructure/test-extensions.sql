-- Only for a dedicated test database, before migrations or test schemas are created.
CREATE SCHEMA IF NOT EXISTS deliverygap_test_extensions;
CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA deliverygap_test_extensions;
DO $$
BEGIN
    IF to_regtype('deliverygap_test_extensions.vector') IS NULL THEN
        RAISE EXCEPTION 'vector is installed in another namespace; use a dedicated test database';
    END IF;
END
$$;
