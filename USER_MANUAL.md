# Auth Service — User Manual

## Table of Contents

1. [Overview](#overview)
2. [Getting Started](#getting-started)
3. [Browser UI Guide](#browser-ui-guide)
   - [Step 1: Register](#step-1-register)
   - [Step 2: Verify your email](#step-2-verify-your-email)
   - [Step 3: Scan the QR code](#step-3-scan-the-qr-code)
   - [Step 4: Confirm setup](#step-4-confirm-setup)
   - [Step 5: Log in](#step-5-log-in)
4. [API Guide](#api-guide)
   - [Register](#api-register)
   - [Confirm TOTP setup](#api-setup-confirm)
   - [Authenticate](#api-authenticate)
5. [API Reference](#api-reference)
6. [SMTP Configuration](#smtp-configuration)
7. [Error Messages](#error-messages)
8. [Security Rules](#security-rules)
9. [Troubleshooting](#troubleshooting)

---

## Overview

The Auth Service verifies a user's identity using three factors:

1. **Email address** — your unique identifier, verified during registration
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
2. Enter your email address
3. Enter a password — click the **eye icon** on the right of the field to show or hide what you are typing
4. Enter the same password again in the **Confirm password** field to make sure it is correct
5. Click **Register**

If the passwords do not match, the form will alert you before submitting. The service then sends a verification email to the address you provided.

---

### Step 2: Verify your email

Check your inbox for an email with the subject **"Verify your email — AuthService"**. Click the link inside.

The link is valid for **30 minutes**. If it expires, go back to the registration page and register again.

> **Local development:** If SMTP is not configured, the verification link is shown directly on the page after clicking Register. Click it there.

---

### Step 3: Scan the QR code

After clicking the verification link your browser shows a QR code.

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

### Step 4: Confirm setup

After scanning, click **I've scanned it** on the QR page. You will be taken to the confirmation screen.

1. Enter the 6-digit code currently shown in Google Authenticator
2. Click **Confirm**

A success message confirms your account is ready.

---

### Step 5: Log in

1. Click **Go to login** or open `http://localhost:8000/ui/login`
2. Enter your email
3. Enter your password — use the **eye icon** to check what you typed
4. Enter the current 6-digit code from Google Authenticator
5. Click **Log in**

A welcome message confirms successful authentication.

---

## API Guide

Use these endpoints programmatically or via `http://localhost:8000/docs` (Swagger UI).

> **Note:** The JSON API does **not** require email verification — it returns the TOTP URI directly. Email verification applies only to the browser UI flow.

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
Accepts form fields `email`, `password`, `password2`. Sends a verification email on success.

### `GET /ui/verify` — Email verification
Query parameter: `token`. Completes account creation and shows the QR code.

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
Creates a new user. Returns JSON with the TOTP URI. No email verification step.

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

## SMTP Configuration

Email verification requires an SMTP server. Set these environment variables:

| Variable | Example | Description |
|----------|---------|-------------|
| `SMTP_HOST` | `smtp.gmail.com` | SMTP server hostname |
| `SMTP_PORT` | `587` | SMTP port (587 = STARTTLS) |
| `SMTP_USER` | `you@gmail.com` | Login username |
| `SMTP_PASSWORD` | `abcd efgh ijkl mnop` | Login password (Gmail: use an App Password) |
| `SMTP_FROM` | `you@gmail.com` | Sender address (defaults to `SMTP_USER`) |

### Using Gmail

1. In your Google Account go to **Security → 2-Step Verification → App passwords**
2. Create a new app password (select "Mail" / "Other")
3. Copy the 16-character password and set it as `SMTP_PASSWORD`
4. Set `SMTP_HOST=smtp.gmail.com` and `SMTP_PORT=587`

### Local development without SMTP

If `SMTP_HOST` and `SMTP_USER` are not set, the verification link is shown directly on the page after registration. No email is sent. This is intentional for local testing.

---

## Error Messages

| Message | Meaning |
|---------|---------|
| `Invalid credentials or OTP code` | Email, password, or TOTP code is wrong. Intentionally vague. |
| `TOTP setup not completed` | Account registered but confirm step not yet done. |
| `Too many failed attempts. Try again in 15 minutes.` | 5 failed attempts in the last 15 minutes. |
| `Email already registered` | Returned by `/register` (API) only. |
| `Passwords do not match` | Both password fields must be identical. |
| `This verification link has expired or has already been used` | Links are valid for 30 minutes and single-use. |
| `Could not send the verification email` | SMTP is configured but the send failed — check SMTP settings. |

---

## Security Rules

**Email must be verified.**
Account creation in the browser UI is not complete until the user clicks the verification link sent to their email address.

**Verification links are single-use and expire.**
Each link works exactly once and expires after 30 minutes.

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

**"Passwords do not match" alert on the registration form**

Both password fields must contain exactly the same text. Use the eye icon on either field to reveal what you typed and check for typos.

**Verification email never arrives**

- Check your spam/junk folder
- The link expires in 30 minutes — if you waited too long, register again
- Ask the administrator to confirm that SMTP is correctly configured

**"This verification link has expired or has already been used"**

Links are valid for 30 minutes and can only be clicked once. Go back to the registration page and register again to get a new link.

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

An administrator can reset your credentials from the admin panel. After a reset, you can register again with the same email address to set up a new TOTP entry.

**Google Authenticator shows a code but it is always rejected**

Your phone clock has drifted. Fix:
- Android: Settings → General Management → Date and Time → enable **Automatic date and time**
- iPhone: Settings → General → Date & Time → enable **Set Automatically**

**The service is not running**

```bash
cd auth_app
python -m uvicorn main:app --reload
```
