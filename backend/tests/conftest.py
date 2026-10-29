import os


# Keep unit tests independent from production credentials while allowing settings
# to require a JWT secret at runtime.
os.environ.setdefault("JWT_SECRET_KEY", "unit-test-only-jwt-secret-with-32-plus-bytes")
