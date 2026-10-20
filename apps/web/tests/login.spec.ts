import { expect, test } from "@playwright/test";

test("Neon exchange rejection stays on the form with the error and entered email", async ({ page }) => {
  await page.route("**/api/v1/auth/options", route => route.fulfill({ json: { neon: true } }));
  await page.route("**/api/auth/**", route => route.fulfill({ json: route.request().url().includes("/token")
    ? { token: "test-rejected-token" } : { user: { id: "test" }, session: null } }));
  await page.route("**/api/v1/auth/neon", route => route.fulfill({ status: 401,
    json: { error: { message: "Invalid or expired Neon sign-in" } } }));
  await page.goto("/login");
  await expect(page.getByLabel("Sign-in method")).toHaveValue("neon");
  await page.getByLabel("Email address").fill("test@example.com");
  await page.getByLabel("Password", { exact: true }).fill("test-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Invalid or expired Neon sign-in" })).toBeVisible();
  await expect(page.getByLabel("Email address")).toHaveValue("test@example.com");
  await expect(page.getByRole("button", { name: "Sign in", exact: true })).toBeEnabled();
});
