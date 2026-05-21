"""
Account-level login lockout using Redis.

Thresholds (all configurable via env):
  - After LOGIN_MAX_ATTEMPTS (default 5) failures: temp lock for LOGIN_LOCKOUT_MINUTES (default 15)
  - After LOGIN_FORCE_RESET_ATTEMPTS (default 10) failures: force password reset

Note: The Redis client is configured with decode_responses=False, so all values
returned from Redis are bytes and must be decoded before use.
"""

ATTEMPT_KEY = "login_attempts:{email}"
LOCKOUT_KEY = "login_locked:{email}"
FORCE_RESET_KEY = "login_force_reset:{email}"


async def record_failed_attempt(
    email: str,
    redis,
    max_attempts: int = 5,
    lockout_minutes: int = 15,
    force_reset_threshold: int = 10,
) -> dict:
    """
    Increment failed attempt counter. Returns lockout state dict:
    {
        "attempts": int,
        "locked": bool,
        "force_reset": bool,
        "lockout_seconds_remaining": int | None,
    }
    """
    key = ATTEMPT_KEY.format(email=email.lower())

    # Increment counter, set expiry on first attempt (24h rolling window)
    attempts = await redis.incr(key)
    if attempts == 1:
        await redis.expire(key, 60 * 60 * 24)  # 24h window

    state = {
        "attempts": attempts,
        "locked": False,
        "force_reset": False,
        "lockout_seconds_remaining": None,
    }

    if attempts >= force_reset_threshold:
        # Force password reset — mark permanently until reset
        await redis.set(FORCE_RESET_KEY.format(email=email.lower()), "1")
        state["force_reset"] = True
    elif attempts >= max_attempts:
        # Temporary lockout
        lockout_secs = lockout_minutes * 60
        await redis.setex(LOCKOUT_KEY.format(email=email.lower()), lockout_secs, "1")
        state["locked"] = True
        state["lockout_seconds_remaining"] = lockout_secs

    return state


async def check_lockout(email: str, redis) -> dict:
    """
    Check lockout state before attempting login.
    Returns same dict shape as record_failed_attempt.
    """
    email_lower = email.lower()
    state = {
        "attempts": 0,
        "locked": False,
        "force_reset": False,
        "lockout_seconds_remaining": None,
    }

    # Check force-reset flag first
    force_reset_val = await redis.get(FORCE_RESET_KEY.format(email=email_lower))
    if force_reset_val is not None:
        state["force_reset"] = True
        return state

    # Check temporary lockout (TTL > 0 means key exists and has remaining time)
    lockout_ttl = await redis.ttl(LOCKOUT_KEY.format(email=email_lower))
    if lockout_ttl > 0:
        state["locked"] = True
        state["lockout_seconds_remaining"] = lockout_ttl
        return state

    # Return current attempt count (bytes → int)
    attempts_val = await redis.get(ATTEMPT_KEY.format(email=email_lower))
    state["attempts"] = int(attempts_val) if attempts_val is not None else 0
    return state


async def clear_lockout(email: str, redis) -> None:
    """Clear all lockout state after successful login or password reset."""
    email_lower = email.lower()
    await redis.delete(
        ATTEMPT_KEY.format(email=email_lower),
        LOCKOUT_KEY.format(email=email_lower),
        FORCE_RESET_KEY.format(email=email_lower),
    )
