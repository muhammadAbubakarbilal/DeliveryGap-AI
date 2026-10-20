import { chromium, expect } from "@playwright/test";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const credentials = JSON.parse(await readFile(fileURLToPath(new URL("../../../.cache/neon-smoke.json", import.meta.url)), "utf8"));
const browser = await chromium.launch();
const page = await browser.newPage();
page.setDefaultTimeout(30000);
try {
  await page.goto("http://localhost:3000/login");
  await page.getByRole("combobox", { name: "Sign-in method" }).selectOption("neon");
  await page.getByLabel("Email address").fill(credentials.email);
  await page.getByLabel("Password", { exact: true }).fill(credentials.password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Projects", exact: true })).toBeVisible({ timeout: 30000 });
  console.log("PASS Neon Auth: browser sign-in and protected application access");
  await page.reload();
  await expect(page.getByRole("heading", { name: "Projects", exact: true })).toBeVisible();
  console.log("PASS Neon Auth: session restoration after reload");
  const name = "Neon verification " + Date.now();
  await page.getByRole("button", { name: "New project" }).click();
  await page.getByLabel("Project name").fill(name);
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("link").filter({ has: page.getByRole("heading", { name, exact: true }) }).click();
  await expect(page).toHaveURL(/\/projects\/[^/]+$/, { timeout: 30000 });
  await page.reload();
  await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
  console.log("PASS Neon Postgres: project written through UI/API and read after reload");
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await page.getByRole("combobox", { name: "Status", exact: true }).selectOption("archived");
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByText("archived", { exact: true }).first()).toBeVisible();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page).toHaveURL(/\/login$/);
  const api = await page.request.get("http://localhost:3000/api/v1/auth/me");
  if (api.status() !== 401) throw new Error("Signed-out API request was not denied");
  const managed = await page.request.get("http://localhost:3000/api/auth/get-session");
  const session = await managed.json();
  if (session?.user || session?.session) throw new Error("Managed session was not revoked");
  await page.goto("http://localhost:3000/projects");
  await expect(page).toHaveURL(/\/login$/);
  console.log("PASS Neon Auth: managed sign-out and protected-page/API denial");
} catch (error) {
  const alerts = await page.getByRole("alert").allTextContents();
  console.error("Neon browser verification failed:", error.message);
  console.error("Page:", page.url());
  console.error("Visible alerts:", alerts.join(" | "));
  process.exitCode = 1;
} finally {
  await browser.close();
}
