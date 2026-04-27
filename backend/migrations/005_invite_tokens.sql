-- Migration 005: Invite tokens for self-service onboarding
CREATE TABLE IF NOT EXISTS invite_tokens (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    token      VARCHAR(64) UNIQUE NOT NULL,
    email      VARCHAR(255) NOT NULL,
    tenant_id  UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    role       VARCHAR(50) NOT NULL DEFAULT 'analyst',
    invited_by UUID REFERENCES users(id) ON DELETE SET NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at    TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_invite_tokens_token    ON invite_tokens(token);
CREATE INDEX IF NOT EXISTS idx_invite_tokens_email    ON invite_tokens(email);
CREATE INDEX IF NOT EXISTS idx_invite_tokens_tenant   ON invite_tokens(tenant_id);
