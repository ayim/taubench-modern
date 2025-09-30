-- Update v2.check_user_access to recognize any subject ending with ':system_user'
-- regardless of the two middle segments (e.g., 'tenant:system:system_user' or 'tenant:user:system_user').

CREATE OR REPLACE FUNCTION v2.check_user_access(record_user_id UUID, requesting_user_id UUID)
RETURNS BOOLEAN AS $$
DECLARE
    record_sub TEXT;
    requesting_sub TEXT;
BEGIN
    SELECT sub INTO record_sub FROM v2.user WHERE user_id = record_user_id;
    SELECT sub INTO requesting_sub FROM v2.user WHERE user_id = requesting_user_id;

    IF record_sub IS NULL OR requesting_sub IS NULL THEN
        RETURN FALSE;
    END IF;

    RETURN
        -- Grant if record_user's sub is a prefix of requesting_user's sub
        requesting_sub LIKE record_sub || '%'
        -- OR if record_user's sub is a system user (any two middle segments)
        OR record_sub LIKE 'tenant:%:%:system_user'
        -- OR if requesting_user's sub is a system user (any two middle segments)
        OR requesting_sub LIKE 'tenant:%:%:system_user';
END;
$$ LANGUAGE plpgsql;


