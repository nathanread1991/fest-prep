-- Initialize database with extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create indexes for better performance (will be created by SQLAlchemy, but good to have as reference)
-- These will be created automatically by the SQLAlchemy models