import csv
import io

from fastapi import APIRouter, Cookie, Depends, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from sqlalchemy.orm import Session

import admin_sessions
import config
import rate_limit
import security
from database import get_db
from models import User

router = APIRouter(prefix="/admin")

_STYLE = """<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: system-ui, sans-serif; color: #111; background: #fff; }
  nav { background: #111; color: #fff; padding: 12px 32px; display: flex; justify-content: space-between; align-items: center; }
  nav .logo { font-weight: 700; font-size: 0.95rem; letter-spacing: 0.02em; }
  nav a { color: #ccc; text-decoration: none; font-size: 0.85rem; }
  nav a:hover { color: #fff; }
  .content { max-width: 900px; margin: 40px auto; padding: 0 32px; }
  h1 { font-size: 1.4rem; font-weight: 700; margin-bottom: 20px; }
  .box-ok    { background: #f0fdf4; border: 1px solid #86efac; color: #15803d; padding: 12px 16px; border-radius: 7px; margin-bottom: 20px; font-size: 0.9rem; }
  .box-error { background: #fef2f2; border: 1px solid #fca5a5; color: #b91c1c; padding: 12px 16px; border-radius: 7px; margin-bottom: 20px; font-size: 0.9rem; }
  table { width: 100%; border-collapse: collapse; font-size: 0.875rem; }
  th { text-align: left; padding: 9px 14px; background: #f5f5f5; border-bottom: 2px solid #e4e4e4; font-weight: 600; color: #555; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.04em; }
  td { padding: 10px 14px; border-bottom: 1px solid #f0f0f0; vertical-align: middle; }
  tr:hover td { background: #fafafa; }
  .badge-yes { display: inline-block; background: #dcfce7; color: #15803d; font-size: 0.75rem; font-weight: 600; padding: 2px 8px; border-radius: 999px; }
  .badge-no  { display: inline-block; background: #fef9c3; color: #854d0e; font-size: 0.75rem; font-weight: 600; padding: 2px 8px; border-radius: 999px; }
  .actions { display: flex; gap: 6px; }
  .btn-sm { padding: 5px 12px; border: none; border-radius: 5px; font-size: 0.8rem; cursor: pointer; font-weight: 500; }
  .btn-danger { background: #fee2e2; color: #b91c1c; }
  .btn-danger:hover { background: #fecaca; }
  .btn-warn { background: #fef3c7; color: #92400e; }
  .btn-warn:hover { background: #fde68a; }
  .toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
  .export-link { font-size: 0.85rem; color: #555; text-decoration: none; border: 1px solid #e4e4e4; padding: 6px 14px; border-radius: 6px; }
  .export-link:hover { background: #f5f5f5; }
  .empty { color: #888; font-size: 0.9rem; padding: 32px 0; text-align: center; }
  .login-wrap { max-width: 420px; margin: 80px auto; padding: 0 24px; }
  .login-wrap h1 { font-size: 1.5rem; margin-bottom: 6px; }
  .sub { color: #666; margin-bottom: 28px; font-size: 0.9rem; }
  label { display: block; font-size: 0.85rem; font-weight: 600; margin: 16px 0 4px; }
  input { width: 100%; padding: 10px 12px; border: 1px solid #d1d5db; border-radius: 7px; font-size: 1rem; outline: none; }
  input:focus { border-color: #111; }
  .btn-primary { display: block; margin-top: 24px; width: 100%; padding: 12px; background: #111; color: #fff; border: none; border-radius: 7px; font-size: 1rem; cursor: pointer; }
  .btn-primary:hover { background: #333; }
  @media (max-width: 600px) {
    .content { padding: 0 16px; margin: 24px auto; }
    .login-wrap { margin: 40px auto; }
    nav { padding: 12px 16px; }
    .toolbar { flex-direction: column; align-items: flex-start; gap: 10px; }
    .table-wrap { overflow-x: auto; }
  }
</style>"""


def _page(title: str, body: str) -> str:
    return (
        "<!DOCTYPE html><html lang='en'><head>"
        "<meta charset='UTF-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>{title} — Admin</title>"
        f"{_STYLE}"
        f"</head><body>{body}</body></html>"
    )


def _nav(logout: bool = True) -> str:
    logout_link = "<a href='/admin/logout'>Log out</a>" if logout else ""
    return f"<nav><span class='logo'>Auth Service — Admin</span>{logout_link}</nav>"


# ── require_admin dependency ──────────────────────────────────────────────────

def require_admin(admin_session: str | None = Cookie(default=None)) -> str:
    if not admin_session or not admin_sessions.validate_session(admin_session):
        raise HTTPException(status_code=302, headers={"Location": "/admin/login"})
    return admin_session


# ── GET /admin/login ──────────────────────────────────────────────────────────

@router.get("/login", response_class=HTMLResponse)
def admin_login_form():
    body = f"""
    {_nav(logout=False)}
    <div class="login-wrap">
      <h1>Admin login</h1>
      <p class="sub">Enter your admin credentials and the current Google Authenticator code.</p>
      <form method="POST" action="/admin/login">
        <label>Username</label>
        <input type="text" name="username" required autofocus autocomplete="username">
        <label>Password</label>
        <input type="password" name="password" required autocomplete="current-password">
        <label>6-digit code</label>
        <input type="text" name="totp_code" inputmode="numeric" maxlength="6"
               pattern="[0-9]{{6}}" autocomplete="one-time-code" required>
        <button class="btn-primary" type="submit">Log in</button>
      </form>
    </div>
    """
    return _page("Admin login", body)


