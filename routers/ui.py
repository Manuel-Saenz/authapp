import base64
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

import rate_limit
import security
from database import get_db
from models import User

router = APIRouter()

_STYLE = """<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: system-ui, sans-serif; max-width: 440px; margin: 72px auto; padding: 0 24px; color: #111; }
  h1 { font-size: 1.5rem; font-weight: 700; margin-bottom: 6px; }
  .sub { color: #666; margin-bottom: 28px; font-size: 0.95rem; }
  label { display: block; font-size: 0.85rem; font-weight: 600; margin: 18px 0 5px; }
  input { width: 100%; padding: 10px 12px; border: 1px solid #d1d5db; border-radius: 7px; font-size: 1rem; outline: none; }
  input:focus { border-color: #111; }
  input[readonly] { background: #f5f5f5; color: #666; }
  .btn { display: block; margin-top: 26px; width: 100%; padding: 12px; background: #111;
         color: #fff; border: none; border-radius: 7px; font-size: 1rem; cursor: pointer;
         text-align: center; text-decoration: none; }
  .btn:hover { background: #333; }
  .hint { margin-top: 18px; text-align: center; font-size: 0.85rem; color: #666; }
  .hint a { color: #111; font-weight: 500; }
  .box-error { background: #fef2f2; border: 1px solid #fca5a5; color: #b91c1c;
               padding: 12px 14px; border-radius: 7px; margin-bottom: 20px; font-size: 0.9rem; }
  .box-ok    { background: #f0fdf4; border: 1px solid #86efac; color: #15803d;
               padding: 12px 14px; border-radius: 7px; margin-bottom: 20px; font-size: 0.9rem; }
  img.qr { display: block; margin: 24px auto; border: 1px solid #e5e7eb; border-radius: 10px; }
</style>"""


def _page(title: str, body: str) -> str:
    return (
        "<!DOCTYPE html><html lang='en'><head>"
        "<meta charset='UTF-8'>"
        f"<title>{title} — AuthService</title>"
        f"{_STYLE}"
        f"</head><body>{body}</body></html>"
    )


# ── GET / — register form ─────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
def register_form():
    body = """
    <h1>Create account</h1>
    <p class="sub">Register with your email and a password.</p>
    <form method="POST" action="/ui/register">
      <label for="email">Email</label>
      <input id="email" type="email" name="email" required autofocus>
      <label for="password">Password</label>
      <input id="password" type="password" name="password" required>
      <button class="btn" type="submit">Register</button>
    </form>
    <p class="hint">Already have an account? <a href="/ui/login">Log in</a></p>
    """
    return _page("Create account", body)


# ── POST /ui/register — create user, show QR ─────────────────────────────────

