# Auth Service

Email + password + Google Authenticator (TOTP) authentication API built with FastAPI and SQLite.

## Setup

```bash
cd auth_app
pip install -r requirements.txt
uvicorn main:app --reload
```

The SQLite database (`auth_app.db`) is created automatically on first run.
Interactive API docs are available at `http://localhost:8000/docs`.

---

## Usage

### 1. Register a user

```bash
curl -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "yourpassword"}'
```

Response:
```json
{
  "status": "ok",
  "totp_uri": "otpauth://totp/AuthService:user%40example.com?secret=XXXX&issuer=AuthService",
  "message": "Scan this URI with Google Authenticator, then call /setup-confirm"
}
```

Open the `totp_uri` as a QR code (e.g. paste it at [qr.io](https://qr.io)) and scan it with
Google Authenticator. The app will start generating 6-digit codes every 30 seconds.

---

### 2. Confirm TOTP setup

```bash
curl -X POST http://localhost:8000/setup-confirm \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "totp_code": "123456"}'
```

Response:
```json
{ "status": "ok" }
```

---

### 3. Authenticate

```bash
curl -X POST http://localhost:8000/authenticate \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "yourpassword", "totp_code": "123456"}'
```

Success:
```json
{ "status": "ok" }
```

Failure (wrong password, wrong code, or rate-limited):
```json
{ "status": "error", "message": "Invalid credentials or OTP code" }
```

---

## Security features

| Feature | Detail |
|---------|--------|
| Password hashing | bcrypt via passlib |
| TOTP standard | RFC 6238, ±30 s clock skew tolerance |
| Replay prevention | Used codes cached for 90 s |
| Brute-force protection | Max 5 failed attempts per email per 15 minutes |
| Timing safety | bcrypt always runs, even for unknown emails |
| Error messages | Generic — no distinction between wrong email, wrong password, or wrong OTP |
