-- Local development only. Run as the PostgreSQL owner/admin when the
-- application tables were created by a different role (for example postgres).
-- The web and worker services connect as renderstudio.

GRANT USAGE ON SCHEMA public TO renderstudio;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO renderstudio;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO renderstudio;

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO renderstudio;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO renderstudio;
