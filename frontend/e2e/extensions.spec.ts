import { test, expect, type Browser, type Page } from "@playwright/test";

async function login(browser: Browser, account: RegExp) {
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto("/login");
  await page.getByRole("button", { name: account }).click();
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).not.toHaveURL(/login/);
  return page;
}
async function post(page: Page, path: string, data: unknown = {}) {
  const session = await (await page.request.get("/api/v1/me")).json();
  const result = await page.request.post(path, {
    data,
    headers: {
      "X-CSRF-Token": session.csrf,
      "Idempotency-Key": crypto.randomUUID(),
    },
  });
  expect(result.ok(), await result.text()).toBeTruthy();
  return result.json();
}
const day = (offset: number) =>
  new Date(Date.now() + offset * 86400000).toISOString().slice(0, 10);

test("supplier and buyer exchange persisted terms, manage fleet and inventory", async ({
  browser,
}, info) => {
  const buyers: Page[] = [];
  const requests: { id: string; pool_id: string }[] = [];
  for (const account of [/Ananya/, /Rahul/, /Meera/]) {
    const buyer = await login(browser, account);
    buyers.push(buyer);
    requests.push(
      await post(buyer, "/api/v1/procurement/requests", {
        product_id: "rice-sona",
        zone_id: "south-zone",
        dispatch_date: day(3),
        quantity_min: 30,
        quantity_max: 30,
        ceiling_minor: 170,
      }),
    );
  }
  const seller = await login(browser, /Sree Distributors/);
  await seller.goto("/seller/offers");
  await seller.getByLabel("Buying request").selectOption(requests[0].id);
  await seller.getByLabel(/Unit offer/).fill("1.50");
  const proposal = seller.waitForResponse(
    (r) =>
      r.url().endsWith("/api/v1/offers") && r.request().method() === "POST",
  );
  await seller
    .getByRole("button", { name: "Send proposal", exact: true })
    .click();
  const offer = await (await proposal).json();
  await expect(
    seller
      .locator(`#offer-${offer.id}`)
      .getByText("SUBMITTED", { exact: true }),
  ).toBeVisible();
  await buyers[0].goto("/retailer/offers");
  buyers[0].once("dialog", (d) => d.accept());
  await buyers[0]
    .locator(`#offer-${offer.id}`)
    .getByRole("button", { name: "Accept offer · version 1" })
    .click();
  await expect(
    buyers[0]
      .locator(`#offer-${offer.id}`)
      .getByText("ACCEPTED", { exact: true }),
  ).toBeVisible();
  await buyers[0].screenshot({
    path: info.outputPath("accepted-commercial-offer.png"),
    fullPage: true,
  });
  const buyerState = await (
    await buyers[0].request.get("/api/v1/workspace")
  ).json();
  expect(
    buyerState.orders.some(
      (o: { pool_id: string }) => o.pool_id === requests[0].pool_id,
    ),
  ).toBeFalsy();
  await seller.goto("/seller/fleet");
  await seller.getByLabel("Vehicle name").fill("City delivery van");
  await seller.getByLabel("Registration", { exact: true }).fill("CITY-100");
  await seller.getByLabel("Maximum load (kg)").fill("100");
  await seller.getByRole("button", { name: "Save vehicle" }).click();
  await expect(
    seller.getByRole("heading", { name: "City delivery van", exact: true }),
  ).toBeVisible();
  await seller.goto("/seller/inventory");
  const product = seller.locator("article").filter({
    has: seller.getByRole("heading", {
      name: "Sona Masoori rice",
      exact: true,
    }),
  });
  await product.getByLabel("Stock adjustment").fill("5");
  await product
    .getByLabel("Reason", { exact: true })
    .fill("New delivery received");
  await product.getByRole("button", { name: "Record adjustment" }).click();
  await expect(
    seller.getByText("New delivery received", { exact: false }),
  ).toBeVisible();
  for (const page of [...buyers, seller]) await page.context().close();
});

