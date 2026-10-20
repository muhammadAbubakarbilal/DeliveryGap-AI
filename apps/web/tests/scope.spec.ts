import { expect, test, type BrowserContext, type Page } from "@playwright/test";

type Role = "admin" | "reviewer";
const sessionCookies: Partial<Record<Role, Awaited<ReturnType<BrowserContext["cookies"]>>>> = {};

test.beforeAll(async ({ playwright, baseURL }) => {
  for (const role of ["admin", "reviewer"] as const) {
    const request = await playwright.request.newContext({ baseURL });
    try {
      const response = await request.post("/api/v1/auth/login", {
        headers: { origin: baseURL! },
        data: { email: `${role}@example.com`, password: "smoke-only-password" },
      });
      expect(response.status()).toBe(200);
      sessionCookies[role] = (await request.storageState()).cookies;
    } finally {
      await request.dispose();
    }
  }
});

async function openWorkspace(page: Page, role: Role = "admin") {
  await page.context().addCookies(sessionCookies[role]!);
  await page.goto("/projects");
}

async function enableExternalAi(page: Page) {
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  const enabledMessage = page.getByText("External AI processing is enabled for this project.", { exact: true });
  if (!(await enabledMessage.count())) {
    await page.getByRole("button", { name: "Enable external AI processing", exact: true }).click();
  }
  await expect(enabledMessage).toBeVisible();
}

test("source upload parses and original download preserves its bytes", async ({ page }) => {
  await openWorkspace(page, "admin");
  await page.getByRole("link").filter({ has: page.getByRole("heading", { name: "ShopFlow Checkout" }) }).click();
  await page.getByRole("link", { name: "Documents and sources", exact: true }).click();
  await page.getByRole("textbox", { name: "Document title", exact: true }).fill("Uploaded delivery scope");
  const original = "The application shall preserve immutable delivery evidence.";
  await page.getByLabel("Source file").setInputFiles({name:"delivery.txt", mimeType:"text/plain", buffer:Buffer.from(original)});
  await page.getByRole("button", { name:"Upload source", exact:true }).click();
  await page.getByRole("link", {name:"Uploaded delivery scope", exact:true}).click();
  await expect(page.getByText(original, {exact:true})).toBeVisible();
  const link = page.getByRole("link", {name:"Download original", exact:true});
  const response = await page.request.get((await link.getAttribute("href"))!);
  expect(response.status()).toBe(200);
  expect(await response.text()).toBe(original);
});

