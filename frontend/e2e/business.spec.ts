import { test, expect, type Browser, type Page } from "@playwright/test";
const photo = {
  name: "test-photo.png",
  mimeType: "image/png",
  buffer: Buffer.from(
    "iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAIAAABLbSncAAAAFElEQVR4nGNkYPjPgA0wYRUdtBIAy0MBD1YkjLoAAAAASUVORK5CYII=",
    "base64",
  ),
};
async function login(browser: Browser, name: RegExp) {
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto("/login");
  await page.getByRole("button", { name }).click();
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).not.toHaveURL(/login/);
  return page;
}
async function post(page: Page, path: string, data: unknown = {}) {
  const me = await (await page.request.get("/api/v1/me")).json();
  const r = await page.request.post(path, {
    data,
    headers: {
      "X-CSRF-Token": me.csrf,
      "Idempotency-Key": crypto.randomUUID(),
    },
  });
  expect(r.ok(), await r.text()).toBeTruthy();
  return r.json();
}

test("business profile persists contact, delivery and notification settings", async ({
  browser,
}) => {
  const p = await login(browser, /Ananya/);
  await p.goto("/retailer/settings");
  await p.getByLabel("Business name", { exact: true }).fill("GreenMart Foods");
  await p
    .getByLabel("Contact email", { exact: true })
    .fill("delivery@example.com");
  await p.getByLabel("Contact phone", { exact: true }).fill("123456789");
  await p
    .getByLabel("Delivery address", { exact: true })
    .fill("12 Market Road");
  await p.getByLabel("City", { exact: true }).fill("Bengaluru");
  await p
    .getByLabel("Delivery instructions", { exact: true })
    .fill("Use rear entrance");
  await p.getByLabel("Receive routine in-app updates").uncheck();
  await p.getByRole("button", { name: "Save profile", exact: true }).click();
  await expect(p.getByRole("status")).toContainText("Business profile saved");
  await expect(
    p.getByText("GreenMart Foods", { exact: true }).first(),
  ).toBeVisible();
  await p.reload();
  await expect(p.getByLabel("Contact email", { exact: true })).toHaveValue(
    "delivery@example.com",
  );
  await expect(p.getByLabel("Delivery address", { exact: true })).toHaveValue(
    "12 Market Road",
  );
  await expect(
    p.getByLabel("Receive routine in-app updates"),
  ).not.toBeChecked();
  await p.context().close();
});

test("supplier application can be rejected, corrected, approved and account access controlled", async ({
  browser,
}) => {
  const buyer = await login(browser, /Rahul/);
  const admin = await login(browser, /PayPool Operations/);
  await buyer.goto("/retailer/settings");
  await buyer
    .getByLabel("Application business name", { exact: true })
    .fill("Corner Wholesale");
  await buyer
    .getByLabel("Business registration / tax number")
    .fill("GST-12345");
  await buyer
    .getByLabel("Registered business address")
    .fill("44 Wholesale Street");
  await buyer.getByLabel("Application contact phone").fill("123456789");
  await buyer
    .getByLabel("Products and fulfillment capability")
    .fill("Rice and packaging with daily local delivery");
  await buyer
    .getByRole("button", { name: "Submit supplier application" })
    .click();
  await expect(
    buyer.getByText("Application status: PENDING", { exact: true }),
  ).toBeVisible();
  await admin.goto("/admin/seller-verification");
  await admin
    .getByLabel("Decision for Corner Wholesale")
    .selectOption("REJECTED");
  await admin
    .getByLabel("Review note for Corner Wholesale")
    .fill("Please correct the registration number");
  admin.once("dialog", (d) => d.accept());
  await admin
    .getByRole("button", { name: "Save application decision" })
    .click();
  await expect(
    buyer.getByText("Application status: REJECTED", { exact: true }),
  ).toBeVisible();
  await buyer
    .getByLabel("Business registration / tax number")
    .fill("GST-CORRECTED");
  await buyer
    .getByRole("button", { name: "Submit supplier application" })
    .click();
  await expect(
    buyer.getByText("Application status: PENDING", { exact: true }),
  ).toBeVisible();
  await admin
    .getByLabel("Decision for Corner Wholesale")
    .selectOption("APPROVED");
  await admin
    .getByLabel("Review note for Corner Wholesale")
    .fill("Business details checked and approved");
  admin.once("dialog", (d) => d.accept());
  await admin
    .getByRole("button", { name: "Save application decision" })
    .click();
  await expect(
    buyer.getByText("Application status: APPROVED", { exact: true }),
  ).toBeVisible();
  const me = await (await buyer.request.get("/api/v1/me")).json();
  expect(me.user.roles).toContain("SELLER");
  await admin.goto("/admin/users");
  admin.once("dialog", (d) => d.accept("Temporary access review"));
  await admin.getByRole("button", { name: /^Disable Rahul/ }).click();
  await expect(
    admin.getByRole("button", { name: /^Reactivate Rahul/ }),
  ).toBeVisible();
  expect((await buyer.request.get("/api/v1/me")).status()).toBe(401);
  admin.once("dialog", (d) => d.accept("Access review completed"));
  await admin.getByRole("button", { name: /^Reactivate Rahul/ }).click();
  await expect(
    admin.getByRole("button", { name: /^Disable Rahul/ }),
  ).toBeVisible();
  await buyer.context().close();
  await admin.context().close();
});

