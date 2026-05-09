# Auth Service — User Manual

## Table of Contents

1. [Overview](#overview)
2. [Getting Started](#getting-started)
3. [Browser UI Guide](#browser-ui-guide)
   - [Step 1: Register](#step-1-register)
   - [Step 2: Scan the QR code](#step-2-scan-the-qr-code)
   - [Step 3: Confirm setup](#step-3-confirm-setup)
   - [Step 4: Log in](#step-4-log-in)
4. [API Guide](#api-guide)
   - [Register](#api-register)
   - [Confirm TOTP setup](#api-setup-confirm)
   - [Authenticate](#api-authenticate)
5. [API Reference](#api-reference)
6. [Error Messages](#error-messages)
7. [Security Rules](#security-rules)
8. [Troubleshooting](#troubleshooting)

---

## Overview

The Auth Service verifies a user's identity using three factors:

1. **Email address** — your unique identifier
2. **Password** — a secret only you know
3. **One-time code** — a 6-digit code generated every 30 seconds by Google Authenticator

All three must be correct for authentication to succeed.

The service offers two interfaces:

| Interface | URL | Best for |
|-----------|-----|----------|
| **Browser UI** | `http://localhost:8000/` | Human users — forms and QR code rendered in the browser |
| **JSON API** | `http://localhost:8000/docs` | Developers and programmatic access |

---

## Getting Started

### What you need

- The Auth Service running (see setup below)
- **Google Authenticator** on your phone:
  - [Android — Google Play](https://play.google.com/store/apps/details?id=com.google.android.apps.authenticator2)
  - [iPhone — App Store](https://apps.apple.com/app/google-authenticator/id388497605)

> Any TOTP-compatible app works — Authy, Microsoft Authenticator, 1Password, etc.

### Start the server

```bash
cd auth_app
python -m uvicorn main:app --reload
```

Then open `http://localhost:8000/` in your browser.

---

## Browser UI Guide

### Step 1: Register

1. Open `http://localhost:8000/` in your browser
2. Enter your email address and a password
3. Click **Register**

The service creates your account and immediately displays a QR code.

---

### Step 2: Scan the QR code

1. Open **Google Authenticator** on your phone
2. Tap **+** → **Scan a QR code**
3. Point your camera at the QR code shown on screen

Google Authenticator will start showing a 6-digit code that refreshes every 30 seconds.

**If you cannot scan the QR code**, enter the secret manually:

1. The QR code encodes a URI in this format:
   `otpauth://totp/AuthService:you%40example.com?secret=`**`YOURSECRET`**`&issuer=AuthService`
2. Open **Google Authenticator** → tap **+** → **Enter a setup key**
3. Account name: your email — Key: the secret — Type: Time-based
4. Tap **Add**

---

### Step 3: Confirm setup

After scanning, click **I've scanned it** on the QR page. You will be taken to the confirmation screen.

1. Enter the 6-digit code currently shown in Google Authenticator
2. Click **Confirm**

A success message confirms your account is ready.

---

### Step 4: Log in

1. Click **Go to login** or open `http://localhost:8000/ui/login`
2. Enter your email, password, and the current 6-digit code from Google Authenticator
3. Click **Log in**

A welcome message confirms successful authentication.

---

## API Guide

Use these endpoints programmatically or via `http://localhost:8000/docs` (Swagger UI).

### API: Register

```bash
curl -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{"email": "you@example.com", "password": "your-password"}'
```

**Response (201):**
```json
{
  "status": "ok",
  "totp_uri": "otpauth://totp/AuthService:you%40example.com?secret=XXXX&issuer=AuthService",
  "message": "Scan this URI with Google Authenticator, then call /setup-confirm"
}
```

Copy the `totp_uri`, generate a QR code from it (e.g. `python -c "import qrcode; qrcode.make('URI').save('qr.png')"`), and scan it with Google Authenticator.

---

### API: Confirm TOTP setup

```bash
curl -X POST http://localhost:8000/setup-confirm \
  -H "Content-Type: application/json" \
  -d '{"email": "you@example.com", "totp_code": "123456"}'
```

**Response (200):**
```json
{ "status": "ok" }
```

---

### API: Authenticate

```bash
curl -X POST http://localhost:8000/authenticate \
  -H "Content-Type: application/json" \
  -d '{"email": "you@example.com", "password": "your-password", "totp_code": "123456"}'
```

**Success:**
```json
{ "status": "ok" }
```

**Failure:**
```json
{ "status": "error", "message": "Invalid credentials or OTP code" }
```

---

## API Reference

### `GET /` — Register form
Returns the browser registration page.

### `POST /ui/register` — Browser registration
Accepts form fields `email` and `password`. Returns the QR code page on success.

### `GET /ui/confirm` — Confirm form
Query parameter: `email`. Returns the TOTP confirmation page.

### `POST /ui/confirm` — Browser confirm
Accepts form fields `email` and `totp_code`. Activates TOTP on success.

### `GET /ui/login` — Login form
Returns the browser login page.

### `POST /ui/login` — Browser login
Accepts form fields `email`, `password`, and `totp_code`. Returns welcome or error page.

---

### `POST /register`
Creates a new user. Returns JSON with the TOTP URI.

| Field | Type | Required |
|-------|------|----------|
| `email` | string | Yes |
| `password` | string | Yes |

| Code | Meaning |
|------|---------|
| `201` | Created — body contains `totp_uri` |
| `409` | Email already registered |
| `422` | Malformed request |

---

### `POST /setup-confirm`
Activates TOTP for the account.

| Field | Type | Required |
|-------|------|----------|
| `email` | string | Yes |
| `totp_code` | string | Yes |

| Code | Meaning |
|------|---------|
| `200` | TOTP confirmed |
| `400` | Invalid code, or already confirmed |
| `404` | Email not found |

---

### `POST /authenticate`
Validates all three factors. Always returns HTTP `200`.

| Field | Type | Required |
|-------|------|----------|
| `email` | string | Yes |
| `password` | string | Yes |
| `totp_code` | string | Yes |

| `status` | Meaning |
|----------|---------|
| `"ok"` | Authenticated |
| `"error"` | One or more factors wrong, or account locked |

---

## Error Messages

| Message | Meaning |
|---------|---------|
| `Invalid credentials or OTP code` | Email, password, or TOTP code is wrong. Intentionally vague. |
| `TOTP setup not completed` | Account registered but `/setup-confirm` not yet called. |
| `Too many failed attempts. Try again in 15 minutes.` | 5 failed attempts in the last 15 minutes. |
| `Email already registered` | Returned by `/register` only. |

---

## Security Rules

**Codes are single-use.**
Each 6-digit code works only once, even within the same 30-second window.

**Codes expire every 30 seconds.**
Always use the code currently shown in Google Authenticator.

**Clock skew tolerance.**
Codes from the window immediately before or after the current one are accepted, allowing for slight phone clock drift.

**Brute-force lock.**
5 consecutive failures lock the account for 15 minutes. A successful login resets the counter.

**Timing protection.**
The service takes the same time to respond whether or not the email exists, preventing user enumeration by measuring response times.

---

## Troubleshooting

**"Email not found" after just registering**

If your email contains a `+` character (e.g. `user+tag@example.com`), a URL encoding issue
may have corrupted it in the confirmation link. Navigate directly to:
```
http://localhost:8000/ui/confirm?email=user%2Btag@example.com
```
Replace `+` with `%2B` in the URL.

**"Invalid credentials or OTP code" even though everything looks right**

- Use the code currently shown in Google Authenticator — codes expire every 30 seconds
- You may have already used that code — wait for the next one
- Check your phone's date and time are set to **automatic / network time**
- Check for extra spaces in email or password

**"TOTP setup not completed"**

Call `/setup-confirm` (or use the browser confirm page) with a valid code to activate the account.

**Lost access to Google Authenticator**

No self-service recovery exists. An administrator must delete the user record from `auth_app.db`
so you can re-register with the same email.

**Google Authenticator shows a code but it is always rejected**

Your phone clock has drifted. Fix:
- Android: Settings → General Management → Date and Time → enable **Automatic date and time**
- iPhone: Settings → General → Date & Time → enable **Set Automatically**

**The service is not running**

```bash
cd auth_app
python -m uvicorn main:app --reload
```
