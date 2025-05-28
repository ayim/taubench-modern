import structlog

logger = structlog.get_logger(__name__)


def convert_user_to_v2_format(v1_user: dict) -> dict:
    """
    Convert a v1 user record to v2 format.

    Args:
        v1_user: Dictionary containing v1 user data

    Returns:
        Dictionary with v2 user format
    """

    def require(key: str) -> str:
        val = v1_user.get(key)
        if not val:
            raise Exception(f"Skipping user because it has no {key}")
        return val

    logger.info(f"Converting user: {v1_user}")

    user_id = require("user_id")
    sub = require("sub")
    created_at = v1_user.get("created_at")

    return {
        "user_id": user_id,
        "sub": sub,
        "created_at": created_at,
    }


async def migrate_users(storage):
    """
    Migrate users using the provided storage connection
    Args:
        storage: Connected storage interface
    """
    try:
        users = await storage.get_all_users()

        for v1_user in users:
            try:
                user_dict = convert_user_to_v2_format(v1_user)
            except Exception as e:
                logger.error(f"Error converting user: {e}")
                continue

            try:
                await storage.insert_user(user_dict)
                logger.info(f"Successfully migrated user: {v1_user['user_id']}")
            except Exception as e:
                logger.error(f"Error migrating user {v1_user['user_id']}: {e}")

    except Exception as e:
        logger.error(f"Error during users migration: {e}")
        raise

    logger.info("Users migration completed!")
