import { test, expect, type Page } from "@playwright/test";

async function setup(page: Page, failSdk = false, authorizationFails = false) {
  const order = {
    id: "popup-test-order",
    pool_id: "popup-pool",
    seller_id: "seller-demo",
    buyer_id: "buyer-a",
    product_id: "rice-sona",
    quantity: 30,
    currency: "USD",
    total_minor: 4900,
    freight_minor: 400,
    status: "APPROVED",
    payment_status: "NOT_STARTED",
    provider: "paypal_sandbox",
    payment_error: "",
    provider_order_id: "",
    approval_url: "",
    refunded_minor: 0,
  };
  const calls = { checkout: 0, authorize: 0 };
  await page.route("**/api/v1/config", async (route) => {
    const response = await route.fetch();
    await route.fulfill({
      response,
      json: { ...(await response.json()), paypal_client_id: "test-sdk-client" },
    });
  });
  await page.route("**/api/v1/workspace", async (route) => {
    const response = await route.fetch();
    await route.fulfill({
      response,
      json: {
        ...(await response.json()),
        payment_provider: "paypal_sandbox",
        orders: [order],
      },
    });
  });
  await page.route(
    "**/api/v1/orders/popup-test-order/checkout",
    async (route) => {
      calls.checkout++;
      Object.assign(order, {
        payment_status: "CREATED",
        provider_order_id: "PAYPAL-POPUP-TEST",
        approval_url: "/paypal-fullpage-test",
      });
      await route.fulfill({ json: order });
    },
  );
  await page.route(
    "**/api/v1/orders/popup-test-order/authorize",
    async (route) => {
      calls.authorize++;
      order.payment_status = authorizationFails
        ? "REQUIRES_RECONCILIATION"
        : "AUTHORIZED";
      order.payment_error = authorizationFails
        ? "Provider authorization needs reconciliation"
        : "";
      await route.fulfill({ json: order });
    },
  );
  await page.route(
    "https://www.sandbox.paypal.com/sdk/js?**",
    async (route) => {
      if (failSdk) return route.abort();
      expect(new URL(route.request().url()).searchParams.get("intent")).toBe(
        "authorize",
      );
      await route.fulfill({
        contentType: "application/javascript",
        body: `
      window[document.currentScript.getAttribute('data-namespace')] = {
        version: 'test', Buttons(options) {
          let button;
          return {
            isEligible: () => true,
            close: async () => { button?.remove(); },
            render: async (container) => {
              button = document.createElement('button'); button.textContent = 'PayPal test button';
              button.onclick = async () => {
                const popup = window.open('about:blank', 'paypal-test');
                const id = await options.createOrder();
                const approve = popup.document.createElement('button'); approve.textContent = 'Approve test purchase';
                approve.onclick = async () => { try { await options.onApprove({ orderID: id }); } catch (error) { options.onError(error); } finally { popup.close(); } };
                const cancel = popup.document.createElement('button'); cancel.textContent = 'Cancel test purchase';
                cancel.onclick = () => { options.onCancel(); popup.close(); };
                popup.document.body.append(approve, cancel);
              };
              container.append(button);
            }
          };
        }
      };`,
      });
    },
  );
  await page.goto("/login");
  await page.getByRole("button", { name: /Ananya/ }).click();
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).not.toHaveURL(/login/);
  await page.goto("/retailer/orders");
  return calls;
}

test("popup cancellation is retryable and approval authorizes without leaving orders", async ({
  page,
}) => {
  const calls = await setup(page);
  const firstPopup = page.waitForEvent("popup");
  await page.getByRole("button", { name: "PayPal test button" }).click();
  const canceled = await firstPopup;
  await canceled.getByRole("button", { name: "Cancel test purchase" }).click();
  await expect(
    page.getByText("Checkout closed. You can try again when ready."),
  ).toBeVisible();
  expect(calls.authorize).toBe(0);
  await expect(page).toHaveURL(/\/retailer\/orders$/);
  const secondPopup = page.waitForEvent("popup");
  await page.getByRole("button", { name: "PayPal test button" }).click();
  const approved = await secondPopup;
  await approved.getByRole("button", { name: "Approve test purchase" }).click();
  await expect(page.getByText("AUTHORIZED", { exact: true })).toBeVisible();
  await expect(page).toHaveURL(/\/retailer\/orders$/);
  expect(calls.checkout).toBe(2);
  expect(calls.authorize).toBe(1);
});

test("SDK failure keeps explicit full-page checkout available", async ({
  page,
}) => {
  const calls = await setup(page, true);
  await expect(
    page.getByText("Could not load PayPal.", { exact: false }),
  ).toBeVisible();
  await page.getByText("Having trouble opening PayPal?").click();
  await page.getByRole("button", { name: "Use full-page checkout" }).click();
  await expect(page).toHaveURL(/paypal-fullpage-test/);
  expect(calls.checkout).toBe(1);
  expect(calls.authorize).toBe(0);
});

test("failed server authorization is never shown as authorized", async ({
  page,
}) => {
  const calls = await setup(page, false, true);
  const opened = page.waitForEvent("popup");
  await page.getByRole("button", { name: "PayPal test button" }).click();
  const popup = await opened;
  await popup.getByRole("button", { name: "Approve test purchase" }).click();
  await expect(
    page.getByText("REQUIRES RECONCILIATION", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText("AUTHORIZED", { exact: true })).toHaveCount(0);
  expect(calls.authorize).toBe(1);
});
