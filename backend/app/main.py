from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.modules.negotiation.router import router as negotiation_router
from app.modules.negotiation.procurement_router import router as procurement_router
from app.modules.negotiation.demo_router import router as demo_router
from app.modules.negotiation.agent_router import router as agent_router

# Local development only; deployed environments supply variables through their
# secret manager. Existing environment variables always take precedence.
load_dotenv()


def create_app() -> FastAPI:
    app = FastAPI(
        title="PayPool API",
        version="0.1.0",
        description="PayPool modular-monolith API.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-Request-ID"],
    )
    app.include_router(negotiation_router, prefix="/api/v1")
    app.include_router(procurement_router, prefix="/api/v1")
    app.include_router(demo_router, prefix="/api/v1")
    app.include_router(agent_router, prefix="/api/v1")

    @app.get("/health", tags=["system"])
    def health_check() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
