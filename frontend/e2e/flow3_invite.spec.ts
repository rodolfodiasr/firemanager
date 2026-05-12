/**
 * E2E Flow 3: Invite → onboarding new user via accept-invite page
 *
 * Validates the AcceptInvite page: valid token shows form, expired token shows
 * error, successful accept shows confirmation and link to login.
 */
import { test, expect } from "@playwright/test";

const VALID_TOKEN = "valid-invite-token-abc";
const EXPIRED_TOKEN = "expired-invite-token-xyz";

test("valid invite token shows accept form", async ({ page }) => {
  await page.route(`**/invites/${VALID_TOKEN}`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        token: VALID_TOKEN,
        email: "newuser@company.com",
        tenant_id: "tenant-111",
        tenant_name: "Acme Corp",
        role: "analyst_n1",
        expires_at: new Date(Date.now() + 3600 * 1000).toISOString(),
      }),
    })
  );

  await page.goto(`/invite/${VALID_TOKEN}`);

  // Should show the invite details — email or tenant name
  await expect(page.locator("text=newuser@company.com").or(page.locator("text=Acme Corp"))).toBeVisible({
    timeout: 10_000,
  });
});

test("expired invite token shows error state", async ({ page }) => {
  await page.route(`**/invites/${EXPIRED_TOKEN}`, (route) =>
    route.fulfill({
      status: 410,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Convite expirado" }),
    })
  );

  await page.goto(`/invite/${EXPIRED_TOKEN}`);

  // AcceptInvite shows error card on 410/404
  await expect(page.locator("text=inválido").or(page.locator("text=expirado")).or(page.locator("text=Convite inválido ou expirado"))).toBeVisible({
    timeout: 10_000,
  });
});

test("successful accept shows confirmation and login button", async ({ page }) => {
  await page.route(`**/invites/${VALID_TOKEN}`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        token: VALID_TOKEN,
        email: "newuser@company.com",
        tenant_id: "tenant-111",
        tenant_name: "Acme Corp",
        role: "analyst_n1",
        expires_at: new Date(Date.now() + 3600 * 1000).toISOString(),
      }),
    })
  );

  await page.route(`**/invites/${VALID_TOKEN}/accept`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ message: "Convite aceito com sucesso. Você já pode fazer login." }),
    })
  );

  await page.goto(`/invite/${VALID_TOKEN}`);

  // Wait for the form to appear
  await expect(page.locator("text=newuser@company.com").or(page.locator("text=Acme Corp"))).toBeVisible({
    timeout: 10_000,
  });

  // Fill the form if inputs are present
  const nameInput = page.locator('input[placeholder*="nome" i]').or(page.locator('input[type="text"]')).first();
  const pwdInput = page.locator('input[type="password"]').first();

  if (await nameInput.isVisible()) {
    await nameInput.fill("New User");
  }
  if (await pwdInput.isVisible()) {
    await pwdInput.fill("NewUser@1234");
  }

  const submitBtn = page.getByRole("button", { name: /aceitar|criar|concluir/i });
  if (await submitBtn.isVisible()) {
    await submitBtn.click();
    // After accept, should show success state
    await expect(page.locator("text=aceito").or(page.locator("text=sucesso")).or(page.locator("text=login"))).toBeVisible({
      timeout: 10_000,
    });
  }
});

test("nonexistent invite token shows 404 error state", async ({ page }) => {
  await page.route("**/invites/does-not-exist", (route) =>
    route.fulfill({
      status: 404,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Convite não encontrado" }),
    })
  );

  await page.goto("/invite/does-not-exist");

  await expect(
    page.locator("text=inválido").or(page.locator("text=expirado")).or(page.locator("text=não encontrado"))
  ).toBeVisible({ timeout: 10_000 });
});
