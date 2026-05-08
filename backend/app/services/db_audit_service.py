"""Fase 20 — Database audit service.

Orchestrates connection testing, user/privilege collection and
AI-powered analysis for all supported database types.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.crypto import decrypt_credentials

log = logging.getLogger(__name__)

_IDLE_DAYS_THRESHOLD = 90
_SUPERUSER_ROLES = {"sysadmin", "DBA", "SYSDBA"}


# ── Connector factory ─────────────────────────────────────────────────────────

def _get_connector(db_type: str, host: str, port: int, database: str, creds: dict):
    username = creds.get("username", "")
    password = creds.get("password", "")
    ssl      = bool(creds.get("ssl", False))

    if db_type == "postgresql":
        from app.connectors.db_postgresql import PostgreSQLDbConnector
        return PostgreSQLDbConnector(host, port, database, username, password, ssl)
    if db_type in ("mysql", "mariadb"):
        from app.connectors.db_mysql import MySQLDbConnector
        return MySQLDbConnector(host, port, database, username, password, ssl)
    if db_type == "sqlserver":
        from app.connectors.db_sqlserver import SQLServerDbConnector
        return SQLServerDbConnector(host, port, database, username, password, ssl)
    if db_type == "oracle":
        from app.connectors.db_oracle import OracleDbConnector
        return OracleDbConnector(host, port, database, username, password, ssl)
    raise ValueError(f"Tipo de banco não suportado: {db_type}")


# ── Connection test ───────────────────────────────────────────────────────────

async def test_connection(connector_obj) -> tuple[bool, str]:
    from app.models.database_connector import DatabaseConnector
    creds = decrypt_credentials(connector_obj.encrypted_credentials)
    conn = _get_connector(
        connector_obj.db_type, connector_obj.host, connector_obj.port,
        connector_obj.database_name, creds,
    )
    return await conn.test_connection()


# ── Findings analysis ─────────────────────────────────────────────────────────

def _analyze_findings(users: list[dict]) -> list[dict]:
    findings: list[dict] = []

    for u in users:
        name = u.get("name", "")
        if u.get("is_system"):
            continue

        if u.get("is_superuser") and u.get("can_login", True):
            findings.append({
                "type":     "excessive_privilege",
                "severity": "high",
                "user":     name,
                "detail":   "Conta com privilégio de superusuário/DBA — minimizar ao necessário",
            })

        days = u.get("days_since_login")
        if days is not None and days > _IDLE_DAYS_THRESHOLD:
            findings.append({
                "type":     "idle_account",
                "severity": "medium",
                "user":     name,
                "detail":   f"Conta inativa há {days} dias — considere desativar ou revogar",
            })

        if u.get("password_never_expires") and u.get("can_login", True):
            findings.append({
                "type":     "no_password_expiry",
                "severity": "low",
                "user":     name,
                "detail":   "Senha configurada para nunca expirar",
            })

        if u.get("password_expired"):
            findings.append({
                "type":     "expired_password",
                "severity": "medium",
                "user":     name,
                "detail":   "Senha expirada — conta pode estar sendo usada com bypass",
            })

        if u.get("is_locked") is False and u.get("days_since_login") is None:
            findings.append({
                "type":     "never_logged_in",
                "severity": "low",
                "user":     name,
                "detail":   "Conta nunca acessou o banco — remova se desnecessária",
            })

    return findings


# ── AI summary ────────────────────────────────────────────────────────────────

async def _generate_ai_summary(connector_name: str, db_type: str, db_version: str,
                                users: list[dict], findings: list[dict]) -> tuple[str, list[str]]:
    try:
        import anthropic
        from app.config import settings

        high   = [f for f in findings if f["severity"] == "high"]
        medium = [f for f in findings if f["severity"] == "medium"]
        low    = [f for f in findings if f["severity"] == "low"]

        findings_txt = "\n".join(
            f"[{f['severity'].upper()}] {f['type']} — {f['user']}: {f['detail']}"
            for f in findings[:30]
        ) or "Nenhuma inconformidade detectada."

        users_summary = (
            f"Total de contas: {len(users)}\n"
            f"Superusuários: {sum(1 for u in users if u.get('is_superuser'))}\n"
            f"Contas que podem logar: {sum(1 for u in users if u.get('can_login'))}\n"
            f"Contas bloqueadas: {sum(1 for u in users if u.get('is_locked'))}\n"
        )

        prompt = (
            f"Banco de dados: {connector_name} ({db_type})\n"
            f"Versão: {db_version}\n\n"
            f"Resumo de contas:\n{users_summary}\n"
            f"Inconformidades detectadas ({len(findings)} total — "
            f"{len(high)} críticas, {len(medium)} médias, {len(low)} baixas):\n"
            f"{findings_txt}\n\n"
            "Forneça:\n"
            "1. Um parágrafo de resumo executivo da postura de segurança deste banco\n"
            "2. Lista de 3-5 recomendações priorizadas (máximo 1 linha cada)\n"
            "Responda em Português do Brasil."
        )

        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        msg = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=1024,
            system=(
                "Você é um especialista em segurança de bancos de dados. "
                "Analise dados de auditoria e forneça recomendações claras e acionáveis. "
                "Seja direto e técnico."
            ),
            messages=[{"role": "user", "content": prompt}],
        )
        full_text = msg.content[0].text if msg.content else ""

        lines = [l.strip() for l in full_text.splitlines() if l.strip()]
        summary = lines[0] if lines else full_text
        recs = [l.lstrip("0123456789.-) ") for l in lines[1:] if l and not l.startswith("#")][:5]
        return summary, recs

    except Exception as exc:
        log.warning("db_audit_ai_failed: %s", exc)
        return "", []


# ── Main audit runner ─────────────────────────────────────────────────────────

async def run_audit(db: AsyncSession, connector_id: UUID, tenant_id: UUID) -> "DatabaseAuditReport":
    from app.models.database_connector import DatabaseAuditReport, DatabaseConnector, AuditStatus

    connector = await db.get(DatabaseConnector, connector_id)
    if not connector or connector.tenant_id != tenant_id:
        raise ValueError("Conector não encontrado")

    report = DatabaseAuditReport(
        tenant_id=tenant_id,
        connector_id=connector_id,
        status=AuditStatus.running,
    )
    db.add(report)
    await db.flush()
    await db.refresh(report)
    await db.commit()

    try:
        creds = decrypt_credentials(connector.encrypted_credentials)
        conn  = _get_connector(
            connector.db_type, connector.host, connector.port,
            connector.database_name, creds,
        )
        info = await conn.collect_info()

        users    = info.get("users", [])
        findings = _analyze_findings(users)
        version  = info.get("version", "")

        ai_summary, ai_recs = await _generate_ai_summary(
            connector.name, connector.db_type, version, users, findings
        )

        report.status           = AuditStatus.completed
        report.db_version       = version[:200] if version else None
        report.user_count       = len(users)
        report.finding_count    = len(findings)
        report.users            = users
        report.findings         = findings
        report.ai_summary       = ai_summary
        report.ai_recommendations = ai_recs
        report.completed_at     = datetime.now(timezone.utc)

        log.info(
            "db_audit_completed connector=%s users=%d findings=%d",
            connector_id, len(users), len(findings),
        )

    except Exception as exc:
        report.status = AuditStatus.failed
        report.error  = str(exc)[:1000]
        report.completed_at = datetime.now(timezone.utc)
        log.exception("db_audit_failed connector=%s: %s", connector_id, exc)

    await db.commit()
    await db.refresh(report)
    return report
