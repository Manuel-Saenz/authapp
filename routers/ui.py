import base64
from urllib.parse import quote

import email_verify
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

import rate_limit
import security
from database import get_db
from models import User

router = APIRouter()

_EYE = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24"'
    ' fill="none" stroke="currentColor" stroke-width="2"'
    ' stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>'
    '<circle cx="12" cy="12" r="3"/></svg>'
)

_STYLE = """<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  html, body { height: 100%; }
  body {
    font-family: system-ui, sans-serif;
    background: #07071a;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    overflow-x: hidden;
    padding: 60px 0 40px;
  }
  /* ── Aurora blobs ── */
  .blob { position: fixed; border-radius: 50%; filter: blur(90px); pointer-events: none; z-index: 0; opacity: 0.72; }
  .blob-1 { width: 560px; height: 560px; background: radial-gradient(circle, rgba(124,58,237,0.85), transparent 70%); top: -180px; left: -140px; animation: drift1 13s ease-in-out infinite alternate; }
  .blob-2 { width: 480px; height: 480px; background: radial-gradient(circle, rgba(6,182,212,0.75), transparent 70%); bottom: -120px; right: -120px; animation: drift2 16s ease-in-out infinite alternate; }
  .blob-3 { width: 360px; height: 360px; background: radial-gradient(circle, rgba(16,185,129,0.5), transparent 70%); top: 55%; left: 35%; animation: drift3 19s ease-in-out infinite alternate; }
  @keyframes drift1 { from { transform: translate(0,0) scale(1); } to { transform: translate(60px,40px) scale(1.12); } }
  @keyframes drift2 { from { transform: translate(0,0) scale(1); } to { transform: translate(-50px,-35px) scale(1.08); } }
  @keyframes drift3 { from { transform: translate(0,0) scale(1); } to { transform: translate(45px,-55px) scale(0.9); } }
  /* ── Card ── */
  .card {
    position: relative; z-index: 1;
    background: rgba(255,255,255,0.94);
    backdrop-filter: blur(28px); -webkit-backdrop-filter: blur(28px);
    border: 1px solid rgba(255,255,255,0.45);
    border-radius: 22px;
    padding: 40px;
    width: 100%; max-width: 440px;
    margin: 0 24px;
    box-shadow: 0 8px 48px rgba(0,0,0,0.45), inset 0 1px 0 rgba(255,255,255,0.15);
  }
  /* ── Typography ── */
  h1 { font-size: 1.5rem; font-weight: 800; letter-spacing: -0.02em; color: #111; margin-bottom: 6px; }
  .sub { color: #666; font-size: 0.9rem; margin-bottom: 20px; }
  /* ── Form ── */
  label { display: block; font-size: 0.82rem; font-weight: 600; margin: 16px 0 4px; color: #333; }
  input { width: 100%; padding: 10px 12px; border: 1px solid #d1d5db; border-radius: 8px; font-size: 1rem; outline: none; background: #fff; }
  input:focus { border-color: #7c3aed; box-shadow: 0 0 0 3px rgba(124,58,237,0.12); }
  input[readonly] { background: #f5f5f5; color: #666; }
  /* ── Buttons ── */
  .btn {
    display: block; margin-top: 24px; width: 100%; padding: 12px;
    background: linear-gradient(135deg, #7c3aed 0%, #2563eb 100%);
    color: #fff; border: none; border-radius: 9px; font-size: 1rem;
    font-weight: 600; cursor: pointer; text-align: center; text-decoration: none; letter-spacing: 0.01em;
  }
  .btn:hover { opacity: 0.87; }
  .hint { margin-top: 18px; text-align: center; font-size: 0.85rem; color: #666; }
  .hint a { color: #7c3aed; font-weight: 600; }
  /* ── Alert boxes ── */
  .box-error { background: #fef2f2; border: 1px solid #fca5a5; color: #b91c1c; padding: 12px 14px; border-radius: 8px; margin-bottom: 20px; font-size: 0.9rem; }
  .box-ok    { background: #f0fdf4; border: 1px solid #86efac; color: #15803d; padding: 12px 14px; border-radius: 8px; margin-bottom: 20px; font-size: 0.9rem; }
  .box-info  { background: #eff6ff; border: 1px solid #93c5fd; color: #1d4ed8; padding: 12px 14px; border-radius: 8px; margin-bottom: 20px; font-size: 0.9rem; }
  /* ── QR ── */
  img.qr { display: block; margin: 20px auto; border: 1px solid #e5e7eb; border-radius: 10px; }
  /* ── Password show/hide ── */
  .pw-wrap { position: relative; display: block; }
  .pw-wrap input { padding-right: 44px; }
  .pw-toggle { position: absolute; right: 10px; top: 50%; transform: translateY(-50%); background: none; border: none; cursor: pointer; color: #888; padding: 4px; line-height: 0; border-radius: 4px; }
  .pw-toggle:hover { color: #7c3aed; }
  /* ── Login box (register page) ── */
  .login-box { margin-top: 18px; padding: 14px 18px; background: rgba(124,58,237,0.06); border: 1px solid rgba(124,58,237,0.2); border-radius: 12px; display: flex; align-items: center; justify-content: space-between; gap: 12px; }
  .login-box p { font-size: 0.875rem; color: #555; }
  .btn-login { flex-shrink: 0; padding: 8px 20px; background: #fff; border: 1.5px solid #7c3aed; color: #7c3aed; border-radius: 7px; font-size: 0.875rem; font-weight: 600; text-decoration: none; white-space: nowrap; }
  .btn-login:hover { background: #7c3aed; color: #fff; }
  /* ── Footer ── */
  .footer { position: fixed; bottom: 14px; left: 0; right: 0; text-align: center; color: rgba(255,255,255,0.3); font-size: 0.73rem; z-index: 1; letter-spacing: 0.02em; }
  .footer a { color: rgba(255,255,255,0.48); text-decoration: none; }
  .footer a:hover { color: rgba(255,255,255,0.85); }
  /* ── Responsive ── */
  @media (max-width: 480px) { .card { padding: 28px 20px; margin: 0 16px; } body { padding: 48px 0 36px; } }
</style>"""

