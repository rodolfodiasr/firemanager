"""DLP — Data Loss Prevention para o chat do Eternity SecOps.

Detecta e mascara PII brasileira, credenciais e segredos de infraestrutura
antes de enviar mensagens ao agente IA e persistir nos audit logs.

Arquitetura:
  - Padrões builtin compilados uma única vez no import do módulo
  - validate-docbr valida dígitos verificadores de CPF/CNPJ (reduz falsos positivos)
  - scan_message() é chamado nos endpoints de chat antes do agente
  - log_incidents() persiste no dlp_incidents sem guardar o dado original
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Sequence
from uuid import UUID

# ── Builtin rules catalog ─────────────────────────────────────────────────────

BUILTIN_RULES: list[dict] = [
    # ── PII Brasileira ─────────────────────────────────────────────────────
    {
        "rule_key":   "cpf",
        "rule_name":  "CPF",
        "description": "Cadastro de Pessoa Física — 11 dígitos com verificador (LGPD)",
        "category":   "pii_br",
        "default_action": "block",
        "pattern":    r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b",
        "use_docbr":  "cpf",
    },
    {
        "rule_key":   "cnpj",
        "rule_name":  "CNPJ",
        "description": "Cadastro Nacional de Pessoa Jurídica — 14 dígitos com verificador",
        "category":   "pii_br",
        "default_action": "block",
        "pattern":    r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b",
        "use_docbr":  "cnpj",
    },
    {
        "rule_key":   "pis",
        "rule_name":  "PIS/PASEP",
        "description": "Programa de Integração Social — 11 dígitos",
        "category":   "pii_br",
        "default_action": "warn",
        "pattern":    r"\b\d{3}\.?\d{5}\.?\d{2}-?\d{1}\b",
    },
    {
        "rule_key":   "titulo_eleitor",
        "rule_name":  "Título de Eleitor",
        "description": "Documento eleitoral brasileiro — 12 dígitos",
        "category":   "pii_br",
        "default_action": "warn",
        "pattern":    r"\b\d{4}\s?\d{4}\s?\d{4}\b",
    },
    {
        "rule_key":   "dados_bancarios",
        "rule_name":  "Dados Bancários",
        "description": "Agência e conta bancária mencionados juntos",
        "category":   "pii_br",
        "default_action": "warn",
        "pattern":    r"(?i)\b(ag[eê]ncia|ag\.?)\s*[\d\-\.]+.{0,20}(conta|c\.?c\.?)\s*[\d\-\.]+",
    },
    {
        "rule_key":   "chave_pix",
        "rule_name":  "Chave PIX",
        "description": "Chave PIX aleatória (UUID) com contexto de PIX",
        "category":   "pii_br",
        "default_action": "warn",
        "pattern":    r"(?i)\bpix\b.{0,30}[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    },
    # ── Credenciais ────────────────────────────────────────────────────────
    {
        "rule_key":   "senha_plain",
        "rule_name":  "Senha em plain text",
        "description": "Senha digitada diretamente com prefixo reconhecível",
        "category":   "credentials",
        "default_action": "block",
        "pattern":    r"(?i)\b(senha|password|pass|pwd|secret)\s*[=:]\s*\S+",
    },
    {
        "rule_key":   "ssh_private_key",
        "rule_name":  "SSH Private Key",
        "description": "Chave privada SSH/PEM colada no chat",
        "category":   "credentials",
        "default_action": "block",
        "pattern":    r"-----BEGIN\s+(?:RSA|EC|OPENSSH|DSA|ECDSA)\s+PRIVATE KEY-----",
    },
    {
        "rule_key":   "pem_certificate",
        "rule_name":  "Certificado PEM",
        "description": "Conteúdo de certificado X.509 em formato PEM",
        "category":   "credentials",
        "default_action": "block",
        "pattern":    r"-----BEGIN CERTIFICATE-----",
    },
    {
        "rule_key":   "aws_access_key",
        "rule_name":  "AWS Access Key",
        "description": "Chave de acesso AWS — formato AKIA seguido de 16 chars",
        "category":   "credentials",
        "default_action": "block",
        "pattern":    r"\bAKIA[A-Z0-9]{16}\b",
    },
    {
        "rule_key":   "jwt_token",
        "rule_name":  "JWT Token",
        "description": "JSON Web Token completo (header.payload.signature)",
        "category":   "credentials",
        "default_action": "block",
        "pattern":    r"\b[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\b",
    },
    {
        "rule_key":   "connection_string",
        "rule_name":  "Connection String com senha",
        "description": "URL de banco de dados com credenciais embutidas",
        "category":   "credentials",
        "default_action": "block",
        "pattern":    r"(?i)(postgresql|mysql|mongodb\+srv?|redis|sqlserver|jdbc):\/\/[^:@\s]+:[^@\s]+@",
    },
    {
        "rule_key":   "http_basic_auth",
        "rule_name":  "HTTP Basic Auth",
        "description": "Header Authorization Basic com credenciais em base64",
        "category":   "credentials",
        "default_action": "block",
        "pattern":    r"(?i)\bBasic\s+[A-Za-z0-9+/]{8,}={0,2}\b",
    },
    {
        "rule_key":   "api_token_generico",
        "rule_name":  "API Token genérico",
        "description": "Token de API identificado por prefixo de chave",
        "category":   "credentials",
        "default_action": "warn",
        "pattern":    r'(?i)\b(api[_-]?key|apikey|bearer|token)\s*[=:]\s*["\']?\S{8,}["\']?',
    },
    # ── Infraestrutura MSSP ────────────────────────────────────────────────
    {
        "rule_key":   "snmp_community",
        "rule_name":  "SNMP Community String",
        "description": "String de comunidade SNMP — acesso de leitura/escrita a devices",
        "category":   "infra_mssp",
        "default_action": "block",
        "pattern":    r"(?i)\b(community|snmp[_-]?community)\s*[=:]\s*\S+",
    },
    {
        "rule_key":   "vpn_psk",
        "rule_name":  "VPN Pre-Shared Key",
        "description": "Chave pré-compartilhada de VPN IPSec",
        "category":   "infra_mssp",
        "default_action": "block",
        "pattern":    r"(?i)\b(psk|pre[_-]?shared[_-]?key|vpn[_-]?key|ipsec[_-]?key)\s*[=:]\s*\S+",
    },
    {
        "rule_key":   "tacacs_radius",
        "rule_name":  "TACACS+/RADIUS Key",
        "description": "Chave de autenticação TACACS+ ou RADIUS",
        "category":   "infra_mssp",
        "default_action": "block",
        "pattern":    r"(?i)\b(tacacs[_+]?key|radius[_-]?secret|radius[_-]?key|aaa[_-]?key)\s*[=:]\s*\S+",
    },
    {
        "rule_key":   "ldap_bind_password",
        "rule_name":  "LDAP Bind Password",
        "description": "Senha de bind LDAP para autenticação de diretório",
        "category":   "infra_mssp",
        "default_action": "block",
        "pattern":    r"(?i)\b(bind[_-]?password|ldap[_-]?password|ldap[_-]?pass)\s*[=:]\s*\S+",
    },
    {
        "rule_key":   "enable_secret",
        "rule_name":  "Enable Secret (Cisco)",
        "description": "Senha de enable/secret de equipamentos Cisco",
        "category":   "infra_mssp",
        "default_action": "block",
        "pattern":    r"(?i)\b(enable[_-]?password|enable[_-]?secret)\s*[=:]\s*\S+",
    },
    {
        "rule_key":   "bgp_password",
        "rule_name":  "BGP MD5 Password",
        "description": "Senha de autenticação de sessão BGP",
        "category":   "infra_mssp",
        "default_action": "block",
        "pattern":    r"(?i)\b(bgp[_-]?password|neighbor.{0,40}password)\s*[=:]\s*\S+",
    },
]

# ── Compiled patterns cache ───────────────────────────────────────────────────

_COMPILED: dict[str, re.Pattern] = {
    r["rule_key"]: re.compile(r["pattern"], re.IGNORECASE | re.DOTALL)
    for r in BUILTIN_RULES
    if r.get("pattern")
}

# ── docbr validators (lazy import to avoid hard crash if not installed) ───────

def _get_docbr_validator(kind: str):
    try:
        if kind == "cpf":
            from validate_docbr import CPF
            return CPF()
        if kind == "cnpj":
            from validate_docbr import CNPJ
            return CNPJ()
    except ImportError:
        return None
    return None


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class DLPFinding:
    rule_key: str
    rule_name: str
    action: str          # "block" | "warn"
    token: str           # masked replacement token


@dataclass
class DLPResult:
    findings: list[DLPFinding] = field(default_factory=list)
    masked_text: str = ""

    @property
    def has_blocks(self) -> bool:
        return any(f.action == "block" for f in self.findings)

    @property
    def blocked_findings(self) -> list[dict]:
        return [
            {"rule_key": f.rule_key, "rule_name": f.rule_name}
            for f in self.findings if f.action == "block"
        ]

    @property
    def warn_findings(self) -> list[dict]:
        return [
            {"rule_key": f.rule_key, "rule_name": f.rule_name}
            for f in self.findings if f.action == "warn"
        ]


# ── Core scan logic ───────────────────────────────────────────────────────────

def _token(rule_key: str, match_str: str) -> str:
    digest = hashlib.sha256(match_str.encode()).hexdigest()[:8]
    return f"[DLP:{rule_key.upper()}:{digest}]"


def _validate_cpf(value: str) -> bool:
    v = _get_docbr_validator("cpf")
    return v.validate(value) if v else True


def _validate_cnpj(value: str) -> bool:
    v = _get_docbr_validator("cnpj")
    return v.validate(value) if v else True


def scan_text(text: str, active_rules: list[dict]) -> DLPResult:
    """Scan text against active rules and return findings + masked text."""
    result = DLPResult(masked_text=text)
    working = text

    for rule in active_rules:
        key = rule["rule_key"]
        action = rule["action"]
        pattern = _COMPILED.get(key)

        if pattern is None and rule.get("pattern"):
            try:
                pattern = re.compile(rule["pattern"], re.IGNORECASE | re.DOTALL)
            except re.error:
                continue

        if pattern is None:
            continue

        matches = list(pattern.finditer(working))
        if not matches:
            continue

        # docbr digit validation for CPF and CNPJ
        use_docbr = rule.get("use_docbr")
        confirmed_matches = []
        for m in matches:
            if use_docbr == "cpf" and not _validate_cpf(m.group()):
                continue
            if use_docbr == "cnpj" and not _validate_cnpj(m.group()):
                continue
            confirmed_matches.append(m)

        if not confirmed_matches:
            continue

        tok = _token(key, confirmed_matches[0].group())
        result.findings.append(DLPFinding(
            rule_key=key,
            rule_name=rule["rule_name"],
            action=action,
            token=tok,
        ))
        working = pattern.sub(tok, working)

    result.masked_text = working
    return result


# ── DB integration ────────────────────────────────────────────────────────────

async def get_or_create_config(db, tenant_id: UUID):
    """Return DLPConfig for tenant, creating default if absent."""
    from sqlalchemy import select
    from app.models.dlp import DLPConfig

    row = (await db.execute(
        select(DLPConfig).where(DLPConfig.tenant_id == tenant_id)
    )).scalar_one_or_none()

    if row is None:
        row = DLPConfig(tenant_id=tenant_id)
        db.add(row)
        await db.flush()
        await db.refresh(row)

    return row


async def get_active_rules(db, tenant_id: UUID) -> list[dict]:
    """Return active rules for tenant.

    If no tenant-specific rules exist yet, seeds builtin rules and returns them.
    """
    from sqlalchemy import select
    from app.models.dlp import DLPRule

    rows = (await db.execute(
        select(DLPRule).where(
            DLPRule.tenant_id == tenant_id,
            DLPRule.is_enabled.is_(True),
        )
    )).scalars().all()

    if not rows:
        await seed_builtin_rules(db, tenant_id)
        rows = (await db.execute(
            select(DLPRule).where(
                DLPRule.tenant_id == tenant_id,
                DLPRule.is_enabled.is_(True),
            )
        )).scalars().all()

    return [
        {
            "rule_key":  r.rule_key,
            "rule_name": r.rule_name,
            "action":    r.action,
            "pattern":   r.pattern,
            "use_docbr": next(
                (b.get("use_docbr") for b in BUILTIN_RULES if b["rule_key"] == r.rule_key),
                None,
            ),
        }
        for r in rows
    ]


async def seed_builtin_rules(db, tenant_id: UUID) -> None:
    """Inserts all builtin rules for a tenant (idempotent via ON CONFLICT DO NOTHING)."""
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from app.models.dlp import DLPRule

    for rule in BUILTIN_RULES:
        stmt = pg_insert(DLPRule).values(
            tenant_id=tenant_id,
            rule_key=rule["rule_key"],
            rule_name=rule["rule_name"],
            description=rule.get("description"),
            category=rule["category"],
            action=rule["default_action"],
            is_enabled=True,
            is_builtin=True,
            pattern=rule.get("pattern"),
        ).on_conflict_do_nothing(constraint="uq_dlp_rules_tenant_key")
        await db.execute(stmt)

    await db.flush()


async def log_incidents(db, tenant_id: UUID, user_id: UUID | None, findings: Sequence[DLPFinding], source: str = "chat", ip: str | None = None) -> None:
    from app.models.dlp import DLPIncident

    for f in findings:
        db.add(DLPIncident(
            tenant_id=tenant_id,
            user_id=user_id,
            pii_type=f.rule_key,
            action_taken=f.action,
            source=source,
            ip_address=ip,
        ))
    if findings:
        await db.flush()


async def scan_message(db, tenant_id: UUID, user_id: UUID | None, text: str, source: str = "chat", ip: str | None = None) -> DLPResult:
    """Full DLP pipeline: load config → load rules → scan → log incidents."""
    config = await get_or_create_config(db, tenant_id)
    if not config.enabled:
        return DLPResult(masked_text=text)

    active_rules = await get_active_rules(db, tenant_id)
    result = scan_text(text, active_rules)

    if result.findings:
        await log_incidents(db, tenant_id, user_id, result.findings, source=source, ip=ip)
        await db.commit()

    return result
