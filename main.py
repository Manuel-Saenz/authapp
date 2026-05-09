from fastapi import FastAPI

from database import Base, engine
from routers.admin import router as admin_router
from routers.auth import router as auth_router
from routers.ui import router as ui_router

# Create all tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Auth Service", description="Email + password + TOTP authentication API")
app.include_router(ui_router)
app.include_router(auth_router)
app.include_router(admin_router)