_PW_SCRIPT = """
const _eOpen = `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>`;
const _eOff = `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>`;
function togglePw(btn) {
  const inp = btn.previousElementSibling;
  const visible = inp.type === 'text';
  inp.type = visible ? 'password' : 'text';
  btn.innerHTML = visible ? _eOpen : _eOff;
}
function checkPw(form) {
  if (form.password2 && form.password.value !== form.password2.value) {
    alert('Passwords do not match. Please try again.');
    return false;
  }
  return true;
}
"""

_FOOTER = (
    "<div class='footer'>Built by "
    "<strong style='color:rgba(255,255,255,0.5)'>Manuel Saenz</strong>"
    " &nbsp;&middot;&nbsp; Assisted by "
    "<a href='https://claude.ai/code'>Claude Code</a></div>"
)

_BLOBS = (
    "<div class='blob blob-1'></div>"
    "<div class='blob blob-2'></div>"
    "<div class='blob blob-3'></div>"
)


def _page(title: str, body: str) -> str:
    return (
        "<!DOCTYPE html><html lang='en'><head>"
        "<meta charset='UTF-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>{title} — AuthService</title>"
        f"{_STYLE}"
        f"</head><body>"
        f"{_BLOBS}"
        f"<div class='card'>{body}</div>"
        f"{_FOOTER}"
        f"<script>{_PW_SCRIPT}</script>"
        "</body></html>"
    )


def _pw_field(fid: str, fname: str, label: str, autofocus: bool = False) -> str:
    af = " autofocus" if autofocus else ""
    return (
        f'<label for="{fid}">{label}</label>'
        '<div class="pw-wrap">'
        f'<input id="{fid}" type="password" name="{fname}" required{af}>'
        f'<button type="button" class="pw-toggle" onclick="togglePw(this)" aria-label="Show/hide">{_EYE}</button>'
        '</div>'
    )


# ── GET / — register form ─────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
def register_form():
    body = (
        "<h1>Create account</h1>"
        "<p class='sub'>Register with your email and a password.</p>"
        "<form method='POST' action='/ui/register' onsubmit='return checkPw(this)'>"
        "<label for='email'>Email</label>"
        "<input id='email' type='email' name='email' required autofocus>"
        + _pw_field("password", "password", "Password")
        + _pw_field("password2", "password2", "Confirm password")
        + "<button class='btn' type='submit'>Create account &rarr;</button>"
        "</form>"
        "<div class='login-box'>"
        "<p>Already have an account?</p>"
        "<a class='btn-login' href='/ui/login'>Log in &rarr;</a>"
        "</div>"
    )
    return _page("Create account", body)


# ── POST /ui/register — validate, store pending, send verification email ──────

@router.post("/ui/register", response_class=HTMLResponse)
def ui_register(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    password2: str = Form(...),
    db: Session = Depends(get_db),
):
    email = email.lower()

    if password != password2:
        body = (
            "<div class='box-error'>Passwords do not match.</div>"
            "<a class='btn' href='/'>← Back</a>"
        )
        return HTMLResponse(_page("Password mismatch", body), status_code=400)

    existing = db.query(User).filter(User.email == email).first()
    if existing and existing.password_hash is not None:
        body = (
            "<div class='box-error'>That email is already registered.</div>"
            "<a class='btn' href='/'>← Back</a>"
        )
        return HTMLResponse(_page("Already registered", body), status_code=409)

    secret = security.generate_totp_secret()
    password_hash = security.hash_password(password)

    token = email_verify.create_pending(email, password_hash, secret)
    base_url = str(request.base_url).rstrip("/")
    verify_url = f"{base_url}/ui/verify?token={token}"

    try:
        email_verify.send_verification_email(email, verify_url)
    except Exception as exc:
        print(f"[ui/register] Email send failed: {exc}")
        body = (
            "<div class='box-error'>Could not send the verification email. "
            "Please check your SMTP settings or try again later.</div>"
            "<a class='btn' href='/'>← Back</a>"
        )
        return HTMLResponse(_page("Email error", body), status_code=500)

    dev_hint = ""
    if not email_verify.smtp_configured():
        dev_hint = (
            f"<div class='box-info'><strong>Dev mode</strong> — SMTP not configured.<br>"
            f"<a href='{verify_url}'>Click here to verify your email</a></div>"
        )

    body = (
        "<h1>Check your email</h1>"
        f"<p class='sub'>We sent a verification link to <strong>{email}</strong>.</p>"
        "<p class='sub'>Click the link in the email to complete registration "
        "and set up Google Authenticator. The link expires in 30 minutes.</p>"
        + dev_hint
    )
    return HTMLResponse(_page("Check your email", body), status_code=202)


