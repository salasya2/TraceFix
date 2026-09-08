-- Runtime role must not own tables, be superuser, or have BYPASSRLS.
CREATE USER tracefix_app WITH PASSWORD 'tracefix_app' NOSUPERUSER NOBYPASSRLS;
GRANT CONNECT ON DATABASE tracefix TO tracefix_app;
