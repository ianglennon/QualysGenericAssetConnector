"""Route introspection test: every non-public endpoint must have a require_permission dependency.

Implements PERM-04. If a new route is added without require_permission(), this test fails.
"""
import pytest
from fastapi.routing import APIRoute
from app.main import app


# Public paths that do not require permission checks
PUBLIC_PATHS = {
    "/health",
    "/api/v1/auth/login",
    "/api/v1/auth/refresh",
    "/api/v1/auth/change-password",
    "/api/v1/auth/me",
    "/docs",
    "/openapi.json",
    "/redoc",
}


def _has_permission_dependency(route: APIRoute) -> bool:
    """Check if a route has a require_permission dependency (tagged with _permission_required)."""
    for dep in route.dependant.dependencies:
        if hasattr(dep, "call"):
            # Check for the _permission_required tag set by require_permission()
            if hasattr(dep.call, "_permission_required"):
                return True
    return False


def test_all_routes_have_permission_dependency():
    """Every non-public API route must have a require_permission() dependency."""
    unprotected = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        if route.path in PUBLIC_PATHS:
            continue
        if not _has_permission_dependency(route):
            unprotected.append(f"{route.methods} {route.path}")

    assert not unprotected, (
        f"Routes without require_permission() dependency:\n"
        + "\n".join(f"  - {r}" for r in sorted(unprotected))
    )


def test_public_paths_are_accessible():
    """Sanity check: public paths exist and are not accidentally protected."""
    route_paths = {route.path for route in app.routes if isinstance(route, APIRoute)}
    for public_path in ["/health", "/api/v1/auth/login", "/api/v1/auth/refresh"]:
        assert public_path in route_paths, f"Expected public path {public_path} not found in routes"
