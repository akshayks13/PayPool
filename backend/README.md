# PayPool backend

See the [root README](../README.md) for startup, configuration, current features
and checks. The [scope note](../docs/STATUS.md) lists outstanding account/service
setup and deliberate product bounds.

For genuine local PayPal Sandbox checkout, run `make sandbox` from the repository
root after privately configuring credentials. Checkout and authorization are
authenticated server operations; only the public SDK client ID is exposed to
the frontend. See [payment flow and verification](../docs/payments.md) for
callbacks, amount checks, webhook configuration and current verification limits.