test("grounded draft, review, baseline, and revision preserve published scope", async ({ page }) => {
  await openWorkspace(page, "admin");
  await page.getByRole("link").filter({ has: page.getByRole("heading", { name: "ShopFlow Checkout" }) }).click();
  await page.getByRole("link", { name: "Review requirements and baselines" }).click();
  await page.getByRole("button", { name: "Create draft", exact: true }).click();
  await page.getByLabel("Title", { exact: true }).fill("Currency restriction");
  await page.getByLabel("Requirement", { exact: true }).fill("Checkout accepts USD payments only.");
  await page.getByLabel("Document version").selectOption({ label: "Synthetic currency scope · v1" });
  await expect(page.getByLabel("Source passage").locator("option")).toHaveCount(2);
  await page.getByLabel("Source passage").selectOption({ index: 1 });
  await expect(page.getByLabel("Exact quote")).toHaveValue("Checkout accepts USD payments only.");
  await page.getByRole("button", { name: "Save draft", exact: true }).click();
  await expect(page.getByText("Draft saved for review.", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Approve", exact: true }).click();
  await page.getByLabel("Include this revision in the next baseline").check();
  const keys: string[] = [];
  await page.route("**/baselines", async route => {
    if (route.request().method() !== "POST") return route.continue();
    keys.push(route.request().headers()["idempotency-key"]);
    const response = await route.fetch();
    expect(response.status()).toBe(201);
    if (keys.length === 1) return route.abort("failed");
    return route.fulfill({ response });
  });
  await page.getByRole("button", { name: "Publish baseline", exact: true }).click();
  await expect(page.getByRole("alert")).toBeVisible();
  await page.getByRole("button", { name: "Publish baseline", exact: true }).click();
  expect(keys[0]).toBe(keys[1]);
  await expect(page.getByText("B1 · 1 requirements", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Create revision", exact: true }).click();
  await page.getByLabel("Title", { exact: true }).fill("Updated currency wording");
  await page.getByRole("button", { name: "Save draft", exact: true }).click();
  await expect(page.getByText("v2 · Updated currency wording · draft", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Back to project" }).click();
  await page.getByRole("link", { name: "Delivery evidence and traceability" }).click();
  await page.getByLabel("External identifier").fill("TEST-USD");
  await page.getByRole("combobox", { name: "Kind", exact: true }).selectOption("test");
  await page.getByLabel("Title", { exact: true }).fill("USD checkout passes");
  await page.getByLabel("Status or test result").fill("pass");
  await page.getByLabel("Execution time", { exact: true }).fill("2026-10-19T10:00");
  await page.getByLabel("Test environment", { exact: true }).fill("staging / Chrome");
  await page.getByRole("button", { name: "Save artifact", exact: true }).click();
  await expect(page.getByText("TEST-USD · USD checkout passes · pass", { exact: true })).toBeVisible();
  await page.getByText("TEST-USD · USD checkout passes · pass", { exact: true }).click();
  await expect(page.getByText(/staging \/ Chrome/).first()).toBeVisible();
  await page.getByLabel("Published baseline").selectOption({ label: "B1" });
  await page.getByLabel("Artifact on current page").selectOption({ label: "TEST-USD · USD checkout passes" });
  await page.getByRole("button", { name: "Link evidence", exact: true }).click();
  await expect(page.getByText("USD checkout passes · proposed · inspected revision 1", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Accept", exact: true }).click();
  await expect(page.getByText("USD checkout passes · accepted · inspected revision 1", { exact: true })).toBeVisible();
  await page.getByLabel("CSV file", { exact: true }).setInputFiles({ name: "tasks.csv", mimeType: "text/csv",
    buffer: Buffer.from("Ticket,title,description,status,requirement_id\nTASK-CSV,Imported checkout,USD delivery,done,REQ-001\n") });
  await page.getByText("Map custom CSV headers", { exact: true }).click();
  await page.getByLabel("CSV header for external_id", { exact: true }).fill("Ticket");
  await page.getByRole("button", { name: "Preview CSV", exact: true }).click();
  await expect(page.getByText("1 valid rows; 0 rejected rows.", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Confirm import", exact: true }).click();
  await expect(page.getByText("Accepted: 1; rejected: 0; changed: 1; unchanged: 0.", { exact: true })).toBeVisible();
  await expect(page.getByText("TASK-CSV · Imported checkout · done", { exact: true })).toBeVisible();
  await page.getByText("Imported checkout · proposed · inspected revision 1", { exact: true })
    .locator("..").getByLabel("Select for bulk review", { exact: true }).check();
  await page.getByRole("button", { name: "Accept selected links", exact: true }).click();
  await expect(page.getByText("Imported checkout · accepted · inspected revision 1", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Generate frozen report", exact: true }).click();
  const downloadLink = page.getByRole("link", { name: "Download CSV", exact: true });
  await expect(downloadLink).toBeVisible();
  const downloadResponse = await page.request.get((await downloadLink.getAttribute("href"))!);
  expect(downloadResponse.status()).toBe(200);
  expect(await downloadResponse.text()).toContain("Checkout accepts USD payments only.");
  await page.getByRole("link", { name: "Back to project" }).click();
  await page.getByRole("link", { name: "Change findings" }).click();
  await page.getByRole("combobox", { name: "Baseline", exact: true }).selectOption({ label: "B1" });
  await page.getByRole("button", { name: "Replay synthetic fixture", exact: true }).click();
  await expect(page.getByRole("heading", { name: "CONFLICT", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Confirm proposal", exact: true }).click();
  await expect(page.getByText("Review: confirmed", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Back to project" }).click();
  await page.getByRole("link", { name: "Review requirements and baselines" }).click();
  await expect(page.getByText("v1 · Currency restriction · approved", { exact: true })).toBeVisible();
  await expect(page.getByText("B1 · 1 requirements", { exact: true })).toHaveCount(1);
  await page.reload();
  await expect(page.getByText("v2 · Updated currency wording · draft", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Split into drafts", exact: true }).click();
  const childDrafts = page.getByRole("group", { name: /Child draft/ });
  await expect(childDrafts).toHaveCount(2);
  await childDrafts.nth(0).getByLabel("Title", { exact: true }).fill("Currency restriction detail");
  await childDrafts.nth(0).getByLabel("Requirement", { exact: true }).fill("Checkout supports USD only.");
  await childDrafts.nth(1).getByLabel("Title", { exact: true }).fill("Currency validation detail");
  await childDrafts.nth(1).getByLabel("Requirement", { exact: true }).fill("Unsupported currencies are rejected.");
  await expect(childDrafts.nth(0).getByLabel("Exact quote")).toHaveValue("Checkout accepts USD payments only.");
  await page.getByRole("button", { name: "Create split drafts", exact: true }).click();
  await expect(page.getByText("Requirement split into source-grounded drafts.", { exact: true })).toBeVisible();
  const lineageSummaries = page.getByText("Requirement lineage", { exact: true });
  await expect(lineageSummaries).toHaveCount(3);
  for (let index = 0; index < 3; index += 1) await lineageSummaries.nth(index).click();
  await expect(page.getByText("split: REQ-001 → REQ-002", { exact: true })).toHaveCount(2);
  await expect(page.getByText("split: REQ-001 → REQ-003", { exact: true })).toHaveCount(2);
  await page.getByRole("link", { name: "Back to project" }).click();
  await page.getByRole("link", { name: "Delivery evidence and traceability" }).click();
  await page.getByLabel("Published baseline").selectOption({ label: "B1" });
  await page.getByRole("group", { name: "Filter report findings" }).getByRole("checkbox", { name: "CONFLICT" }).check();
  await page.getByRole("checkbox", { name: "confirmed", exact: true }).check();
  await page.getByRole("button", { name: "Generate frozen report", exact: true }).click();
  await expect(page.getByRole("link", { name: "Download Markdown", exact: true })).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("reviewer can inspect requirements but cannot create or publish", async ({ page }) => {
  await openWorkspace(page, "reviewer");
  await page.getByRole("link").filter({ has: page.getByRole("heading", { name: "ShopFlow Checkout" }) }).click();
  await page.getByRole("link", { name: "Review requirements and baselines" }).click();
  await expect(page.getByRole("heading", { name: "Published baselines" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Create draft", exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Publish baseline", exact: true })).toHaveCount(0);
});

test("background extraction creates cited drafts for human review", async ({ page }) => {
  await openWorkspace(page, "admin");
  await page.getByRole("link").filter({ has: page.getByRole("heading", { name: "ShopFlow Checkout" }) }).click();
  await enableExternalAi(page);
  await page.getByRole("link", { name: "Review requirements and baselines" }).click();
  await page.getByLabel("Source for extraction").selectOption({ label: "Synthetic currency scope · v1" });
  await page.getByRole("button", { name: "Extract drafts", exact: true }).click();
  await expect(page.getByText("1 drafts saved for review.", { exact: true })).toBeVisible();
  await expect(page.getByText("v1 · Extracted currency proposal · draft", { exact: true })).toBeVisible();
});

test("failed extraction retry preserves its idempotency key after a lost response", async ({ page }) => {
  await openWorkspace(page, "admin");
  const projectLink = page.getByRole("link").filter({ has: page.getByRole("heading", { name: "ShopFlow Checkout" }) });
  const projectUrl = await projectLink.getAttribute("href");
  await projectLink.click();
  await enableExternalAi(page);
  await page.getByRole("link", { name: "Documents and sources", exact: true }).click();
  await page.getByLabel("Document title", { exact: true }).fill("Unsupported extraction fixture");
  await page.getByLabel("Source file").setInputFiles({
    name: "unsupported.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("This source is outside the deterministic extraction fixture."),
  });
  await page.getByRole("button", { name: "Upload source", exact: true }).click();
  await page.getByRole("link", { name: "Unsupported extraction fixture", exact: true }).click();
  await expect(page.getByText("This source is outside the deterministic extraction fixture.", { exact: true })).toBeVisible();
  await page.goto(projectUrl!);
  await page.getByRole("link", { name: "Review requirements and baselines" }).click();

  const retryKeys: string[] = [];
  const observedAttempts: number[] = [];
  await page.route("**/operations?page=1&kind=extraction", async route => {
    const response = await route.fetch();
    if (response.ok()) {
      const rows = await response.json() as { status: string; attempts: number }[];
      observedAttempts.push(...rows.filter(row => row.status === "failed").map(row => row.attempts));
    }
    await route.fulfill({ response });
  });
  await page.route("**/operations/*/retry", async route => {
    retryKeys.push(route.request().headers()["idempotency-key"]);
    if (retryKeys.length === 1) return route.abort("failed");
    await route.continue();
  });

  await page.getByLabel("Source for extraction").selectOption({ label: "Unsupported extraction fixture · v1" });
  await page.getByRole("button", { name: "Extract drafts", exact: true }).click();
  await expect(page.getByRole("button", { name: "Retry failed extraction", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Retry failed extraction", exact: true }).click();
  await expect(page.getByText("Failed to fetch", { exact: false }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Retry failed extraction", exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Retry failed extraction", exact: true }).click();
  await expect.poll(() => retryKeys.length).toBe(2);
  await expect.poll(() => observedAttempts.includes(2)).toBe(true);
  expect(retryKeys[0]).toBeTruthy();
  expect(retryKeys[1]).toBe(retryKeys[0]);
});

test("queued change analysis saves grounded findings for review", async ({ page }) => {
  await openWorkspace(page, "admin");
  await page.getByRole("link").filter({ has: page.getByRole("heading", { name: "ShopFlow Checkout" }) }).click();
  await enableExternalAi(page);
  await page.getByRole("link", { name: "Change findings", exact: true }).click();
  await page.getByRole("combobox", { name: "Analysis baseline", exact: true }).selectOption({ label: "B1" });
  await page.getByLabel("Change request", { exact: true }).fill("Add EUR and GBP checkout.");
  await page.getByRole("button", { name: "Queue change analysis", exact: true }).click();
  await expect(page.getByText("Analyzed 1 atomic request(s).", { exact: true })).toBeVisible();
  await expect(page.getByText("Synthetic grounded proposal for browser testing.", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Retrieved baseline candidates" })).toBeVisible();
  await expect(page.getByText(/fused rank 1; lexical rank 1; semantic rank 1/)).toBeVisible();
  await expect(page.getByRole("heading", { name: /Change request evidence/ })).toBeVisible();
});

test("non-actionable change note completes successfully without findings", async ({ page }) => {
  await openWorkspace(page, "admin");
  await page.getByRole("link").filter({ has: page.getByRole("heading", { name: "ShopFlow Checkout" }) }).click();
  await enableExternalAi(page);
  await page.getByRole("link", { name: "Change findings", exact: true }).click();
  await page.getByRole("combobox", { name: "Analysis baseline", exact: true }).selectOption({ label: "B1" });
  await page.getByLabel("Change request", { exact: true }).fill("Let's schedule a call next Tuesday.");
  await page.getByRole("button", { name: "Queue change analysis", exact: true }).click();
  await expect(page.getByText("No actionable software changes were identified.", { exact: true })).toBeVisible();
  await expect(page.getByText("Analysis completed successfully. No actionable software changes were identified.", { exact: true })).toBeVisible();
});

test("multi-action analysis displays successful and failed request segments", async ({ page }) => {
  await openWorkspace(page, "admin");
  await page.getByRole("link").filter({ has: page.getByRole("heading", { name: "ShopFlow Checkout" }) }).click();
  await enableExternalAi(page);
  await page.getByRole("link", { name: "Change findings", exact: true }).click();
  await page.getByRole("combobox", { name: "Analysis baseline", exact: true }).selectOption({ label: "B1" });
  await page.getByLabel("Change request", { exact: true }).fill("Add EUR and GBP checkout. Also allow guest checkout.");
  await page.getByRole("button", { name: "Queue change analysis", exact: true }).click();
  await expect(page.getByText("Analyzed 1 of 2 atomic requests.", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Request 1 · completed", exact: true })).toHaveCount(2);
  await expect(page.getByRole("heading", { name: "Request 2 · failed", exact: true })).toHaveCount(1);
  await expect(page.getByText("Provider output unavailable or invalid", { exact: true })).toBeVisible();
});

test("failed analysis retry preserves its idempotency key after a lost response", async ({ page }) => {
  await openWorkspace(page, "admin");
  await page.getByRole("link").filter({ has: page.getByRole("heading", { name: "ShopFlow Checkout" }) }).click();
  await enableExternalAi(page);
  const baselinesLoaded = page.waitForResponse(response =>
    response.request().method() === "GET" && response.url().includes("/baselines?page=1"),
  );
  await page.getByRole("link", { name: "Review requirements and baselines" }).click();
  await baselinesLoaded;
  const publishedBaselines = page.getByText(/B\d+ · 1 requirements/);
  const previousBaselineCount = await publishedBaselines.count();
  await page.getByRole("button", { name: "Create draft", exact: true }).click();
  await page.getByLabel("Title", { exact: true }).fill("Retry workflow scope");
  await page.getByLabel("Requirement", { exact: true }).fill("Checkout accepts USD payments only.");
  await page.getByLabel("Document version").selectOption({ label: "Synthetic currency scope · v1" });
  await page.getByLabel("Source passage").selectOption({ index: 1 });
  await page.getByRole("button", { name: "Save draft", exact: true }).click();
  await expect(page.getByText("Draft saved for review.", { exact: true })).toBeVisible();
  const retryDraft = page.getByText("v1 · Retry workflow scope · draft", { exact: true })
    .locator("xpath=ancestor::section[contains(@class, 'panel')][1]");
  await retryDraft.getByRole("button", { name: "Approve", exact: true }).click();
  const approvedRetry = page.getByText("v1 · Retry workflow scope · approved", { exact: true })
    .locator("xpath=ancestor::section[contains(@class, 'panel')][1]");
  await expect(approvedRetry).toBeVisible();
  await approvedRetry.getByLabel("Include this revision in the next baseline").check();
  await page.getByRole("button", { name: "Publish baseline", exact: true }).click();
  await expect(page.getByText("Baseline published.", { exact: true })).toBeVisible();
  await expect.poll(() => publishedBaselines.count()).toBe(previousBaselineCount + 1);
  const latestBaseline = await publishedBaselines.first().innerText();
  const baselineNumber = latestBaseline.match(/^B(\d+)/)?.[1];
  expect(baselineNumber).toBeTruthy();
  await page.getByRole("link", { name: "Back to project" }).click();
  await page.getByRole("link", { name: "Change findings", exact: true }).click();

  const retryKeys: string[] = [];
  const observedAttempts: number[] = [];
  await page.route("**/operations?kind=analysis&page=1", async route => {
    const response = await route.fetch();
    if (response.ok()) {
      const rows = await response.json() as { status: string; attempts: number }[];
      observedAttempts.push(...rows.filter(row => row.status === "failed").map(row => row.attempts));
    }
    await route.fulfill({ response });
  });
  await page.route("**/operations/*/retry", async route => {
    retryKeys.push(route.request().headers()["idempotency-key"]);
    if (retryKeys.length === 1) return route.abort("failed");
    await route.continue();
  });

  await page.getByRole("combobox", { name: "Analysis baseline", exact: true }).selectOption({ label: `B${baselineNumber}` });
  await page.getByLabel("Change request", { exact: true }).fill("Unsupported synthetic request.");
  await page.getByRole("button", { name: "Queue change analysis", exact: true }).click();
  await expect(page.getByRole("button", { name: "Retry failed analysis", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Retry failed analysis", exact: true }).click();
  await expect(page.getByText("Failed to fetch", { exact: false }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Retry failed analysis", exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Retry failed analysis", exact: true }).click();
  await expect.poll(() => retryKeys.length).toBe(2);
  await expect.poll(() => observedAttempts.includes(2)).toBe(true);
  expect(retryKeys[0]).toBeTruthy();
  expect(retryKeys[1]).toBe(retryKeys[0]);
});