@router.post("/ui/register", response_class=HTMLResponse)
def ui_register(
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    email = email.lower()

    secret = security.generate_totp_secret()
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        if existing.password_hash is not None:
            body = (
                "<div class='box-error'>That email is already registered.</div>"
                "<a class='btn' href='/'>← Back</a>"
            )
            return HTMLResponse(_page("Already registered", body), status_code=409)
        existing.password_hash = security.hash_password(password)
        existing.totp_secret = secret
        existing.totp_confirmed = False
        db.commit()
    else:
        user = User(
            email=email,
            password_hash=security.hash_password(password),
            totp_secret=secret,
            totp_confirmed=False,
        )
        db.add(user)
        db.commit()

    totp_uri = security.build_totp_uri(secret, email)
    qr_b64 = base64.b64encode(security.generate_qr_png(totp_uri)).decode()

    body = f"""
    <h1>Scan this QR code</h1>
    <p class="sub">Account created for <strong>{email}</strong>.</p>
    <p class="sub">Open <strong>Google Authenticator</strong>, tap <strong>+</strong>
       &rarr; <strong>Scan a QR code</strong>, then point your camera below.</p>
    <img class="qr" src="data:image/png;base64,{qr_b64}" width="240" height="240" alt="TOTP QR code">
    <p class="sub">Once you see a 6-digit code in the app, click the button to finish setup.</p>
    <a class="btn" href="/ui/confirm?email={quote(email)}">I've scanned it &rarr;</a>
    """
    return HTMLResponse(_page("Scan QR code", body), status_code=201)


# ── GET /ui/confirm — confirm form ───────────────────────────────────────────

@router.get("/ui/confirm", response_class=HTMLResponse)
def confirm_form(email: str = ""):
    readonly = "readonly" if email else ""
    body = f"""
    <h1>Confirm setup</h1>
    <p class="sub">Enter the 6-digit code currently shown in Google Authenticator.</p>
    <form method="POST" action="/ui/confirm">
      <label for="email">Email</label>
      <input id="email" type="email" name="email" value="{email}" {readonly} required>
      <label for="code">6-digit code</label>
      <input id="code" type="text" name="totp_code" inputmode="numeric"
             maxlength="6" pattern="[0-9]{{6}}" autocomplete="one-time-code" required autofocus>
      <button class="btn" type="submit">Confirm</button>
    </form>
    """
    return _page("Confirm setup", body)


# ── POST /ui/confirm — verify first TOTP code ────────────────────────────────

@router.post("/ui/confirm", response_class=HTMLResponse)
def ui_confirm(
    email: str = Form(...),
    totp_code: str = Form(...),
    db: Session = Depends(get_db),
):
    email = email.lower()
    user = db.query(User).filter(User.email == email).first()

    if not user:
        body = "<div class='box-error'>Email not found.</div><a class='btn' href='/'>← Back</a>"
        return HTMLResponse(_page("Not found", body), status_code=404)

    if user.totp_confirmed:
        body = (
            "<div class='box-error'>TOTP is already confirmed for this account.</div>"
            "<a class='btn' href='/ui/login'>Go to login</a>"
        )
        return HTMLResponse(_page("Already confirmed", body), status_code=400)

    if user.totp_secret is None or not security.verify_totp(user.totp_secret, totp_code):
        body = (
            "<div class='box-error'>That code is not valid — wait for the next one and try again.</div>"
            f"<a class='btn' href='/ui/confirm?email={quote(email)}'>← Try again</a>"
        )
        return HTMLResponse(_page("Invalid code", body), status_code=400)

    user.totp_confirmed = True
    db.commit()

    body = f"""
    <div class="box-ok">Setup complete!</div>
    <h1>You're all set</h1>
    <p class="sub">Google Authenticator is linked to <strong>{email}</strong>.
       You can now log in with your email, password, and the code from the app.</p>
    <a class="btn" href="/ui/login">Go to login &rarr;</a>
    """
    return _page("Setup complete", body)


# ── GET /ui/login — login form ───────────────────────────────────────────────

@router.get("/ui/login", response_class=HTMLResponse)
def login_form():
    body = """
    <h1>Log in</h1>
    <p class="sub">Enter your email, password, and the current code from Google Authenticator.</p>
    <form method="POST" action="/ui/login">
      <label for="email">Email</label>
      <input id="email" type="email" name="email" required autofocus>
      <label for="password">Password</label>
      <input id="password" type="password" name="password" required>
      <label for="code">6-digit code</label>
      <input id="code" type="text" name="totp_code" inputmode="numeric"
             maxlength="6" pattern="[0-9]{6}" autocomplete="one-time-code" required>
      <button class="btn" type="submit">Log in</button>
    </form>
    <p class="hint">No account yet? <a href="/">Register</a></p>
    """
    return _page("Log in", body)


# ── POST /ui/login — authenticate ────────────────────────────────────────────

@router.post("/ui/login", response_class=HTMLResponse)
def ui_login(
    email: str = Form(...),
    password: str = Form(...),
    totp_code: str = Form(...),
    db: Session = Depends(get_db),
):
    email = email.lower()

    if rate_limit.is_rate_limited(email):
        body = (
            "<div class='box-error'>Too many failed attempts. Try again in 15 minutes.</div>"
            "<a class='btn' href='/ui/login'>← Back</a>"
        )
        return HTMLResponse(_page("Locked", body))

    user = db.query(User).filter(User.email == email).first()

    _fail_body = (
        "<div class='box-error'>Invalid email, password, or code.</div>"
        "<a class='btn' href='/ui/login'>← Try again</a>"
    )

    if not user:
        security.dummy_verify()
        rate_limit.record_attempt(email)
        return HTMLResponse(_page("Login failed", _fail_body))

    if user.password_hash is None or not security.verify_password(password, user.password_hash):
        rate_limit.record_attempt(email)
        return HTMLResponse(_page("Login failed", _fail_body))

    if not user.totp_confirmed:
        body = (
            "<div class='box-error'>TOTP setup not completed.</div>"
            f"<a class='btn' href='/ui/confirm?email={quote(email)}'>Complete setup</a>"
        )
        return HTMLResponse(_page("Setup required", body))

    if not security.verify_totp(user.totp_secret, totp_code):
        rate_limit.record_attempt(email)
        return HTMLResponse(_page("Login failed", _fail_body))

    if security.is_code_used(email, totp_code):
        rate_limit.record_attempt(email)
        body = (
            "<div class='box-error'>That code has already been used — wait for the next one.</div>"
            "<a class='btn' href='/ui/login'>← Try again</a>"
        )
        return HTMLResponse(_page("Login failed", body))

    security.mark_code_used(email, totp_code)
    rate_limit.clear_attempts(email)

    body = f"""
    <div class="box-ok">Authentication successful!</div>
    <h1>Welcome</h1>
    <p class="sub">You are logged in as <strong>{email}</strong>.</p>
    <a class="btn" href="/ui/login">Log in again</a>
    """
    return _page("Welcome", body)
