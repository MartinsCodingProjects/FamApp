// Full setup wizard flow in a browser (BUILDPLAN 1.9.7, docs/spec-setup-wizard.md).
import { expect, test } from "@playwright/test";

import { totp } from "./totp";

const SETUP_TOKEN = "e2e-setup-token-0123456789abcdef0123";
const PASSWORD = "correct horse battery";
const SERVICE_ACCOUNT = {
  type: "service_account",
  project_id: "famapp-e2e",
  client_email: "fcm@famapp-e2e.iam.gserviceaccount.com",
  private_key: "-----BEGIN PRIVATE KEY-----\nnot-a-real-key\n-----END PRIVATE KEY-----\n",
};

test("wizard: token, admin, TOTP, Firebase, second user, lock, login, logout", async ({ page }) => {
  await page.goto("/setup");
  await page.locator('input[name="token"]').fill("wrong");
  await page.getByRole("button").click();
  await expect(page.getByRole("alert")).toBeVisible();

  await page.locator('input[name="token"]').fill(SETUP_TOKEN);
  await page.getByRole("button").click();
  await expect(page).toHaveURL(/\/setup\/admin$/);

  await page.locator('input[name="name"]').fill("Admin");
  await page.locator('input[name="password"]').fill(PASSWORD);
  await page.locator('input[name="password_repeat"]').fill(PASSWORD);
  await page.getByRole("button").click();
  await expect(page).toHaveURL(/\/setup\/totp$/);

  await expect(page.locator(".qr-code")).toBeVisible();
  const secret = (await page.getByTestId("totp-secret").textContent())!.trim();
  await page.locator('input[name="code"]').fill(totp(secret));
  await page.getByRole("button").click();
  await expect(page).toHaveURL(/\/setup\/firebase$/);

  await page.locator('input[name="file"]').setInputFiles({
    name: "credentials.json",
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify(SERVICE_ACCOUNT)),
  });
  await page.getByRole("button").click();
  await expect(page).toHaveURL(/\/setup\/user$/);

  await page.locator('input[name="name"]').fill("Partner");
  await page.locator('select[name="time_zone"]').selectOption("Europe/Berlin");
  await page.getByRole("button").click();
  await expect(page).toHaveURL(/\/setup\/finish$/);
  await expect(page.locator(".summary")).toContainText("famapp-e2e");

  await page.getByRole("button").click();
  await expect(page).toHaveURL(/\/login$/);
  expect((await page.request.get("/setup")).status()).toBe(404);

  // The wizard used the current TOTP step; log in with the next one so it is not a replay.
  await page.locator('input[name="name"]').fill("Admin");
  await page.locator('input[name="password"]').fill(PASSWORD);
  await page.locator('input[name="code"]').fill(totp(secret, Date.now(), 1));
  await page.getByRole("button").click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByTestId("signed-in")).toContainText("Admin");

  await page.getByRole("button").click();
  await expect(page).toHaveURL(/\/login$/);
});
