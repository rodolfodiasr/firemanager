from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from app.api import admin, ai_safety, alerts, assistant, assistant_docs, audit, auth, bulk_jobs, category_roles, cloud_accounts, compliance, compliance_packs, config_migration, connectivity, database_connectors, device_groups, devices, dlp, documents, edge_agents, enterprise, executive, firewall_migration, firmware, glpi, golden_bundles, golden_template, identity, identity_governance, inspect, integrations, invite, knowledge, module_roles, onboarding, operations, orchestrator, platform_config, playbooks, product, recommendations, remediation, security_infra, self_service, selfservice_portal, server_operations, servers, siem, templates, tenants, variables, vm_migration
from app.config import settings

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    log.info("Eternity SecOps starting", environment=settings.environment)
    from app.database import AsyncSessionLocal
    from app.services import platform_config_service
    async with AsyncSessionLocal() as db:
        try:
            await platform_config_service.warm_cache(db)
        except Exception:
            pass  # DB may not have the table yet (first run before migration)
    yield
    log.info("Eternity SecOps shutting down")


app = FastAPI(
    title="Eternity SecOps API",
    description="Plataforma Multivendor de Segurança e Gestão de Infraestrutura com IA",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.middleware.api_key_rate_limit import ApiKeyRateLimitMiddleware  # noqa: E402
app.add_middleware(ApiKeyRateLimitMiddleware)

Instrumentator().instrument(app).expose(app)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(devices.router, prefix="/devices", tags=["devices"])
app.include_router(operations.router, prefix="/operations", tags=["operations"])
app.include_router(audit.router, prefix="/audit", tags=["audit"])
app.include_router(documents.router, prefix="/documents", tags=["documents"])
app.include_router(templates.router, prefix="/templates", tags=["templates"])
app.include_router(inspect.router, prefix="/devices", tags=["inspect"])
app.include_router(recommendations.router, prefix="/devices", tags=["recommendations"])
app.include_router(tenants.router, prefix="/tenants", tags=["tenants"])
app.include_router(integrations.router, prefix="/integrations", tags=["integrations"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])
app.include_router(invite.router, prefix="/invite", tags=["invite"])
app.include_router(bulk_jobs.router, prefix="/bulk-jobs", tags=["bulk-jobs"])
app.include_router(device_groups.router, prefix="/device-groups", tags=["device-groups"])
app.include_router(variables.router, prefix="/variables", tags=["variables"])
app.include_router(servers.router, prefix="/servers", tags=["servers"])
app.include_router(server_operations.router, prefix="/server-operations", tags=["server-operations"])
app.include_router(remediation.router, prefix="/remediation", tags=["remediation"])
app.include_router(compliance.router, prefix="/compliance", tags=["compliance"])
app.include_router(category_roles.router, prefix="/category-roles", tags=["category-roles"])
app.include_router(module_roles.router, prefix="/module-roles", tags=["module-roles"])
app.include_router(glpi.router, prefix="/glpi", tags=["glpi"])
app.include_router(config_migration.router,   prefix="/config-migrations",   tags=["config-migrations"])
app.include_router(firewall_migration.router,  prefix="/firewall-migrations",  tags=["firewall-migrations"])
app.include_router(golden_template.router,    prefix="/golden-templates",      tags=["golden-templates"])
app.include_router(connectivity.router,       prefix="/connectivity",           tags=["connectivity"])
app.include_router(knowledge.router,           prefix="/knowledge/documents",    tags=["knowledge"])
app.include_router(database_connectors.router, prefix="/database-connectors",    tags=["database-connectors"])
app.include_router(identity.router,            prefix="/identity",                tags=["identity"])
app.include_router(onboarding.router,          prefix="/onboarding",              tags=["onboarding"])
app.include_router(alerts.router,              prefix="/alerts",                  tags=["alerts"])
app.include_router(executive.router,           prefix="/executive",               tags=["executive"])
app.include_router(enterprise.router,          prefix="/enterprise",               tags=["enterprise"])
app.include_router(golden_bundles.router,      prefix="/golden-bundles",           tags=["golden-bundles"])
app.include_router(vm_migration.router,        prefix="/vm-migration",              tags=["vm-migration"])
app.include_router(platform_config.router,     prefix="/platform-config",            tags=["platform-config"])
app.include_router(firmware.router,            prefix="",                             tags=["firmware"])
app.include_router(assistant.router,           prefix="/assistant",                    tags=["assistant"])
app.include_router(assistant_docs.router,      prefix="/assistant",                    tags=["assistant-docs"])
app.include_router(orchestrator.router,        prefix="/orchestrate",                  tags=["orchestrator"])
app.include_router(identity_governance.router, prefix="/identity-governance",          tags=["identity-governance"])
app.include_router(self_service.router,        prefix="/identity/self-service",        tags=["self-service"])
app.include_router(playbooks.router,           prefix="/playbooks",                    tags=["playbooks"])
app.include_router(siem.router,               prefix="/siem",                         tags=["siem"])
app.include_router(siem.webhook_router,        prefix="/webhooks",                     tags=["webhooks"])
app.include_router(cloud_accounts.router,      prefix="/cloud-accounts",               tags=["cloud-accounts"])
app.include_router(compliance_packs.router,    prefix="/compliance-enterprise",        tags=["compliance-enterprise"])
app.include_router(ai_safety.router,           prefix="/ai-safety",                    tags=["ai-safety"])
app.include_router(selfservice_portal.router,  prefix="/selfservice-portal",           tags=["selfservice-portal"])
app.include_router(security_infra.router,      prefix="/security-infra",               tags=["security-infra"])
app.include_router(edge_agents.router,         prefix="/platform",                     tags=["edge-agents"])
app.include_router(product.router,             prefix="/product",                      tags=["product"])
app.include_router(dlp.router,                 prefix="/dlp",                           tags=["dlp"])


class FireManagerError(Exception):
    status_code: int = 500
    default_message: str = "Internal server error"

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.default_message
        super().__init__(self.message)


@app.exception_handler(FireManagerError)
async def firemanager_error_handler(request: Request, exc: FireManagerError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": "0.1.0"}
