"""
Tests for Meta Data Deletion Callback — Priority 1 implementation.

Run with:
    python manage.py test AdminApp.tests_meta_deletion --verbosity=2

Uses Django's test runner (in-memory SQLite per settings.py test override).
No real Facebook credentials, signed requests are crafted with a test secret.
"""
import base64
import hashlib
import hmac as hmac_lib
import json
import threading
import uuid
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone

from AdminApp.models import (
    Company,
    MetaDeletionRequest,
    MetaIntegration,
    MetaPage,
    Lead,
    Staff,
)

# ── Helpers ────────────────────────────────────────────────────────────────────

TEST_APP_SECRET = "test_app_secret_never_used_in_production"
CALLBACK_URL = "/api/admin/integrations/meta/data-deletion/"
STATUS_URL = "/api/admin/integrations/meta/deletion-status/"


def _make_signed_request(payload_dict, app_secret=TEST_APP_SECRET):
    """
    Build a valid Meta-style signed_request string using the given payload
    and app secret.

    Format: base64url(HMAC-SHA256(encoded_payload, secret)).encoded_payload
    """
    payload_json = json.dumps(payload_dict).encode("utf-8")
    encoded_payload = (
        base64.urlsafe_b64encode(payload_json).rstrip(b"=").decode("utf-8")
    )
    sig = hmac_lib.new(
        key=app_secret.encode("utf-8"),
        msg=encoded_payload.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    encoded_sig = base64.urlsafe_b64encode(sig).rstrip(b"=").decode("utf-8")
    return f"{encoded_sig}.{encoded_payload}"


def _make_company_and_integration(
    fb_user_id="111111111",
    company_name="Test Company",
    email="test@example.com",
):
    """Create a Company + MetaIntegration fixture pair."""
    user = User.objects.create_user(
        username=email, password="testpass", email=email
    )
    company = Company.objects.create(name=company_name, email=email)
    staff = Staff.objects.create(
        user=user,
        company=company,
        full_name="Test Admin",
        role="admin",
        email=email,
    )
    integration = MetaIntegration.objects.create(
        company=company,
        meta_user_id=fb_user_id,
        access_token="dummy_access_token",
        is_active=True,
    )
    return company, integration, staff


# ── Test Cases ─────────────────────────────────────────────────────────────────


@override_settings(
    META_APP_SECRET=TEST_APP_SECRET,
    BACKEND_BASE_URL="https://crm-backend-ejfr.onrender.com",
)
class MetaDataDeletionCallbackTest(TestCase):
    """Tests for POST /api/admin/integrations/meta/data-deletion/"""

    # ── 1. Valid signed_request ────────────────────────────────────────────────

    def test_valid_signed_request_no_matching_integration(self):
        """
        A correctly signed request for a user with no MetaIntegration should
        return 200 with confirmation_code and status_url, and create a
        MetaDeletionRequest with status='not_found'.
        """
        signed_req = _make_signed_request({"user_id": "999999999"})
        resp = self.client.post(
            CALLBACK_URL, data={"signed_request": signed_req}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("confirmation_code", data)
        self.assertIn("url", data)
        self.assertIn(data["confirmation_code"], data["url"])

        record = MetaDeletionRequest.objects.get(
            confirmation_code=data["confirmation_code"]
        )
        self.assertEqual(record.status, MetaDeletionRequest.STATUS_NOT_FOUND)
        self.assertEqual(record.facebook_user_id, "999999999")
        self.assertIsNone(record.company)
        self.assertIsNotNone(record.completed_at)

    def test_valid_signed_request_with_matching_integration(self):
        """
        A correctly signed request for a user whose MetaIntegration exists
        should delete that MetaIntegration (and cascade MetaPage),
        create a MetaDeletionRequest with status='completed'.
        """
        company, integration, _ = _make_company_and_integration(
            fb_user_id="222222222"
        )
        # Add a MetaPage so we can verify CASCADE deletion.
        page = MetaPage.objects.create(
            company=company,
            meta_integration=integration,
            page_id="PAGE_123",
            page_name="Test Page",
        )

        signed_req = _make_signed_request({"user_id": "222222222"})
        resp = self.client.post(
            CALLBACK_URL, data={"signed_request": signed_req}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("confirmation_code", data)

        record = MetaDeletionRequest.objects.get(
            confirmation_code=data["confirmation_code"]
        )
        self.assertEqual(record.status, MetaDeletionRequest.STATUS_COMPLETED)
        self.assertIsNotNone(record.completed_at)

        # MetaIntegration must be deleted.
        self.assertFalse(
            MetaIntegration.objects.filter(pk=integration.pk).exists()
        )
        # MetaPage must be cascade-deleted.
        self.assertFalse(MetaPage.objects.filter(pk=page.pk).exists())

    def test_valid_signed_request_leads_are_not_deleted(self):
        """
        CRITICAL: Lead records belonging to the matched company must NOT be
        deleted.  The facebook_user_id identifies the CRM admin who connected
        the integration, not the end-users who submitted the Lead Ads forms.
        """
        company, integration, _ = _make_company_and_integration(
            fb_user_id="333333333"
        )
        lead = Lead.objects.create(
            company=company,
            full_name="Customer From Ads",
            lead_source="Facebook Ads",
            meta_lead_id="lead_abc123",
        )

        signed_req = _make_signed_request({"user_id": "333333333"})
        resp = self.client.post(
            CALLBACK_URL, data={"signed_request": signed_req}
        )
        self.assertEqual(resp.status_code, 200)

        # The lead must still exist.
        self.assertTrue(Lead.objects.filter(pk=lead.pk).exists())

    # ── 2. Invalid signature ───────────────────────────────────────────────────

    def test_invalid_signature_returns_403(self):
        """
        A signed_request with a valid payload but wrong HMAC should return 403.
        """
        signed_req = _make_signed_request(
            {"user_id": "444444444"}, app_secret="wrong_secret"
        )
        resp = self.client.post(
            CALLBACK_URL, data={"signed_request": signed_req}
        )
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()["error"], "signature_mismatch")
        # No deletion record should be created.
        self.assertFalse(
            MetaDeletionRequest.objects.filter(facebook_user_id="444444444").exists()
        )

    # ── 3. Malformed signed_request ───────────────────────────────────────────

    def test_missing_signed_request_field_returns_400(self):
        """POST with no signed_request field should return 400."""
        resp = self.client.post(CALLBACK_URL, data={})
        self.assertEqual(resp.status_code, 400)

    def test_signed_request_missing_dot_separator(self):
        """A signed_request with no '.' separator should return 400."""
        resp = self.client.post(
            CALLBACK_URL, data={"signed_request": "nodothere"}
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["error"], "malformed_signed_request")

    def test_signed_request_invalid_base64_payload(self):
        """A payload part that is not valid base64url should return 400."""
        resp = self.client.post(
            CALLBACK_URL, data={"signed_request": "aGVsbG8=.!!!not-base64!!!"}
        )
        self.assertEqual(resp.status_code, 400)

    def test_signed_request_invalid_json_payload(self):
        """
        A correctly signed but non-JSON payload should return 400.
        """
        raw_payload = b"this is not json"
        encoded_payload = (
            base64.urlsafe_b64encode(raw_payload).rstrip(b"=").decode("utf-8")
        )
        sig = hmac_lib.new(
            key=TEST_APP_SECRET.encode("utf-8"),
            msg=encoded_payload.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        encoded_sig = base64.urlsafe_b64encode(sig).rstrip(b"=").decode("utf-8")
        signed_req = f"{encoded_sig}.{encoded_payload}"
        resp = self.client.post(
            CALLBACK_URL, data={"signed_request": signed_req}
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["error"], "invalid_payload_json")

    # ── 4. Missing META_APP_SECRET ─────────────────────────────────────────────

    @override_settings(META_APP_SECRET=None)
    def test_missing_app_secret_returns_503(self):
        """
        If META_APP_SECRET is not configured, the callback must refuse the
        request with 503 rather than accepting an unverified payload.
        """
        signed_req = _make_signed_request({"user_id": "555555555"})
        resp = self.client.post(
            CALLBACK_URL, data={"signed_request": signed_req}
        )
        self.assertEqual(resp.status_code, 503)
        # No deletion record should be created.
        self.assertFalse(
            MetaDeletionRequest.objects.filter(facebook_user_id="555555555").exists()
        )

    @override_settings(META_APP_SECRET="")
    def test_empty_app_secret_returns_503(self):
        """Empty string META_APP_SECRET must also be treated as missing."""
        signed_req = _make_signed_request(
            {"user_id": "666666666"}, app_secret=""
        )
        resp = self.client.post(
            CALLBACK_URL, data={"signed_request": signed_req}
        )
        self.assertEqual(resp.status_code, 503)

    # ── 5. Missing or invalid Facebook user_id in payload ─────────────────────

    def test_missing_user_id_in_payload_returns_400(self):
        """
        A correctly signed payload that does not contain 'user_id' should
        return 400.
        """
        signed_req = _make_signed_request({"algorithm": "HMAC-SHA256"})
        resp = self.client.post(
            CALLBACK_URL, data={"signed_request": signed_req}
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["error"], "missing_user_id_in_payload")

    def test_empty_user_id_returns_400(self):
        """An empty string user_id should return 400."""
        signed_req = _make_signed_request({"user_id": ""})
        resp = self.client.post(
            CALLBACK_URL, data={"signed_request": signed_req}
        )
        self.assertEqual(resp.status_code, 400)

    # ── 6. Duplicate callback / retry (idempotency) ────────────────────────────

    def test_duplicate_callback_returns_existing_code(self):
        """
        Sending the same signed_request twice (or a retry) must return the
        same confirmation_code as the first request and must NOT create a
        second MetaDeletionRequest row.
        """
        signed_req = _make_signed_request({"user_id": "777777777"})

        resp1 = self.client.post(
            CALLBACK_URL, data={"signed_request": signed_req}
        )
        self.assertEqual(resp1.status_code, 200)
        code1 = resp1.json()["confirmation_code"]

        resp2 = self.client.post(
            CALLBACK_URL, data={"signed_request": signed_req}
        )
        self.assertEqual(resp2.status_code, 200)
        code2 = resp2.json()["confirmation_code"]

        # Same confirmation code returned.
        self.assertEqual(code1, code2)
        # Only one DB record.
        self.assertEqual(
            MetaDeletionRequest.objects.filter(facebook_user_id="777777777").count(),
            1,
        )

    # ── 7. Unknown confirmation code on status endpoint ────────────────────────

    def test_status_unknown_code_returns_404(self):
        """A valid UUID that doesn't match any record must return 404."""
        resp = self.client.get(STATUS_URL, {"code": str(uuid.uuid4())})
        self.assertEqual(resp.status_code, 404)

    def test_status_invalid_uuid_returns_400(self):
        """A non-UUID code parameter must return 400."""
        resp = self.client.get(STATUS_URL, {"code": "not-a-uuid"})
        self.assertEqual(resp.status_code, 400)

    def test_status_missing_code_returns_400(self):
        """Missing 'code' query parameter must return 400."""
        resp = self.client.get(STATUS_URL)
        self.assertEqual(resp.status_code, 400)

    # ── 8. Public deletion status endpoint ────────────────────────────────────

    def test_status_returns_correct_fields(self):
        """
        Status endpoint must return confirmation_code, status, requested_at,
        completed_at; and must NOT expose facebook_user_id, company,
        or notes.
        """
        record = MetaDeletionRequest.objects.create(
            facebook_user_id="888888888",
            status=MetaDeletionRequest.STATUS_COMPLETED,
            notes="Some internal notes — must not be exposed.",
            completed_at=timezone.now(),
        )
        resp = self.client.get(
            STATUS_URL, {"code": str(record.confirmation_code)}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        # Required fields.
        self.assertIn("confirmation_code", data)
        self.assertIn("status", data)
        self.assertIn("requested_at", data)
        self.assertIn("completed_at", data)
        self.assertEqual(data["status"], MetaDeletionRequest.STATUS_COMPLETED)

        # Sensitive fields must NOT be present.
        self.assertNotIn("facebook_user_id", data)
        self.assertNotIn("company", data)
        self.assertNotIn("notes", data)

    # ── 9. Company isolation — unrelated leads are NOT deleted ─────────────────

    def test_deletion_does_not_affect_other_company_integrations(self):
        """
        Deleting one company's MetaIntegration must not affect integrations
        belonging to a different company, even if they share the same page.
        """
        company_a, integration_a, _ = _make_company_and_integration(
            fb_user_id="ADMIN_A", company_name="Company A", email="a@example.com"
        )
        company_b, integration_b, _ = _make_company_and_integration(
            fb_user_id="ADMIN_B", company_name="Company B", email="b@example.com"
        )

        # Only delete for ADMIN_A.
        signed_req = _make_signed_request({"user_id": "ADMIN_A"})
        resp = self.client.post(
            CALLBACK_URL, data={"signed_request": signed_req}
        )
        self.assertEqual(resp.status_code, 200)

        # Integration A is gone.
        self.assertFalse(
            MetaIntegration.objects.filter(pk=integration_a.pk).exists()
        )
        # Integration B must be untouched.
        self.assertTrue(
            MetaIntegration.objects.filter(pk=integration_b.pk).exists()
        )

    # ── 10. Response format matches Meta's specification ──────────────────────

    def test_response_body_format(self):
        """
        Response must be JSON with 'url' and 'confirmation_code' at top level.
        The 'url' must contain the confirmation_code.
        The 'url' must point to the public deletion-status endpoint.
        """
        signed_req = _make_signed_request({"user_id": "RESP_FORMAT_TEST"})
        resp = self.client.post(
            CALLBACK_URL, data={"signed_request": signed_req}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertIn("url", data)
        self.assertIn("confirmation_code", data)

        # URL must embed the confirmation code.
        self.assertIn(data["confirmation_code"], data["url"])

        # URL must include the status endpoint path.
        self.assertIn("deletion-status", data["url"])

        # URL must use the configured BACKEND_BASE_URL.
        self.assertIn(
            "https://crm-backend-ejfr.onrender.com", data["url"]
        )

    # ── 11. Non-dict JSON payloads ────────────────────────────────────────────

    def test_signed_request_json_primitive_returns_400(self):
        """
        JSON payloads that decode to non-dict primitives (int, list, str, bool)
        must return 400 invalid_payload_json rather than raising AttributeError.
        """
        for primitive_val in [12345, ["item1", "item2"], "just_a_string", True]:
            signed_req = _make_signed_request(primitive_val)
            resp = self.client.post(
                CALLBACK_URL, data={"signed_request": signed_req}
            )
            self.assertEqual(resp.status_code, 400, f"Failed for {primitive_val}")
            self.assertEqual(resp.json()["error"], "invalid_payload_json")

    # ── 12. Transaction failure persistence (STATUS_ERROR) ───────────────────

    def test_processing_failure_persists_status_error(self):
        """
        If _process_deletion_for_user raises an unhandled exception, the
        MetaDeletionRequest must NOT be erased by the rollback. It must be
        persisted with status='error' so it can be audited and queried.
        """
        with patch("AdminApp.views._process_deletion_for_user") as mock_proc:
            mock_proc.side_effect = RuntimeError("Simulated database timeout")

            signed_req = _make_signed_request({"user_id": "ERROR_USER_1"})
            resp = self.client.post(
                CALLBACK_URL, data={"signed_request": signed_req}
            )
            self.assertEqual(resp.status_code, 500)
            self.assertEqual(resp.json()["error"], "server_error")

            # Record must exist in database with STATUS_ERROR
            record = MetaDeletionRequest.objects.filter(
                facebook_user_id="ERROR_USER_1"
            ).first()
            self.assertIsNotNone(record)
            self.assertEqual(record.status, MetaDeletionRequest.STATUS_ERROR)
            self.assertIn("Processing failed", record.notes)
            self.assertIsNotNone(record.completed_at)

            # Public status endpoint must query the error record successfully
            status_resp = self.client.get(
                STATUS_URL, {"code": str(record.confirmation_code)}
            )
            self.assertEqual(status_resp.status_code, 200)
            status_data = status_resp.json()
            self.assertEqual(status_data["status"], "error")
            self.assertEqual(status_data["confirmation_code"], str(record.confirmation_code))

    # ── 13. Retry behavior after error ───────────────────────────────────────

    def test_retry_after_error_succeeds(self):
        """
        If a previous deletion request ended in STATUS_ERROR, a subsequent
        request for the same user should retry processing and update the record
        to STATUS_COMPLETED or STATUS_NOT_FOUND.
        """
        # Create an existing error record
        err_record = MetaDeletionRequest.objects.create(
            facebook_user_id="RETRY_USER_1",
            status=MetaDeletionRequest.STATUS_ERROR,
            notes="Previous failure",
        )
        original_code = err_record.confirmation_code

        # Now send a valid callback
        signed_req = _make_signed_request({"user_id": "RETRY_USER_1"})
        resp = self.client.post(
            CALLBACK_URL, data={"signed_request": signed_req}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        # Reuses the original confirmation code
        self.assertEqual(data["confirmation_code"], str(original_code))

        # Record is now updated to not_found (since no integration exists)
        err_record.refresh_from_db()
        self.assertEqual(err_record.status, MetaDeletionRequest.STATUS_NOT_FOUND)

    # ── 14. Concurrency handling ─────────────────────────────────────────────

    def test_concurrent_callbacks_return_same_code(self):
        """
        Two concurrent callbacks for the same Facebook user should return the
        same confirmation code without creating conflicting deletion records.
        """
        signed_req = _make_signed_request({"user_id": "CONCURRENT_USER_1"})
        results = []

        def worker():
            from django.test import Client
            c = Client()
            r = c.post(CALLBACK_URL, data={"signed_request": signed_req})
            results.append(r)

        t1 = threading.Thread(target=worker)
        t2 = threading.Thread(target=worker)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        self.assertEqual(len(results), 2)
        for r in results:
            self.assertEqual(r.status_code, 200)

        codes = [r.json()["confirmation_code"] for r in results]
        self.assertEqual(codes[0], codes[1])

        # Exactly 1 record in database
        self.assertEqual(
            MetaDeletionRequest.objects.filter(facebook_user_id="CONCURRENT_USER_1").count(),
            1,
        )

    # ── 15. BACKEND_BASE_URL configuration validation ─────────────────────────

    def test_missing_or_invalid_backend_base_url_in_production(self):
        """
        When DEBUG=False, BACKEND_BASE_URL must be configured and start with
        https://. If missing or insecure, the callback must fail closed with 500.
        """
        signed_req = _make_signed_request({"user_id": "BASE_URL_TEST"})

        # Missing base URL in production
        with override_settings(DEBUG=False, BACKEND_BASE_URL=""):
            resp = self.client.post(
                CALLBACK_URL, data={"signed_request": signed_req}
            )
            self.assertEqual(resp.status_code, 500)
            self.assertEqual(resp.json()["error"], "server_configuration_error")

        # Insecure HTTP base URL in production
        with override_settings(DEBUG=False, BACKEND_BASE_URL="http://insecure-domain.com"):
            resp = self.client.post(
                CALLBACK_URL, data={"signed_request": signed_req}
            )
            self.assertEqual(resp.status_code, 500)
            self.assertEqual(resp.json()["error"], "server_configuration_error")

    # ── 16. Webhook unsubscription on Meta Graph API ──────────────────────────

    def test_remote_webhook_unsubscription_success(self):
        """
        Deleting an integration should call DELETE /{page_id}/subscribed_apps
        for all associated MetaPage rows.
        """
        company, integration, _ = _make_company_and_integration(
            fb_user_id="PAGE_UNSUB_USER"
        )
        page = MetaPage.objects.create(
            company=company,
            meta_integration=integration,
            page_id="PAGE_999",
            page_name="Unsub Test Page",
            page_access_token="page_token_abc",
        )

        with patch("AdminApp.views.requests.delete") as mock_del:
            mock_del.return_value = MagicMock(json=lambda: {"success": True})

            signed_req = _make_signed_request({"user_id": "PAGE_UNSUB_USER"})
            resp = self.client.post(
                CALLBACK_URL, data={"signed_request": signed_req}
            )
            self.assertEqual(resp.status_code, 200)

            # requests.delete should have been called for PAGE_999
            mock_del.assert_called_once()
            call_url = mock_del.call_args[0][0]
            self.assertIn("PAGE_999/subscribed_apps", call_url)

            # Record notes mention unsubscription
            record = MetaDeletionRequest.objects.get(facebook_user_id="PAGE_UNSUB_USER")
            self.assertIn("Page PAGE_999: unsubscribed", record.notes)

    def test_remote_webhook_unsubscription_api_error_does_not_abort_deletion(self):
        """
        If Meta Graph API returns an error during unsubscription (e.g. token expired),
        the local deletion of MetaIntegration and MetaPage must still succeed.
        """
        company, integration, _ = _make_company_and_integration(
            fb_user_id="PAGE_ERR_USER"
        )
        page = MetaPage.objects.create(
            company=company,
            meta_integration=integration,
            page_id="PAGE_888",
            page_name="Error Page",
            page_access_token="expired_token",
        )

        with patch("AdminApp.views.requests.delete") as mock_del:
            mock_del.return_value = MagicMock(
                json=lambda: {"error": {"code": 190, "message": "Invalid OAuth access token"}}
            )

            signed_req = _make_signed_request({"user_id": "PAGE_ERR_USER"})
            resp = self.client.post(
                CALLBACK_URL, data={"signed_request": signed_req}
            )
            self.assertEqual(resp.status_code, 200)

            # Local MetaIntegration and MetaPage are still deleted
            self.assertFalse(MetaIntegration.objects.filter(pk=integration.pk).exists())
            self.assertFalse(MetaPage.objects.filter(pk=page.pk).exists())

            # Notes record the API error code
            record = MetaDeletionRequest.objects.get(facebook_user_id="PAGE_ERR_USER")
            self.assertIn("api_error_190", record.notes)

    def test_page_token_revoked_code_190_exact_meta_error_message(self):
        """
        Simulate Meta's exact error message when a user has removed/deauthorized
        the application before or during data deletion callback:
        code=190 'Error validating access token: The user has not authorized application ...'
        Verify that local integration and pages are deleted cleanly and final status is 'completed'.
        """
        company, integration, _ = _make_company_and_integration(
            fb_user_id="FB_USER_REVOKED_APP"
        )
        page = MetaPage.objects.create(
            company=company,
            meta_integration=integration,
            page_id="415404014994690",
            page_name="Revoked Page",
            page_access_token="revoked_token_xyz",
        )

        with patch("AdminApp.views.requests.delete") as mock_del:
            mock_del.return_value = MagicMock(
                json=lambda: {
                    "error": {
                        "message": "Error validating access token: The user has not authorized application 1865139438174659.",
                        "type": "OAuthException",
                        "code": 190,
                        "error_subcode": 458,
                    }
                }
            )

            signed_req = _make_signed_request({"user_id": "FB_USER_REVOKED_APP"})
            resp = self.client.post(
                CALLBACK_URL, data={"signed_request": signed_req}
            )
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            code = data["confirmation_code"]

            # Local MetaIntegration and MetaPage are deleted
            self.assertFalse(MetaIntegration.objects.filter(pk=integration.pk).exists())
            self.assertFalse(MetaPage.objects.filter(pk=page.pk).exists())

            # Deletion request status is completed
            record = MetaDeletionRequest.objects.get(confirmation_code=code)
            self.assertEqual(record.status, MetaDeletionRequest.STATUS_COMPLETED)
            self.assertIn("api_error_190", record.notes)

            # Querying the status endpoint confirms completed status
            status_resp = self.client.get(STATUS_URL, {"code": code})
            self.assertEqual(status_resp.status_code, 200)
            self.assertEqual(status_resp.json()["status"], "completed")

    def test_remote_webhook_unsubscription_network_error_does_not_abort_deletion(self):
        """
        If a network timeout occurs while contacting Meta's Graph API, the local
        cleanup must proceed to delete the MetaIntegration and MetaPage.
        """
        import requests
        company, integration, _ = _make_company_and_integration(
            fb_user_id="FB_USER_NET_ERR"
        )
        page = MetaPage.objects.create(
            company=company,
            meta_integration=integration,
            page_id="PAGE_NET_123",
            page_name="Network Page",
            page_access_token="token_net",
        )

        with patch("AdminApp.views.requests.delete") as mock_del:
            mock_del.side_effect = requests.RequestException("Graph API timeout")

            signed_req = _make_signed_request({"user_id": "FB_USER_NET_ERR"})
            resp = self.client.post(
                CALLBACK_URL, data={"signed_request": signed_req}
            )
            self.assertEqual(resp.status_code, 200)

            # Local integration and page deleted
            self.assertFalse(MetaIntegration.objects.filter(pk=integration.pk).exists())
            self.assertFalse(MetaPage.objects.filter(pk=page.pk).exists())

            record = MetaDeletionRequest.objects.get(facebook_user_id="FB_USER_NET_ERR")
            self.assertEqual(record.status, MetaDeletionRequest.STATUS_COMPLETED)
            self.assertIn("network_error", record.notes)

    def test_legacy_single_page_integration_unsubscribes_and_deletes(self):
        """
        Legacy single-page integrations (with page_id on MetaIntegration and no
        MetaPage rows) must still attempt unsubscribe and delete cleanly.
        """
        company, integration, _ = _make_company_and_integration(
            fb_user_id="LEGACY_FB_USER"
        )
        integration.page_id = "LEGACY_PAGE_99"
        integration.page_access_token = "legacy_page_token_99"
        integration.save()

        with patch("AdminApp.views.requests.delete") as mock_del:
            mock_del.return_value = MagicMock(json=lambda: {"success": True})

            signed_req = _make_signed_request({"user_id": "LEGACY_FB_USER"})
            resp = self.client.post(
                CALLBACK_URL, data={"signed_request": signed_req}
            )
            self.assertEqual(resp.status_code, 200)

            # Unsubscribe was called for legacy page
            mock_del.assert_called_once()
            self.assertIn("LEGACY_PAGE_99/subscribed_apps", mock_del.call_args[0][0])

            # Integration deleted
            self.assertFalse(MetaIntegration.objects.filter(pk=integration.pk).exists())

    def test_unknown_facebook_user_id_reports_not_found_on_status_endpoint(self):
        """
        When a verified signed request has an unknown Facebook User ID (no matching
        CRM integration), the callback returns 200 with confirmation code and
        the status endpoint reports status='not_found'.
        """
        signed_req = _make_signed_request({"user_id": "UNKNOWN_FB_USER_777"})
        resp = self.client.post(
            CALLBACK_URL, data={"signed_request": signed_req}
        )
        self.assertEqual(resp.status_code, 200)
        code = resp.json()["confirmation_code"]

        # Status endpoint confirms 'not_found'
        status_resp = self.client.get(STATUS_URL, {"code": code})
        self.assertEqual(status_resp.status_code, 200)
        status_data = status_resp.json()
        self.assertEqual(status_data["status"], "not_found")
        self.assertEqual(status_data["confirmation_code"], code)

    def test_tampered_signature_returns_403_forbidden(self):
        """
        Modifying any byte of the signature must cause HMAC comparison failure
        and return HTTP 403 signature_mismatch.
        """
        valid_signed_req = _make_signed_request({"user_id": "TAMPER_USER"})
        sig_part, payload_part = valid_signed_req.split(".", 1)
        # Flip first character of signature
        tampered_sig = ("A" if sig_part[0] != "A" else "B") + sig_part[1:]
        tampered_req = f"{tampered_sig}.{payload_part}"

        resp = self.client.post(
            CALLBACK_URL, data={"signed_request": tampered_req}
        )
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()["error"], "signature_mismatch")
        self.assertFalse(
            MetaDeletionRequest.objects.filter(facebook_user_id="TAMPER_USER").exists()
        )





@override_settings(
    META_APP_SECRET=TEST_APP_SECRET,
    BACKEND_BASE_URL="https://crm-backend-ejfr.onrender.com",
)
class MetaDeletionStatusPublicAccessTest(TestCase):
    """
    Verify the status endpoint is publicly accessible without any
    CRM JWT token.
    """

    def test_status_accessible_without_auth_header(self):
        """
        The status endpoint must return a non-401 response without an
        Authorization header.
        """
        record = MetaDeletionRequest.objects.create(
            facebook_user_id="PUBLIC_ACCESS_TEST",
            status=MetaDeletionRequest.STATUS_PENDING,
        )
        # Deliberately do NOT set any auth header.
        resp = self.client.get(
            STATUS_URL, {"code": str(record.confirmation_code)}
        )
        self.assertNotEqual(resp.status_code, 401)
        self.assertEqual(resp.status_code, 200)

    def test_callback_accessible_without_auth_header(self):
        """
        The callback endpoint must return a non-401 response without an
        Authorization header (valid signed_request, no JWT).
        """
        signed_req = _make_signed_request({"user_id": "CALLBACK_NO_AUTH"})
        resp = self.client.post(
            CALLBACK_URL, data={"signed_request": signed_req}
        )
        self.assertNotEqual(resp.status_code, 401)
        self.assertIn(resp.status_code, [200])
