from slowapi import Limiter
from slowapi.util import get_remote_address

# Shared rate limiter instance for the auth service.
# Registered on app.state in main.py; imported by endpoints for @limiter.limit decorators.
limiter = Limiter(key_func=get_remote_address)
