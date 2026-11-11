import { test, expect, type Browser, type Page } from "@playwright/test";

async function signIn(browser: Browser, account: RegExp) {
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto("/login");
  await page.getByRole("button", { name: account }).click();
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).not.toHaveURL(/login/);
  return page;
}

test("three shops approve, authorize, receive delivery and reconcile receipts", async ({
  browser,
}, testInfo) => {
  const buyers: Page[] = [];
  const tomorrow = new Date(Date.now() + 86_400_000).toISOString().slice(0, 10);
  for (const name of [/Ananya/, /Rahul/, /Meera/]) {
    const page = await signIn(browser, name);
    buyers.push(page);
    await page.goto("/retailer/catalog");
    const product = page
      .locator("article")
      .filter({ has: page.getByText("Sona Masoori rice", { exact: true }) });
    await product
      .getByRole("button", { name: "Prepare buying request" })
      .click();
    await page.getByLabel("Delivery date").fill(tomorrow);
    await page.getByLabel(/Minimum quantity/).fill("30");
    await page.getByLabel(/Maximum quantity/).fill("30");
    await page.getByLabel(/Hard delivered-price ceiling/).fill("1.70");
    await page
      .getByRole("button", { name: "Confirm request & join delivery pool" })
      .click();
    await expect(page.getByRole("status")).toContainText("Saved");
  }
  const seller = await signIn(browser, /Sree Distributors/);
  await seller.goto("/seller/pools");
  await seller
    .getByRole("button", { name: "Optimize & lock final quote" })
    .click();
  await expect(
    seller.getByRole("cell", { name: "$48.00", exact: true }),
  ).toHaveCount(3);
  await seller.screenshot({
    path: testInfo.outputPath("cleared-pool.png"),
    fullPage: true,
  });

  for (const page of buyers) {
    await page.goto("/retailer/pools");
    await page.getByRole("button", { name: /Approve my allocation/ }).click();
    await page.getByRole("link", { name: "Continue to payment" }).click();
    await page
      .getByRole("button", { name: "Create simulated checkout" })
      .click();
    await page
      .getByRole("button", { name: "Simulate buyer authorization" })
      .click();
    await expect(page.getByText("AUTHORIZED", { exact: true })).toBeVisible();
  }

  await seller.reload();
  await seller.getByRole("button", { name: "Dispatch authorized run" }).click();
  await expect(seller.getByText("DISPATCHED", { exact: true })).toBeVisible();
  const driver = await signIn(browser, /Kiran/);
  await expect(
    driver.getByRole("heading", { name: /Ordered delivery stops/ }),
  ).toBeVisible();
  await expect(
    driver.getByRole("link", { name: "Open navigation ↗" }),
  ).toHaveCount(3);
  for (let i = 0; i < 3; i++) {
    const form = driver.locator("form").first();
    await form.getByLabel("Recipient name").fill("Verified shop recipient");
    await form.getByLabel("Recipient acknowledges receipt").check();
    await form
      .getByRole("button", { name: "Record delivery evidence" })
      .click();
    await expect(driver.locator("form")).toHaveCount(2 - i);
  }
  await expect(driver.getByText("CAPTURED", { exact: true })).toHaveCount(3);
  await buyers[0].goto("/retailer/receipts");
  await expect(buyers[0].getByText("MATCHED", { exact: true })).toBeVisible();
  await buyers[0].screenshot({
    path: testInfo.outputPath("matched-receipt.png"),
    fullPage: true,
  });
  await buyers[0].setViewportSize({ width: 390, height: 844 });
  await buyers[0].reload();
  await expect(buyers[0].getByText("MATCHED", { exact: true })).toBeVisible();
  await buyers[0].getByRole("button", { name: "Open navigation" }).click();
  await expect(
    buyers[0].getByRole("link", { name: "Bills & receipts" }),
  ).toBeVisible();
  await buyers[0].screenshot({
    path: testInfo.outputPath("mobile-navigation.png"),
    fullPage: true,
  });
  for (const page of [...buyers, seller, driver]) await page.context().close();
});

