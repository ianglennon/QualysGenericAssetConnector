-- Creates the test database on first PostgreSQL volume initialization.
-- Mounted at /docker-entrypoint-initdb.d/ in docker-compose.yml.
SELECT 'CREATE DATABASE qualys_test'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'qualys_test')\gexec
