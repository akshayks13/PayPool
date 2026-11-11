# Integration adapters

This directory is a historical planning namespace. Running PayPal Orders/webhook
adapters are in `app/platform/payments.py`, Identity in `app/platform/router.py`,
search in `app/platform/search.py`, and model adapters in `app/modules/negotiation`.
Braintree delegated payments are not implemented. See `docs/STATUS.md` for the
actual delivery boundary; this folder does not represent another provider stack.
