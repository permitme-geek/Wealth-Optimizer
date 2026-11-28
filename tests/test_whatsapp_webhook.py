import hashlib
import hmac
import unittest

from api.whatsapp_webhook import valid_signature


class WhatsAppWebhookTests(unittest.TestCase):
    def test_accepts_valid_meta_signature(self):
        raw = b'{"object":"whatsapp_business_account"}'
        secret = "test-app-secret"
        digest = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
        self.assertTrue(valid_signature(raw, f"sha256={digest}", secret))

    def test_rejects_wrong_or_missing_signature(self):
        self.assertFalse(valid_signature(b"body", "sha256=bad", "secret"))
        self.assertFalse(valid_signature(b"body", "", "secret"))
        self.assertFalse(valid_signature(b"body", "sha256=bad", ""))


if __name__ == "__main__":
    unittest.main()
