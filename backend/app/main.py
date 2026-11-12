import os

from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.modules.negotiation.agent_router import router as agent_router
from app.modules.negotiation.demo_router import router as demo_router
from app.modules.negotiation.procurement_router import router as procurement_router
from app.modules.negotiation.router import router as negotiation_router
from app.platform.acp import VERSION as ACP_VERSION
from app.platform.acp import ProtocolError
from app.platform.acp import router as acp_router
from app.platform.auth import current_user
from app.platform.business import router as business_router
from app.platform.features_router import router as features_router
from app.platform.media import router as media_router
from app.platform.payments import Payments
from app.platform.registration import router as registration_router
from app.platform.router import router as platform_router
from app.platform.seed import seed
from app.platform.store import Store

# Local development only; deployed environments supply variables through their
# secret manager. Existing environment variables always take precedence.
load_dotenv()


def create_app(database_url: str | None = None, demo: bool | None = None) -> FastAPI:
    app = FastAPI(
        title="PayPool API",
        version="0.2.0",
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
    app.include_router(registration_router)
    app.include_router(business_router)
    app.include_router(media_router)
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
    else:
        app.include_router(features_router)
        app.include_router(acp_router)

    @app.exception_handler(ProtocolError)
    async def protocol_error(request, error):
        return JSONResponse(
            {
                "type": "service_unavailable"
                if error.status >= 500
                else "invalid_request",
                "code": error.code,
                "message": error.message,
            },
            status_code=error.status,
            headers={"API-Version": ACP_VERSION, "Cache-Control": "no-store"},
        )

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
