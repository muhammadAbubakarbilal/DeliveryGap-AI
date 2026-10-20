import { expect, test } from "@playwright/test";

test("project creation retries a lost response without duplicating the project", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email address").fill("admin@example.com");
  await page.getByLabel("Password", { exact: true }).fill("smoke-only-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("button", { name: "New project" }).click();
  await page.getByLabel("Project name").fill("Recover lost response");
  const keys: string[] = [];
  const projectIds: string[] = [];
  await page.route("**/api/v1/projects", async route => {
    if (route.request().method() !== "POST") return route.continue();
    keys.push(route.request().headers()["idempotency-key"]);
    const response = await route.fetch();
    expect(response.status()).toBe(201);
    projectIds.push((await response.json()).id);
    // Commit the first request, then lose its response on the way to the UI.
    if (keys.length === 1) return route.abort("failed");
    return route.fulfill({ response });
  });
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Submit the form again to retry." })).toBeVisible();
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Create a project", exact: true })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Recover lost response", exact: true })).toHaveCount(1);
  expect(keys).toHaveLength(2);
  expect(keys[0]).toBeTruthy();
  expect(keys[0]).toBe(keys[1]);
  expect(projectIds[0]).toBe(projectIds[1]);
  // A deliberate new submission after success receives a fresh key.
  await page.getByRole("button", { name: "New project" }).click();
  await page.getByLabel("Project name").fill("Recover lost response");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Recover lost response", exact: true })).toHaveCount(2);
  expect(keys).toHaveLength(3);
  expect(keys[2]).not.toBe(keys[0]);
  expect(projectIds[2]).not.toBe(projectIds[0]);
});

test("authenticated project setup, settings, membership and logout", async ({ page }) => {
  await page.goto("/projects");
  await expect(page).toHaveURL(/\/login$/);
  await page.getByLabel("Email address").fill("admin@example.com");
  await page.getByLabel("Password", { exact: true }).fill("smoke-only-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Projects", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "ShopFlow Checkout" })).toBeVisible();
  await page.getByRole("button", { name: "New project" }).click();
  await page.getByLabel("Project name").fill("Browser smoke project");
  await page.getByLabel("Description").fill("Created through the actual UI and FastAPI.");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("link").filter({ has: page.getByRole("heading", { name: "Browser smoke project" }) }).click();
  await expect(page.getByRole("heading", { name: "Project setup" })).toBeVisible();
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await page.getByLabel("Project name").fill("Reviewed project name");
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByRole("heading", { name: "Reviewed project name" })).toBeVisible();
  await page.getByRole("button", { name: "Enable external AI processing", exact: true }).click();
  await expect(page.getByText("External AI processing is enabled for this project.", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Revoke external AI consent", exact: true }).click();
  await expect(page.getByText("External AI processing is disabled for this project.", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Members", exact: true }).click();
  await page.getByLabel("Workspace user’s email").fill("reviewer@example.com");
  await page.locator('select[name="role"]').selectOption("reviewer");
  await page.getByRole("button", { name: "Add member" }).click();
  await expect(page.getByRole("table").getByText("Sam Rivera", { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: "Reviewed project name" })).toBeVisible();
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.goto("/projects");
  await expect(page).toHaveURL(/\/login$/);
});

test("read-only reviewer sees real data but no management controls", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email address").fill("reviewer@example.com");
  await page.getByLabel("Password", { exact: true }).fill("smoke-only-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Projects", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "New project" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "People & access" })).toHaveCount(0);
  await page.getByRole("link").filter({ has: page.getByRole("heading", { name: "ShopFlow Checkout" }) }).click();
  await expect(page.getByRole("button", { name: "Settings", exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "Members", exact: true }).click();
  await expect(page.getByRole("table").getByText("Sam Rivera", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Add member" })).toHaveCount(0);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  const signOut = page.getByRole("button", { name: "Sign out" });
  await expect(signOut).toBeVisible();
  await signOut.focus();
  await expect(signOut).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/login$/);
  await page.goto("/projects");
  await expect(page).toHaveURL(/\/login$/);
});
