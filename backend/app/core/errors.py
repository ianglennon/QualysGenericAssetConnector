from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException


def make_error(code: str, message: str, details: dict | None = None) -> dict:
    return {"error": {"code": code, "message": message, "details": details or {}}}


# Exception handlers to register on the app
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    # If the router already passed a structured error dict, pass it through directly.
    # This preserves specific error codes (e.g. AUTH_INVALID_CREDENTIALS) from routers
    # rather than overwriting with the generic code_map value.
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)

    code_map = {
        401: "AUTH_UNAUTHORIZED",
        403: "AUTH_FORBIDDEN",
        404: "NOT_FOUND",
        422: "VALIDATION_ERROR",
    }
    code = code_map.get(exc.status_code, "HTTP_ERROR")
    return JSONResponse(
        status_code=exc.status_code,
        content=make_error(code, str(exc.detail)),
    )


def _sanitize_errors(errors: list[dict]) -> list[dict]:
    """Ensure validation error details are JSON-serializable.

    Pydantic V2 may include non-serializable objects (e.g. ValueError)
    in the ``ctx`` field. Convert them to strings.
    """
    sanitized = []
    for err in errors:
        clean = dict(err)
        if "ctx" in clean and isinstance(clean["ctx"], dict):
            clean["ctx"] = {k: str(v) for k, v in clean["ctx"].items()}
        sanitized.append(clean)
    return sanitized


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=make_error("VALIDATION_ERROR", "Request validation failed", {"errors": _sanitize_errors(exc.errors())}),
    )