# ── POST /admin/login ─────────────────────────────────────────────────────────

@router.post("/login", response_class=HTMLResponse)
def admin_login(
    username: str = Form(...),
    password: str = Form(...),
    totp_code: str = Form(...),
):
    def _fail(msg: str) -> HTMLResponse:
        body = f"""
        {_nav(logout=False)}
        <div class="login-wrap">
          <h1>Admin login</h1>
          <div class="box-error">{msg}</div>
          <form method="POST" action="/admin/login">
            <label>Username</label>
            <input type="text" name="username" value="{username}" required autofocus autocomplete="username">
            <label>Password</label>
            <input type="password" name="password" required autocomplete="current-password">
            <label>6-digit code</label>
            <input type="text" name="totp_code" inputmode="numeric" maxlength="6"
                   pattern="[0-9]{{6}}" autocomplete="one-time-code" required>
            <button class="btn-primary" type="submit">Log in</button>
          </form>
        </div>
        """
        return HTMLResponse(_page("Admin login", body))

    if rate_limit.is_rate_limited(username):
        return _fail("Too many failed attempts. Try again in 15 minutes.")

    if username != config.ADMIN_USERNAME:
        security.dummy_verify()
        rate_limit.record_attempt(username)
        return _fail("Invalid username, password, or code.")

    if not security.verify_password(password, config.ADMIN_PASSWORD_HASH):
        rate_limit.record_attempt(username)
        return _fail("Invalid username, password, or code.")

    if not security.verify_totp(config.ADMIN_TOTP_SECRET, totp_code):
        rate_limit.record_attempt(username)
        return _fail("Invalid username, password, or code.")

    if security.is_code_used(username, totp_code):
        rate_limit.record_attempt(username)
        return _fail("That code has already been used — wait for the next one.")

    security.mark_code_used(username, totp_code)
    rate_limit.clear_attempts(username)

    token = admin_sessions.create_session()
    response = RedirectResponse("/admin/", status_code=303)
    response.set_cookie("admin_session", token, httponly=True, samesite="lax")
    return response


# ── GET /admin/ — dashboard ───────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
def admin_dashboard(
    deleted: str = Query(default=""),
    reset: str = Query(default=""),
    _session: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    users = db.query(User).order_by(User.created_at.desc()).all()

    flash = ""
    if deleted:
        flash = "<div class='box-ok'>User deleted successfully.</div>"
    elif reset:
        flash = "<div class='box-ok'>User credentials reset. They can now re-register with the same email.</div>"

    if users:
        rows = ""
        for u in users:
            confirmed = (
                "<span class='badge-yes'>Yes</span>" if u.totp_confirmed
                else "<span class='badge-no'>No</span>"
            )
            created = u.created_at.strftime("%Y-%m-%d %H:%M") if u.created_at else "—"
            email_js = u.email.replace("'", "\\'")
            rows += f"""
            <tr>
              <td>{u.email}</td>
              <td>{confirmed}</td>
              <td>{created}</td>
              <td>
                <div class="actions">
                  <form method="POST" action="/admin/users/reset"
                        onsubmit="return confirm('Reset credentials for {email_js}?')">
                    <input type="hidden" name="email" value="{u.email}">
                    <button class="btn-sm btn-warn" type="submit">Reset</button>
                  </form>
                  <form method="POST" action="/admin/users/delete"
                        onsubmit="return confirm('Permanently delete {email_js}?')">
                    <input type="hidden" name="email" value="{u.email}">
                    <button class="btn-sm btn-danger" type="submit">Delete</button>
                  </form>
                </div>
              </td>
            </tr>"""
        table = f"""
        <table>
          <thead>
            <tr>
              <th>Email</th><th>TOTP confirmed</th><th>Registered</th><th>Actions</th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>"""
    else:
        table = "<p class='empty'>No registered users.</p>"

    body = f"""
    {_nav()}
    <div class="content">
      <div class="toolbar">
        <h1>Users ({len(users)})</h1>
        <a class="export-link" href="/admin/users/export.csv">&#8595; Export CSV</a>
      </div>
      {flash}
      <div class="table-wrap">{table}</div>
    </div>
    """
    return _page("Admin — Users", body)


# ── GET /admin/users/export.csv ───────────────────────────────────────────────

@router.get("/users/export.csv")
def export_csv(
    _session: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    users = db.query(User).order_by(User.created_at).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["email", "totp_confirmed", "created_at"])
    for u in users:
        writer.writerow([u.email, u.totp_confirmed, u.created_at])
    csv_bytes = output.getvalue().encode()
    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=users.csv"},
    )


# ── POST /admin/users/delete ──────────────────────────────────────────────────

@router.post("/users/delete")
def admin_delete_user(
    email: str = Form(...),
    _session: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    db.query(User).filter(User.email == email.lower()).delete()
    db.commit()
    return RedirectResponse("/admin/?deleted=1", status_code=303)


# ── POST /admin/users/reset ───────────────────────────────────────────────────

@router.post("/users/reset")
def admin_reset_user(
    email: str = Form(...),
    _session: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == email.lower()).first()
    if user:
        user.password_hash = None
        user.totp_secret = None
        user.totp_confirmed = False
        db.commit()
    return RedirectResponse("/admin/?reset=1", status_code=303)


# ── GET /admin/logout ─────────────────────────────────────────────────────────

@router.get("/logout")
def admin_logout(admin_session: str | None = Cookie(default=None)):
    if admin_session:
        admin_sessions.delete_session(admin_session)
    response = RedirectResponse("/admin/login", status_code=303)
    response.delete_cookie("admin_session")
    return response