test("supplier and assigned driver upload real images through authenticated endpoints", async ({
  browser,
}) => {
  const seller = await login(browser, /Sree Distributors/);
  await seller.goto("/seller/catalog");
  await seller
    .locator("article")
    .filter({
      has: seller.getByRole("heading", {
        name: "Sona Masoori rice",
        exact: true,
      }),
    })
    .getByRole("button", { name: "Edit product & tiers" })
    .click();
  await seller
    .getByLabel("Choose file for upload product photo", { exact: true })
    .setInputFiles(photo);
  await seller
    .getByRole("button", { name: "Upload product photo", exact: true })
    .click();
  await expect(
    seller.getByText("Image uploaded. Embedded metadata was removed.", {
      exact: true,
    }),
  ).toBeVisible();
  const buyers: Page[] = [];
  const date = new Date(Date.now() + 86400000).toISOString().slice(0, 10);
  let poolId = "";
  for (const name of [/Ananya/, /Rahul/, /Meera/]) {
    const b = await login(browser, name);
    buyers.push(b);
    const r = await post(b, "/api/v1/procurement/requests", {
      product_id: "rice-sona",
      zone_id: "south-zone",
      dispatch_date: date,
      quantity_min: 30,
      quantity_max: 30,
      ceiling_minor: 170,
      target_price_minor: 150,
    });
    poolId = r.pool_id;
  }
  const pool = await post(seller, `/api/v1/pools/${poolId}/clear`);
  for (const b of buyers) {
    const o = await post(b, `/api/v1/pools/${poolId}/approve`, {
      version: pool.version,
    });
    await post(b, `/api/v1/orders/${o.id}/checkout`);
    await post(b, `/api/v1/orders/${o.id}/authorize`);
  }
  await post(seller, `/api/v1/pools/${poolId}/dispatch`, {
    driver_id: "driver-demo",
    vehicle_id: "demo-van",
  });
  const driver = await login(browser, /Kiran/);
  const form = driver.locator("form").first();
  await form
    .getByLabel("Choose file for upload delivery photo", { exact: true })
    .setInputFiles(photo);
  await form
    .getByRole("button", { name: "Upload delivery photo", exact: true })
    .click();
  await expect(
    form.getByRole("link", { name: "View attached delivery photo" }),
  ).toBeVisible();
  await form.getByLabel("Recipient name").fill("Shop recipient");
  await form.getByLabel("Recipient acknowledges receipt").check();
  await form.getByRole("button", { name: "Record delivery evidence" }).click();
  await expect(
    driver.getByRole("link", { name: "View delivery photo", exact: true }),
  ).toBeVisible();
  for (const p of [...buyers, seller, driver]) await p.context().close();
});
