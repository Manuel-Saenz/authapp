import os

# Locally: written by setup_admin.py.
# In production: set ADMIN_USERNAME, ADMIN_PASSWORD_HASH, ADMIN_TOTP_SECRET as env vars.
ADMIN_USERNAME: str = os.environ.get("ADMIN_USERNAME", "manuelsaenz")
ADMIN_PASSWORD_HASH: str = os.environ.get("ADMIN_PASSWORD_HASH", "$2b$12$KzSHwTXXz3pR53bCwB0aBe2/5OB9.7Ak2hgy0szkkKCObaqB5viu6")
ADMIN_TOTP_SECRET: str = os.environ.get("ADMIN_TOTP_SECRET", "R7BZUYAQR3O5OHMVSJ3H726CIUGBGJXM")