test("buying helper compares live catalog and a retailer cannot enter admin", async ({
  browser,
}, testInfo) => {
  const page = await signIn(browser, /Ananya/);
  await page.goto("/retailer/procurement");
  await page
    .getByRole("button", { name: "Try a shared rice order within $1.70/kg" })
    .click();
  await page.getByRole("button", { name: "Compare supplier offers" }).click();
  await expect(
    page.getByText("Offline rules-based interpretation · no model call"),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Basmati rice", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Review product & create request" }),
  ).toHaveCount(2);
  await page.screenshot({
    path: testInfo.outputPath("buying-helper.png"),
    fullPage: true,
  });
  await page.goto("/admin/users");
  await expect(
    page.getByRole("heading", { name: "This workspace is unavailable" }),
  ).toBeVisible();
  const response = await page.request.get("/api/v1/workspace");
  expect((await response.json()).user.roles).toEqual(["RETAILER"]);
  await page.context().close();
});

test("a dropout voids old commitments and requires fresh approval", async ({
  browser,
}, testInfo) => {
  const date = new Date(Date.now() + 2 * 86_400_000).toISOString().slice(0, 10);
  const buyers: Page[] = [];
  const requests: { id: string; pool_id: string }[] = [];
  async function mutate(page: Page, path: string, body: unknown = {}) {
    const session = await (await page.request.get("/api/v1/me")).json();
    const response = await page.request.post(path, {
      data: body,
      headers: { "X-CSRF-Token": session.csrf },
    });
    expect(response.ok(), await response.text()).toBeTruthy();
    return response.json();
  }
  for (const name of [/Ananya/, /Rahul/, /Meera/]) {
    const page = await signIn(browser, name);
    buyers.push(page);
    requests.push(
      await mutate(page, "/api/v1/procurement/requests", {
        product_id: "rice-sona",
        zone_id: "south-zone",
        dispatch_date: date,
        quantity_min: 30,
        quantity_max: 30,
        ceiling_minor: 170,
      }),
    );
  }
  const seller = await signIn(browser, /Sree Distributors/);
  const pool = await mutate(
    seller,
    `/api/v1/pools/${requests[0].pool_id}/clear`,
  );
  for (const buyer of buyers) {
    const order = await mutate(buyer, `/api/v1/pools/${pool.id}/approve`, {
      version: pool.version,
    });
    await mutate(buyer, `/api/v1/orders/${order.id}/checkout`);
    await mutate(buyer, `/api/v1/orders/${order.id}/authorize`);
  }
  await seller.goto("/seller/pools");
  const current = seller
    .locator("section")
    .filter({ has: seller.getByText(date, { exact: false }) })
    .filter({ has: seller.getByText("CLEARED", { exact: true }) });
  await current.getByText("Recover a changed order").click();
  await current.getByLabel("Request to exclude").selectOption(requests[2].id);
  seller.once("dialog", (dialog) => dialog.accept());
  await current
    .getByRole("button", { name: "Recalculate with fresh approvals" })
    .click();
  await expect(
    seller.getByRole("cell", { name: "$49.00", exact: true }),
  ).toHaveCount(2);
  await expect(seller.getByText("CANCELLED", { exact: true })).toBeVisible();
  await seller.screenshot({
    path: testInfo.outputPath("dropout-recovery.png"),
    fullPage: true,
  });
  await buyers[0].goto("/retailer/pools");
  await expect(
    buyers[0].getByRole("button", { name: /Approve my allocation/ }),
  ).toBeVisible();
  const state = await (await buyers[0].request.get("/api/v1/workspace")).json();
  expect(
    state.orders
      .filter((o: { pool_id: string }) => o.pool_id === pool.id)
      .every((o: { payment_status: string }) => o.payment_status === "VOIDED"),
  ).toBeTruthy();
  for (const page of [...buyers, seller]) await page.context().close();
});
