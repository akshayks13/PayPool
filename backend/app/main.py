import os

from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.modules.negotiation.agent_router import router as agent_router
from app.modules.negotiation.demo_router import router as demo_router
from app.modules.negotiation.procurement_router import router as procurement_router
from app.modules.negotiation.router import router as negotiation_router
from app.platform.auth import current_user
from app.platform.payments import Payments
from app.platform.router import router as platform_router
from app.platform.seed import seed
from app.platform.store import Store

# Local development only; deployed environments supply variables through their
# secret manager. Existing environment variables always take precedence.
load_dotenv()


def create_app(database_url: str | None = None, demo: bool | None = None) -> FastAPI:
    app = FastAPI(
        title="PayPool API",
        version="0.1.0",
        description="PayPool modular-monolith API.",
    )
    app.state.demo = (
        demo
        if demo is not None
        else os.getenv("PAYPOOL_DEMO_MODE", "true").lower() == "true"
    )
    app.state.store = Store(database_url)
    app.state.payments = Payments(app.state.demo)
    if app.state.demo:
        seed(app.state.store)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[os.getenv("PAYPOOL_FRONTEND_URL", "http://localhost:3000")],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT"],
        allow_headers=[
            "Content-Type",
            "X-Request-ID",
            "X-CSRF-Token",
            "Idempotency-Key",
        ],
    )
    app.include_router(platform_router)
    # The original fixture endpoints accept caller-supplied identities and
    # therefore remain opt-in, demo-only development tools.
    legacy = (
        app.state.demo
        and os.getenv("PAYPOOL_ENABLE_LEGACY_API", "false").lower() == "true"
    )
    if legacy:
        app.include_router(negotiation_router, prefix="/api/v1")
        app.include_router(demo_router, prefix="/api/v1")
        app.include_router(agent_router, prefix="/api/v1")
    app.include_router(
        procurement_router,
        prefix="/api/v1",
        dependencies=[] if legacy else [Depends(current_user)],
    )

    @app.get("/health", tags=["system"])
    def health_check() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