test("map schedule, buyer-confirmed delivery, recurring requests and worker controls", async ({
  browser,
}, info) => {
  const seller = await login(browser, /Sree Distributors/);
  await seller.goto("/seller/service-areas");
  await seller
    .getByLabel("Area name", { exact: true })
    .fill("Confirmed receipt route");
  await seller.getByRole("button", { name: "Save delivery area" }).click();
  await expect(
    seller.getByRole("heading", {
      name: "Confirmed receipt route",
      exact: true,
    }),
  ).toBeVisible();
  await seller.screenshot({
    path: info.outputPath("delivery-zone-map.png"),
    fullPage: true,
  });
  const catalog = await (await seller.request.get("/api/v1/workspace")).json();
  const zone = catalog.zones.find(
    (z: { name: string }) => z.name === "Confirmed receipt route",
  );
  expect(zone.recipient_confirmation_required).toBeTruthy();
  const buyers: Page[] = [];
  const requests: { pool_id: string }[] = [];
  const orders: { id: string }[] = [];
  for (const account of [/Ananya/, /Rahul/, /Meera/]) {
    const buyer = await login(browser, account);
    buyers.push(buyer);
    requests.push(
      await post(buyer, "/api/v1/procurement/requests", {
        product_id: "rice-sona",
        zone_id: zone.id,
        dispatch_date: day(4),
        quantity_min: 30,
        quantity_max: 30,
        ceiling_minor: 170,
      }),
    );
  }
  const pool = await post(seller, `/api/v1/pools/${requests[0].pool_id}/clear`);
  for (const buyer of buyers) {
    const order = await post(buyer, `/api/v1/pools/${pool.id}/approve`, {
      version: pool.version,
    });
    orders.push(order);
    await post(buyer, `/api/v1/orders/${order.id}/checkout`);
    await post(buyer, `/api/v1/orders/${order.id}/authorize`);
  }
  await post(seller, `/api/v1/pools/${pool.id}/dispatch`, {
    driver_id: "driver-demo",
    vehicle_id: "demo-van",
  });
  const driver = await login(browser, /Kiran/);
  for (let i = 0; i < 3; i++) {
    const form = driver.locator("form").first();
    await form.getByLabel("Recipient name").fill("Shop recipient");
    await form.getByLabel("Recipient acknowledges receipt").check();
    await form
      .getByRole("button", { name: "Record delivery evidence" })
      .click();
    await expect(driver.locator("form")).toHaveCount(2 - i);
  }
  const driverState = await (
    await driver.request.get("/api/v1/workspace")
  ).json();
  expect(
    driverState.orders
      .filter((o: { pool_id: string }) => o.pool_id === pool.id)
      .every(
        (o: { payment_status: string }) => o.payment_status === "AUTHORIZED",
      ),
  ).toBeTruthy();
  await buyers[0].goto("/retailer/orders");
  buyers[0].once("dialog", (d) => d.accept());
  await buyers[0]
    .getByRole("button", { name: "Confirm received goods & release payment" })
    .click();
  const received = await buyers[0].request.get(
    `/api/v1/orders/${orders[0].id}`,
  );
  expect((await received.json()).payment_status).toBe("CAPTURED");
  await buyers[0].goto("/retailer/receipts");
  const printable = await buyers[0].request.get(
    `/api/v1/orders/${orders[0].id}/receipt.html`,
  );
  expect(printable.ok()).toBeTruthy();
  expect(await printable.text()).toContain("PayPool Smart Receipt");
  await buyers[1].goto("/retailer/standing-orders");
  await buyers[1].getByLabel("Instruction name").fill("Weekly replenishment");
  await buyers[1].getByLabel("First delivery date").fill(day(7));
  await buyers[1].getByLabel("Create request this many days ahead").fill("1");
  await buyers[1]
    .getByRole("button", { name: "Save recurring instruction" })
    .click();
  await expect(
    buyers[1].getByRole("heading", {
      name: "Weekly replenishment",
      exact: true,
    }),
  ).toBeVisible();
  await buyers[1].getByRole("button", { name: "Pause instruction" }).click();
  await expect(
    buyers[1].getByRole("button", { name: "Resume instruction" }),
  ).toBeVisible();
  const admin = await login(browser, /PayPool Operations/);
  await admin.goto("/admin/jobs");
  await admin.getByRole("button", { name: "Run pending jobs" }).click();
  await expect(
    admin.getByText("No worker heartbeat yet", { exact: false }),
  ).toHaveCount(0);
  await admin.screenshot({
    path: info.outputPath("durable-worker-health.png"),
    fullPage: true,
  });
  for (const page of [...buyers, seller, driver, admin])
    await page.context().close();
});
