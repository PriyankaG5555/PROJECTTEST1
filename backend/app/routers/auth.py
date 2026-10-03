"""Auth endpoints — api-contract-spec.md §5."""

from fastapi import APIRouter, Request, Response, status

from app.schemas import UserOut
from app.schemas.auth import DeleteAccountIn, LoginIn, SignupIn, UserResponse
from app.security import CurrentUser, DbSession, clear_session_cookie, set_session_cookie
from app.services import auth_service
from app.services.rate_limit import check_auth_rate_limit

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", status_code=status.HTTP_201_CREATED, response_model=UserResponse)
def signup(body: SignupIn, request: Request, response: Response, db: DbSession) -> UserResponse:
    check_auth_rate_limit(request)
    user = auth_service.signup(db, body.username, body.password)
    set_session_cookie(response, user.id)
    return UserResponse(user=UserOut.model_validate(user))


@router.post("/login", response_model=UserResponse)
def login(body: LoginIn, request: Request, response: Response, db: DbSession) -> UserResponse:
    check_auth_rate_limit(request)
    user = auth_service.login(db, body.username, body.password)
    set_session_cookie(response, user.id)
    return UserResponse(user=UserOut.model_validate(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout() -> Response:
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_session_cookie(response)
    return response


@router.get("/me", response_model=UserResponse)
def me(user: CurrentUser) -> UserResponse:
    return UserResponse(user=UserOut.model_validate(user))


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_me(
    body: DeleteAccountIn, request: Request, user: CurrentUser, db: DbSession
) -> Response:
    check_auth_rate_limit(request)
    auth_service.delete_account(db, user, body.password)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_session_cookie(response)
    return response
