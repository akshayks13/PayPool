import { test, expect } from "@playwright/test";

test("admin removes a role with confirmation and searches paginated audit events", async ({
  page,
}) => {
  await page.goto("/login");
  await page.getByRole("button", { name: /PayPool Operations/ }).click();
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).not.toHaveURL(/login/);
  const session = await (await page.request.get("/api/v1/me")).json();
  for (let i = 0; i < 22; i++) {
    const response = await page.request.post(
      "/api/v1/admin/users/buyer-a/roles",
      {
        data: { role: "RETAILER" },
        headers: { "X-CSRF-Token": session.csrf },
      },
    );
    expect(response.ok()).toBeTruthy();
  }
  await page.goto("/admin/users");
  page.once("dialog", (dialog) => dialog.accept());
  await page
    .getByRole("button", {
      name: "Remove RETAILER from Ananya · GreenMart",
      exact: true,
    })
    .click();
  await expect(
    page.getByRole("button", {
      name: "Remove RETAILER from Ananya · GreenMart",
      exact: true,
    }),
  ).toHaveCount(0);
  page.once("dialog", (dialog) => dialog.accept());
  await page
    .getByLabel("Grant role to Ananya · GreenMart")
    .selectOption("RETAILER");
  await expect(
    page.getByRole("button", {
      name: "Remove RETAILER from Ananya · GreenMart",
      exact: true,
    }),
  ).toBeVisible();
  await page.getByLabel("Search audit events").fill("ROLE_GRANTED");
  await expect(
    page.getByText("23 events · Page 1 of 2", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Next events" }).click();
  await expect(
    page.getByText("23 events · Page 2 of 2", { exact: true }),
  ).toBeVisible();
  await page.getByLabel("Search audit events").fill("ROLE_REVOKED");
  await expect(
    page.getByText("1 events · Page 1 of 1", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Next events" }),
  ).toBeDisabled();
  await page.getByLabel("Search audit events").fill("no-such-audit-event");
  await expect(
    page.getByText("No matching activity.", { exact: true }),
  ).toBeVisible();
});

test("clarification keeps the original buying requirements and reset starts fresh", async ({
  page,
}) => {
  await page.goto("/login");
  await page.getByRole("button", { name: /Ananya/ }).click();
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).not.toHaveURL(/login/);
  await page.goto("/retailer/procurement");
  const input = page.getByRole("textbox", { name: "Buying request" });
  const compare = page.getByRole("button", { name: "Compare supplier offers" });
  await input.fill("I need Sona Masoori rice");
  await compare.click();
  await expect(
    page.getByText(
      "What is the delivery date? Please provide it as YYYY-MM-DD.",
      { exact: true },
    ),
  ).toBeVisible();
  await expect(input).toHaveValue("");
  const date = new Date(Date.now() + 86400000).toISOString().slice(0, 10);
  await input.fill(`30 kg by ${date}, landed price below USD 1.70/kg`);
  const response = page.waitForResponse(
    (r) =>
      r.url().endsWith("/api/v1/procurement/discover") &&
      r.request().method() === "POST",
  );
  await compare.click();
  const discovery = await (await response).json();
  expect(discovery.intent.product_description).toBe("Sona Masoori rice");
  expect(Number(discovery.intent.quantity)).toBe(30);
  expect(discovery.intent.delivery_date).toBe(date);
  expect(discovery.intent.price_ceiling_per_unit_minor).toBe(170);
  expect(discovery.intent.clarification_questions).toEqual([]);
  await expect(
    page.getByRole("button", { name: "Review product & create request" }),
  ).toHaveCount(2);
  await page.getByRole("button", { name: "Start a new request" }).click();
  await expect(
    page.getByRole("button", { name: "Review product & create request" }),
  ).toHaveCount(0);
  await input.fill("I need 20 kg Basmati rice");
  const fresh = page.waitForResponse(
    (r) =>
      r.url().endsWith("/api/v1/procurement/discover") &&
      r.request().method() === "POST",
  );
  await compare.click();
  expect((await fresh).request().postDataJSON().message).toBe(
    "I need 20 kg Basmati rice",
  );
});