# ── GET /ui/verify — consume token, create user, show QR ─────────────────────

@router.get("/ui/verify", response_class=HTMLResponse)
def ui_verify(token: str = "", db: Session = Depends(get_db)):
    if not token:
        body = (
            "<div class='box-error'>Missing verification token.</div>"
            "<a class='btn' href='/'>← Back</a>"
        )
        return HTMLResponse(_page("Invalid link", body), status_code=400)

    entry = email_verify.consume_pending(token)
    if entry is None:
        body = (
            "<div class='box-error'>This verification link has expired or has already been used. "
            "Please register again.</div>"
            "<a class='btn' href='/'>Register again</a>"
        )
        return HTMLResponse(_page("Link expired", body), status_code=400)

    email = entry["email"]
    password_hash = entry["password_hash"]
    totp_secret = entry["totp_secret"]

    existing = db.query(User).filter(User.email == email).first()
    if existing:
        if existing.password_hash is not None:
            body = (
                "<div class='box-error'>That email is already registered.</div>"
                "<a class='btn' href='/ui/login'>Go to login</a>"
            )
            return HTMLResponse(_page("Already registered", body), status_code=409)
        existing.password_hash = password_hash
        existing.totp_secret = totp_secret
        existing.totp_confirmed = False
        db.commit()
    else:
        user = User(
            email=email,
            password_hash=password_hash,
            totp_secret=totp_secret,
            totp_confirmed=False,
        )
        db.add(user)
        db.commit()

    totp_uri = security.build_totp_uri(totp_secret, email)
    qr_b64 = base64.b64encode(security.generate_qr_png(totp_uri)).decode()

    body = (
        "<h1>Scan this QR code</h1>"
        f"<p class='sub'>Email verified for <strong>{email}</strong>.</p>"
        "<p class='sub'>Open <strong>Google Authenticator</strong>, tap <strong>+</strong>"
        " &rarr; <strong>Scan a QR code</strong>, then point your camera below.</p>"
        f'<img class="qr" src="data:image/png;base64,{qr_b64}" width="240" height="240" alt="TOTP QR code">'
        "<p class='sub'>Once you see a 6-digit code in the app, click the button to finish setup.</p>"
        f'<a class="btn" href="/ui/confirm?email={quote(email)}">I\'ve scanned it &rarr;</a>'
    )
    return HTMLResponse(_page("Scan QR code", body))


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

    body = (
        "<div class='box-ok'>Setup complete!</div>"
        "<h1>You're all set</h1>"
        f"<p class='sub'>Google Authenticator is linked to <strong>{email}</strong>. "
        "You can now log in with your email, password, and the code from the app.</p>"
        "<a class='btn' href='/ui/login'>Go to login &rarr;</a>"
    )
    return _page("Setup complete", body)


# ── GET /ui/login — login form ───────────────────────────────────────────────

@router.get("/ui/login", response_class=HTMLResponse)
def login_form():
    body = (
        "<h1>Log in</h1>"
        "<p class='sub'>Enter your email, password, and the current code from Google Authenticator.</p>"
        "<form method='POST' action='/ui/login'>"
        "<label for='email'>Email</label>"
        "<input id='email' type='email' name='email' required autofocus>"
        + _pw_field("password", "password", "Password")
        + "<label for='code'>6-digit code</label>"
        "<input id='code' type='text' name='totp_code' inputmode='numeric'"
        " maxlength='6' pattern='[0-9]{6}' autocomplete='one-time-code' required>"
        "<button class='btn' type='submit'>Log in</button>"
        "</form>"
        "<p class='hint'>No account yet? <a href='/'>Register</a></p>"
    )
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

    body = (
        "<div class='box-ok'>Authentication successful!</div>"
        "<h1>Welcome</h1>"
        f"<p class='sub'>You are logged in as <strong>{email}</strong>.</p>"
        "<a class='btn' href='/ui/login'>Log in again</a>"
    )
    return _page("Welcome", body)
