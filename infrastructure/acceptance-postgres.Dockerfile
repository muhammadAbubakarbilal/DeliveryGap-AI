FROM pgvector/pgvector:pg16
COPY infrastructure/test-extensions.sql /docker-entrypoint-initdb.d/test-extensions.sql
