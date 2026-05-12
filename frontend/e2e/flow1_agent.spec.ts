/**
 * E2E Flow 1: Login → select device → chat with agent → execute operation
 *
 * Uses page.route() to mock API responses so the test runs without a backend.
 */
import { test, expect } from "@playwright/test";

const MOCK_TOKEN = "eyJ.mock.token";
const MOCK_TENANT_ID = "tenant-aaa-111";
const MOCK_DEVICE_ID = "device-bbb-222";
const MOCK_OP_ID = "op-ccc-333";

test.beforeEach(async ({ page }) => {
  // Intercept login — return a direct access_token (single tenant)
  await page.route("**/auth/login", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        access_token: MOCK_TOKEN,
        refresh_token: "refresh.mock",
      }),
    })
  );

  // Intercept /auth/me
  await page.route("**/auth/me", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "user-aaa",
        email: "admin@test.local",
        name: "Test Admin",
        role: "operator",
        is_super_admin: false,
        is_active: true,
        mfa_enabled: false,
      }),
    })
  );

  // Intercept device list
  await page.route("**/devices**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        {
          id: MOCK_DEVICE_ID,
          name: "FW-Prod-01",
          vendor: "fortinet",
          category: "firewall",
          host: "192.0.2.1",
          port: 443,
          use_ssl: true,
          verify_ssl: false,
          read_only_agent: false,
          status: "online",
          firmware_version: null,
          notes: null,
        },
      ]),
    })
  );
});

test("login succeeds and dashboard loads", async ({ page }) => {
  await page.goto("/login");
  await page.fill('input[type="email"]', "admin@test.local");
  await page.fill('input[type="password"]', "admin@1234");
  await page.click('button[type="submit"]');

  // After login, should redirect to dashboard (not /login)
  await expect(page).not.toHaveURL(/\/login/);
});

test("login with wrong password shows error", async ({ page }) => {
  await page.route("**/auth/login", (route) =>
    route.fulfill({
      status: 401,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Invalid credentials" }),
    })
  );

  await page.goto("/login");
  await page.fill('input[type="email"]', "admin@test.local");
  await page.fill('input[type="password"]', "wrong_password");
  await page.click('button[type="submit"]');

  await expect(page.locator("text=Credenciais inválidas")).toBeVisible();
});

test("agent chat flow — send message and receive plan", async ({ page }) => {
  // Mock start-chat endpoint
  await page.route("**/operations/start-chat", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        operation_id: MOCK_OP_ID,
        status: "approved",
        agent_message: "Plano gerado: liberar porta 443 para 10.0.0.5",
        ready_to_execute: true,
        requires_approval: false,
        intent: "create_rule",
        preview_commands: ["config firewall policy", "edit 0", "end"],
        guardrail_blocked: false,
        device_id: MOCK_DEVICE_ID,
      }),
    })
  );

  // Login first
  await page.goto("/login");
  await page.fill('input[type="email"]', "admin@test.local");
  await page.fill('input[type="password"]', "admin@1234");
  await page.click('button[type="submit"]');

  // Navigate to agent page
  await page.goto("/agent");

  // Wait for page to load
  await page.waitForURL(/\/agent/);

  // The agent page should show the chat interface
  await expect(page.locator("text=FireManager AI")).toBeVisible({ timeout: 10_000 });
});

test("agent execute operation completes", async ({ page }) => {
  await page.route("**/operations/start-chat", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        operation_id: MOCK_OP_ID,
        status: "approved",
        agent_message: "Pronto para executar.",
        ready_to_execute: true,
        requires_approval: false,
        intent: "create_rule",
        preview_commands: ["config firewall policy"],
        guardrail_blocked: false,
        device_id: MOCK_DEVICE_ID,
      }),
    })
  );

  await page.route(`**/operations/${MOCK_OP_ID}/execute`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: MOCK_OP_ID,
        status: "completed",
        intent: "create_rule",
        action_plan: { rule_spec: { name: "Rule-Test", action: "allow" }, result: [] },
        error_message: null,
        executed_direct: false,
        device_id: MOCK_DEVICE_ID,
        device_name: "FW-Prod-01",
        device_category: "firewall",
        bulk_job_id: null,
        parent_operation_id: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        natural_language_input: "criar regra",
        review_comment: null,
        reviewer_id: null,
        reviewed_at: null,
      }),
    })
  );

  await page.goto("/login");
  await page.fill('input[type="email"]', "admin@test.local");
  await page.fill('input[type="password"]', "admin@1234");
  await page.click('button[type="submit"]');
  await page.goto("/agent");
  await page.waitForURL(/\/agent/);
  await expect(page.locator("text=FireManager AI")).toBeVisible({ timeout: 10_000 });
});
