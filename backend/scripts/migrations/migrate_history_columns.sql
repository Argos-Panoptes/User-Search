-- Add columns to user_history
ALTER TABLE user_history
ADD COLUMN IF NOT EXISTS e164 VARCHAR;
ALTER TABLE user_history
ADD COLUMN IF NOT EXISTS name VARCHAR;
ALTER TABLE user_history
ADD COLUMN IF NOT EXISTS profile_name VARCHAR;
ALTER TABLE user_history
ADD COLUMN IF NOT EXISTS profile_family_name VARCHAR;
ALTER TABLE user_history
ADD COLUMN IF NOT EXISTS profile_full_name VARCHAR;
ALTER TABLE user_history
ADD COLUMN IF NOT EXISTS active_at BIGINT;
ALTER TABLE user_history
ADD COLUMN IF NOT EXISTS about TEXT;
ALTER TABLE user_history
ADD COLUMN IF NOT EXISTS about_emoji VARCHAR;
ALTER TABLE user_history
ADD COLUMN IF NOT EXISTS remote_avatar_url VARCHAR;
ALTER TABLE user_history
ADD COLUMN IF NOT EXISTS is_admin BOOLEAN;
ALTER TABLE user_history
ADD COLUMN IF NOT EXISTS export_timestamp TIMESTAMPTZ;
ALTER TABLE user_history
ADD COLUMN IF NOT EXISTS avatar_id INTEGER;
-- Add columns to group_history
ALTER TABLE group_history
ADD COLUMN IF NOT EXISTS group_name VARCHAR;
ALTER TABLE group_history
ADD COLUMN IF NOT EXISTS number_of_members INTEGER;
ALTER TABLE group_history
ADD COLUMN IF NOT EXISTS admin_approval_required BOOLEAN;
ALTER TABLE group_history
ADD COLUMN IF NOT EXISTS group_link VARCHAR;
ALTER TABLE group_history
ADD COLUMN IF NOT EXISTS description TEXT;
ALTER TABLE group_history
ADD COLUMN IF NOT EXISTS retention_period VARCHAR;
-- Add columns to avatar_history
ALTER TABLE avatar_history
ADD COLUMN IF NOT EXISTS s3_key VARCHAR;
ALTER TABLE avatar_history
ADD COLUMN IF NOT EXISTS s3_url VARCHAR;
ALTER TABLE avatar_history
ADD COLUMN IF NOT EXISTS filename VARCHAR;
ALTER TABLE avatar_history
ADD COLUMN IF NOT EXISTS file_size BIGINT;
ALTER TABLE avatar_history
ADD COLUMN IF NOT EXISTS timestamp TIMESTAMPTZ;
-- Add snapshot_hash to avatars table
ALTER TABLE avatars
ADD COLUMN IF NOT EXISTS snapshot_hash BYTEA;