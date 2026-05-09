"""
One-time admin setup script.
Run from the auth_app/ directory:

  python setup_admin.py             # generate credentials and write config.py
  python setup_admin.py --print-only  # print credentials for Railway env vars, skip writing config.py
"""
import getpass
import os
import sys

import security


def _prompt_username() -> str:
    while True:
        username = input("Admin username: ").strip()
        if username:
            return username
        print("Username cannot be empty.")


def _prompt_password() -> str:
    while True:
        pw1 = getpass.getpass("Admin password: ")
        pw2 = getpass.getpass("Confirm password: ")
        if not pw1:
            print("Password cannot be empty.")
        elif pw1 != pw2:
            print("Passwords do not match.")
        else:
            return pw1


def _write_config(username: str, password_hash: str, totp_secret: str) -> None:
    config_path = os.path.join(os.path.dirname(__file__), "config.py")
    content = (
        "# Written by setup_admin.py — do not edit by hand.\n"
        f"ADMIN_USERNAME: str = {repr(username)}\n"
        f"ADMIN_PASSWORD_HASH: str = {repr(password_hash)}\n"
        f"ADMIN_TOTP_SECRET: str = {repr(totp_secret)}\n"
    )
    with open(config_path, "w", encoding="utf-8") as f:
        f.write(content)


def main() -> None:
    print_only = "--print-only" in sys.argv
    print("=== Auth Service — Admin Setup ===\n")

    username = _prompt_username()
    password = _prompt_password()

    print("\nGenerating TOTP secret...")
    totp_secret = security.generate_totp_secret()
    password_hash = security.hash_password(password)

    totp_uri = security.build_totp_uri(totp_secret, username, issuer="AuthService-Admin")
    qr_bytes = security.generate_qr_png(totp_uri)

    if print_only:
        print("\n--- Copy these values into your Railway environment variables ---")
        print(f"ADMIN_USERNAME={username}")
        print(f"ADMIN_PASSWORD_HASH={password_hash}")
        print(f"ADMIN_TOTP_SECRET={totp_secret}")
        print("-----------------------------------------------------------------")
    else:
        qr_path = os.path.join(os.path.dirname(__file__), "admin_qr.png")
        with open(qr_path, "wb") as f:
            f.write(qr_bytes)
        _write_config(username, password_hash, totp_secret)
        print(f"\nQR code saved to: {qr_path}")
        print("Open admin_qr.png and scan it with Google Authenticator.")
        print("\nSetup complete. Restart the app to apply the new credentials.")

    print(f"\nScan this URI with Google Authenticator if needed:\n{totp_uri}")


if __name__ == "__main__":
    main()
