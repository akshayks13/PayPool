# PayPool frontend

See the [root README](../README.md) for startup, configuration, current features
and checks. The [scope note](../docs/STATUS.md) lists outstanding account/service
setup and deliberate product bounds.

Sandbox payments use PayPal's official JavaScript SDK popup, backed by the
server's checkout and authorization routes. The app remains on My orders while
the buyer approves. Cancellation, loading failures and an explicit full-page
fallback are handled by `src/components/paypal-checkout.tsx`.

Run `make sandbox` from the repository root for genuine local test payments.
`make demo` always uses the simulator. See [payment flow and verification](../docs/payments.md)
for the walkthrough and focused browser regression checks.
