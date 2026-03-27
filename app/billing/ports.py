"""Ports (interfaces) for the billing domain."""
from typing import Protocol


class PaymentGatewayPort(Protocol):
    """Abstract interface for payment processing."""

    async def create_checkout_session(
        self,
        user_id: str,
        price_id: str,
        **kwargs,
    ) -> str:
        """Create a checkout session. Returns session URL."""
        ...

    async def verify_webhook(self, payload: bytes, signature: str) -> dict:
        """Verify and parse a webhook payload. Returns the event dict."""
        ...
