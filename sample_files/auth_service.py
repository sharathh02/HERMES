"""
Hermes Authentication Service
Provides secure token generation, verification, and role-based access control.
"""

import hashlib
import hmac
import time
from typing import Dict, Any, Optional, Set


class TokenManager:
    """Handles signed token creation, expiration checks, and cryptographic verification."""

    def __init__(self, secret_key: str, default_ttl_seconds: int = 3600):
        """
        Initialize the TokenManager with a secret key.

        Args:
            secret_key: Secret used to compute HMAC signatures.
            default_ttl_seconds: Token validity duration in seconds (defaults to 1 hour).
        """
        self.secret_key = secret_key.encode("utf-8")
        self.default_ttl = default_ttl_seconds
        self._revocation_list: Set[str] = set()

    def generate_token(self, user_id: str, role: str = "viewer") -> str:
        """
        Generate a signed, timestamped auth token for a user.

        Args:
            user_id: Unique user identifier.
            role: Assigned authorization role.

        Returns:
            Colon-separated token string (user_id:expiry:signature).
        """
        expiry = int(time.time()) + self.default_ttl
        payload = f"{user_id}:{role}:{expiry}"
        signature = hmac.new(self.secret_key, payload.encode("utf-8"), hashlib.sha256).hexdigest()
        return f"{payload}:{signature}"

    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Verify signature and freshness of a token string.

        Args:
            token: The raw token string to validate.

        Returns:
            Dictionary with user_id and role if valid, None otherwise.
        """
        if not token or token in self._revocation_list:
            return None

        parts = token.split(":")
        if len(parts) != 4:
            return None

        user_id, role, expiry_str, received_sig = parts
        try:
            expiry = int(expiry_str)
        except ValueError:
            return None

        if time.time() > expiry:
            return None

        expected_payload = f"{user_id}:{role}:{expiry_str}"
        expected_sig = hmac.new(self.secret_key, expected_payload.encode("utf-8"), hashlib.sha256).hexdigest()

        if not hmac.compare_digest(received_sig, expected_sig):
            return None

        return {"user_id": user_id, "role": role, "expires_at": expiry}

    def revoke_token(self, token: str) -> bool:
        """
        Explicitly invalidate an active token before expiration.

        Args:
            token: Token to add to revocation list.

        Returns:
            True if revoked successfully.
        """
        self._revocation_list.add(token)
        return True
