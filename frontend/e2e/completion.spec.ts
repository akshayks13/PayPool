import { test, expect, type Browser, type Page } from "@playwright/test";

async function login(browser: Browser, name: RegExp) {
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto("/login");
  await page.getByRole("button", { name }).click();
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).not.toHaveURL(/login/);
  return page;
}
async function post(page: Page, path: string, data: unknown) {
  const me = await (await page.request.get("/api/v1/me")).json();
  const response = await page.request.post(path, {
    data,
    headers: {
      "X-CSRF-Token": me.csrf,
      "Idempotency-Key": crypto.randomUUID(),
    },
  });
  expect(response.ok(), await response.text()).toBeTruthy();
  return response.json();
}

test("catalog filters use server brands, units and availability", async ({
  browser,
}) => {
  const page = await login(browser, /Ananya/);
  await page.goto("/retailer/catalog");
  await page.getByLabel("Filter product brand").selectOption("Harvest");
  await expect(page.locator("article")).toHaveCount(2);
  await page.getByLabel("Filter product unit").selectOption("kg");
  await page.getByLabel("Filter product brand").selectOption("Field");
  await expect(page.locator("article")).toHaveCount(1);
  await expect(
    page.getByRole("heading", {
      name: "Sona Masoori rice · alternative brand",
      exact: true,
    }),
  ).toBeVisible();
  await page
    .getByRole("textbox", { name: "Search products" })
    .fill("no-such-wholesale-product");
  await expect(
    page.getByText("No matching products in your delivery area.", {
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Next products" }),
  ).toBeDisabled();
  await page.context().close();
});

test("buyer compares prices and revisions, then rejects a proposal without purchasing", async ({
  browser,
}) => {
  const buyer = await login(browser, /Ananya/);
  const seller = await login(browser, /Sree Distributors/);
  const date = new Date(Date.now() + 6 * 86400000).toISOString().slice(0, 10);
  const buying = await post(buyer, "/api/v1/procurement/requests", {
    product_id: "rice-sona",
    zone_id: "south-zone",
    dispatch_date: date,
    quantity_min: 30,
    quantity_max: 30,
    ceiling_minor: 170,
  });
  const base = {
    request_id: buying.id,
    product_id: "rice-sona",
    quantity_min: 30,
    quantity_max: 30,
    expires_in_hours: 24,
  };
  await post(seller, "/api/v1/offers", {
    ...base,
    unit_price_minor: 155,
    note: "Higher comparison proposal",
  });
  const low = await post(seller, "/api/v1/offers", {
    ...base,
    unit_price_minor: 150,
    note: "Lower comparison proposal",
  });
  await buyer.goto("/retailer/offers");
  await buyer.getByLabel("Comparison request").selectOption(buying.id);
  await buyer.getByLabel("Sort commercial offers").selectOption("price");
  const table = buyer.getByRole("table", {
    name: "Commercial offer comparison",
  });
  await expect(table.getByRole("row")).toHaveCount(3);
  await expect(table.getByRole("row").nth(1)).toContainText("$1.50");
  await expect(table.getByRole("row").nth(2)).toContainText("$1.55");
  await buyer.getByLabel(`View revisions for ${low.id}`).click();
  await expect(
    buyer.getByRole("heading", { name: "Offer revision history" }),
  ).toBeVisible();
  await expect(
    buyer.getByText(/Version 1 · SUBMITTED when proposed/),
  ).toBeVisible();
  buyer.once("dialog", (d) => d.accept());
  await buyer
    .locator(`#offer-${low.id}`)
    .getByRole("button", { name: "Reject offer · version 1" })
    .click();
  await expect(
    buyer.locator(`#offer-${low.id}`).getByText("REJECTED", { exact: true }),
  ).toBeVisible();
  await buyer
    .getByLabel("Filter commercial offer state")
    .selectOption("REJECTED");
  await expect(table.getByRole("row")).toHaveCount(2);
  const workspace = await (await buyer.request.get("/api/v1/workspace")).json();
  expect(
    workspace.orders.some(
      (o: { pool_id: string }) => o.pool_id === buying.pool_id,
    ),
  ).toBeFalsy();
  await buyer.context().close();
  await seller.context().close();
});
