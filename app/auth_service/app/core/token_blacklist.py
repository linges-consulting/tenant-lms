"""
Token blacklist using Redis.

JWTs are stateless by nature, but we need to support logout (token revocation).
We store the JTI (JWT ID) in Redis with a TTL matching the token's remaining lifetime.
Any request carrying a blacklisted JTI is rejected with 401.
"""

from redis.asyncio import Redis


async def blacklist_token(jti: str, expires_in_seconds: int, redis_client: Redis) -> None:
    """Add token JTI to blacklist with TTL matching token expiry."""
    await redis_client.setex(f"blacklisted_token:{jti}", expires_in_seconds, "1")


async def is_token_blacklisted(jti: str, redis_client: Redis) -> bool:
    """Check if token JTI is in the blacklist."""
    result = await redis_client.get(f"blacklisted_token:{jti}")
    return result is not None
