# Integration adapters

This boundary will hold provider-specific implementations for PayPal Identity,
PayPal Orders/webhooks, Braintree (only if approved for ACP), Elasticsearch,
and the selected LLM provider. Domain modules depend on provider-neutral ports,
not adapter implementations.
