from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel, Field, SecretStr

from seoci import auth
from seoci.db import Session
from seoci.models import AuditEvent


class AuthRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()
        async def safe_handler(request):
            try:
                return await handler(request)
            except RequestValidationError:
                return JSONResponse(status_code=422, content={"detail": "Enter a valid username and password (8–1024 characters)"})
        return safe_handler


router = APIRouter(prefix="/api/auth", route_class=AuthRoute)


class Credentials(BaseModel):
    username: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$", max_length=64)
    password: SecretStr = Field(min_length=1, max_length=1024)


class SetupCredentials(Credentials):
    password: SecretStr = Field(min_length=8, max_length=1024)


def audit(username, action):
    with Session() as db:
        db.add(AuditEvent(actor=username, action=action, data={}))
        db.commit()


def set_session(response, request, username, password_hash):
    response.set_cookie(auth.COOKIE, auth.create_session(username, password_hash), max_age=auth.SESSION_SECONDS,
                        httponly=True, samesite="lax", path="/",
                        secure=request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https")
    response.headers["Cache-Control"] = "no-store"


@router.get("/status")
def status():
    return JSONResponse({"setup_required": not bool(auth.load_users())}, headers={"Cache-Control": "no-store"})


@router.get("/me")
def me(request: Request):
    return JSONResponse({"username": request.state.username}, headers={"Cache-Control": "no-store"})


@router.post("/setup")
def setup(body: SetupCredentials):
    if not auth.add_user(body.username, body.password.get_secret_value(), first_only=True):
        raise HTTPException(409, "Setup is already complete. Sign in instead.")
    audit(body.username, "auth_setup")
    return JSONResponse({"username": body.username}, status_code=201, headers={"Cache-Control": "no-store"})


@router.post("/login")
def login(body: Credentials, request: Request, response: Response):
    key = (body.username, request.client.host if request.client else "unknown")
    if auth.throttle.blocked(key):
        raise HTTPException(429, "Too many failed attempts. Try again in 15 minutes.", headers={"Retry-After": "900"})
    encoded = auth.load_users().get(body.username)
    valid = auth.verify_password(body.password.get_secret_value(), encoded or auth.DUMMY_HASH)
    if not valid or not encoded:
        auth.throttle.failed(key)
        audit(body.username, "auth_login_failed")
        raise HTTPException(401, "Invalid username or password")
    auth.throttle.reset(key)
    set_session(response, request, body.username, encoded)
    audit(body.username, "auth_login")
    return {"username": body.username}


@router.post("/logout")
def logout():
    response = JSONResponse({"ok": True}, headers={"Cache-Control": "no-store"})
    response.delete_cookie(auth.COOKIE, path="/", httponly=True, samesite="lax")
    return response
