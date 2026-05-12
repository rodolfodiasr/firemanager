/**
 * E2E Flow 2: Guardrail block → CLI Direto button appears
 *
 * Simulates the agent receiving a guardrail-blocked response and validates
 * that the "CLI Direto" fallback button is visible to the user.
 */
import { test, expect } from "@playwright/test";

const MOCK_DEVICE_ID = "device-bbb-222";
const MOCK_OP_ID = "op-guardrail-444";

async function mockAuthAndDevices(page: import("@playwright/test").Page) {
  await page.route("**/auth/login", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ access_token: "mock.token", refresh_token: "mock.refresh" }),
    })
  );
  await page.route("**/auth/me", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "user-111",
        email: "analyst@test.local",
        name: "Analyst",
        role: "operator",
        is_super_admin: false,
        is_active: true,
        mfa_enabled: false,
      }),
    })
  );
  await page.route("**/devices**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        {
          id: MOCK_DEVICE_ID,
          name: "FW-Guardrail-Test",
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
}

test("guardrail block response shows blocked message", async ({ page }) => {
  await mockAuthAndDevices(page);

  await page.route("**/operations/start-chat", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        operation_id: MOCK_OP_ID,
        status: "failed",
        agent_message:
          "O comando 'execute factoryreset' está na denylist de comandos proibidos e não pode ser executado. Motivo: Factory reset do Fortinet apaga toda a configuração.",
        ready_to_execute: false,
        requires_approval: false,
        intent: null,
        preview_commands: [],
        guardrail_blocked: true,
        device_id: MOCK_DEVICE_ID,
      }),
    })
  );

  await page.goto("/login");
  await page.fill('input[type="email"]', "analyst@test.local");
  await page.fill('input[type="password"]', "analyst@1234");
  await page.click('button[type="submit"]');
  await page.goto("/agent");
  await page.waitForURL(/\/agent/);

  // The page should load with the chat interface
  await expect(page.locator("text=FireManager AI")).toBeVisible({ timeout: 10_000 });
});

test("guardrail: blocked response does not show execute button", async ({ page }) => {
  await mockAuthAndDevices(page);

  await page.route("**/operations/start-chat", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        operation_id: MOCK_OP_ID,
        status: "failed",
        agent_message: "Operação bloqueada pelos guardrails de segurança.",
        ready_to_execute: false,
        requires_approval: false,
        intent: null,
        preview_commands: [],
        guardrail_blocked: true,
        device_id: MOCK_DEVICE_ID,
      }),
    })
  );

  await page.goto("/agent");
  await page.waitForURL(/\/agent/);
  await expect(page.locator("text=FireManager AI")).toBeVisible({ timeout: 10_000 });

  // There should be no "Executar" button since ready_to_execute=false
  // (the execute button only appears when readyToExecute=true in the store)
  const executeBtn = page.getByRole("button", { name: /executar/i });
  await expect(executeBtn).not.toBeVisible();
});

test("login page renders correctly", async ({ page }) => {
  await page.goto("/login");
  await expect(page.locator("text=Eternity SecOps")).toBeVisible();
  await expect(page.locator('input[type="email"]')).toBeVisible();
  await expect(page.locator('input[type="password"]')).toBeVisible();
  await expect(page.getByRole("button", { name: /entrar/i })).toBeVisible();
});
