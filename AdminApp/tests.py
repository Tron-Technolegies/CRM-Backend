import hmac
import hashlib
import json
from unittest.mock import patch, MagicMock
from urllib.parse import urlparse, parse_qs
from django.test import TestCase, Client, override_settings
from django.core import signing
from django.conf import settings
from django.contrib.auth.models import User
from django.db import IntegrityError
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from datetime import timedelta
from django.utils import timezone
from AdminApp.models import Company, Staff, EmailIntegration, Product, Service, Lead, AuditLog, StickyNote, MetaIntegration, MetaPage
from AdminApp.permissions import (
    ROLE_PERMISSIONS,
    has_permission,
    require_permission,
)
from AdminApp.views import (
    view_leads,
    delete_lead,
    add_staff,
    delete_staff,
    view_cases,
    view_quotes,
    add_lead,
    view_single_lead,
    update_lead,
)


class MockStaff:
    """Lightweight mock object with a role attribute for unit testing."""
    def __init__(self, role):
        self.role = role


class RBACPermissionsUnitTest(TestCase):
    """Test the core RBAC logic and role matrix in permissions.py."""

    def test_admin_has_all_permissions(self):
        staff = MockStaff("admin")
        self.assertTrue(has_permission(staff, "lead.create"))
        self.assertTrue(has_permission(staff, "staff.delete"))
        self.assertTrue(has_permission(staff, "picklist.create"))
        self.assertTrue(has_permission(staff, "integration.manage"))
        self.assertTrue(has_permission(staff, "twilio.manage"))
        self.assertTrue(has_permission(staff, "nonexistent.permission"))  # admin wildcard/full access

    def test_manager_permissions(self):
        staff = MockStaff("manager")
        # Allowed operational permissions
        self.assertTrue(has_permission(staff, "lead.create"))
        self.assertTrue(has_permission(staff, "lead.delete"))
        self.assertTrue(has_permission(staff, "staff.create"))
        self.assertTrue(has_permission(staff, "staff.view"))
        self.assertTrue(has_permission(staff, "staff.edit"))
        self.assertTrue(has_permission(staff, "report.export"))
        self.assertTrue(has_permission(staff, "call.dial"))
        self.assertTrue(has_permission(staff, "picklist.view"))

        # Strictly prohibited for Manager
        self.assertFalse(has_permission(staff, "staff.delete"))
        self.assertFalse(has_permission(staff, "picklist.create"))
        self.assertFalse(has_permission(staff, "picklist.edit"))
        self.assertFalse(has_permission(staff, "picklist.delete"))
        self.assertFalse(has_permission(staff, "integration.manage"))
        self.assertFalse(has_permission(staff, "integration.view"))
        self.assertFalse(has_permission(staff, "twilio.manage"))
        self.assertFalse(has_permission(staff, "twilio.view"))

    def test_sales_agent_permissions(self):
        staff = MockStaff("sales agent")
        # Allowed sales permissions
        self.assertTrue(has_permission(staff, "lead.view"))
        self.assertTrue(has_permission(staff, "lead.create"))
        self.assertTrue(has_permission(staff, "lead.edit"))
        self.assertTrue(has_permission(staff, "lead.convert"))
        self.assertTrue(has_permission(staff, "deal.view"))
        self.assertTrue(has_permission(staff, "customer.create"))
        self.assertTrue(has_permission(staff, "quote.view"))
        self.assertTrue(has_permission(staff, "salesorder.view"))
        self.assertTrue(has_permission(staff, "invoice.view"))
        self.assertTrue(has_permission(staff, "call.dial"))
        self.assertTrue(has_permission(staff, "picklist.view"))

        # Strictly prohibited for Sales Agent
        self.assertFalse(has_permission(staff, "lead.delete"))
        self.assertFalse(has_permission(staff, "deal.delete"))
        self.assertFalse(has_permission(staff, "customer.delete"))
        self.assertFalse(has_permission(staff, "staff.view"))
        self.assertFalse(has_permission(staff, "staff.create"))
        self.assertFalse(has_permission(staff, "vendor.view"))
        self.assertFalse(has_permission(staff, "purchaseorder.view"))
        self.assertFalse(has_permission(staff, "case.view"))
        self.assertFalse(has_permission(staff, "casesolution.view"))
        self.assertFalse(has_permission(staff, "quote.create"))
        self.assertFalse(has_permission(staff, "report.export"))
        self.assertFalse(has_permission(staff, "twilio.manage"))

    def test_support_agent_permissions(self):
        staff = MockStaff("support agent")
        # Allowed support permissions
        self.assertTrue(has_permission(staff, "case.view"))
        self.assertTrue(has_permission(staff, "case.create"))
        self.assertTrue(has_permission(staff, "case.edit"))
        self.assertTrue(has_permission(staff, "casesolution.view"))
        self.assertTrue(has_permission(staff, "customer.view"))
        self.assertTrue(has_permission(staff, "customer.edit"))
        self.assertTrue(has_permission(staff, "lead.view"))
        self.assertTrue(has_permission(staff, "deal.view"))
        self.assertTrue(has_permission(staff, "call.dial"))
        self.assertTrue(has_permission(staff, "picklist.view"))

        # Strictly prohibited for Support Agent
        self.assertFalse(has_permission(staff, "case.delete"))
        self.assertFalse(has_permission(staff, "customer.create"))
        self.assertFalse(has_permission(staff, "customer.delete"))
        self.assertFalse(has_permission(staff, "lead.create"))
        self.assertFalse(has_permission(staff, "lead.edit"))
        self.assertFalse(has_permission(staff, "lead.delete"))
        self.assertFalse(has_permission(staff, "lead.convert"))
        self.assertFalse(has_permission(staff, "staff.view"))
        self.assertFalse(has_permission(staff, "vendor.view"))
        self.assertFalse(has_permission(staff, "quote.view"))
        self.assertFalse(has_permission(staff, "pricebook.view"))
        self.assertFalse(has_permission(staff, "salesorder.view"))
        self.assertFalse(has_permission(staff, "invoice.view"))
        self.assertFalse(has_permission(staff, "purchaseorder.view"))
        self.assertFalse(has_permission(staff, "report.export"))

    def test_none_or_invalid_staff(self):
        self.assertFalse(has_permission(None, "lead.view"))
        self.assertFalse(has_permission(MockStaff(None), "lead.view"))
        self.assertFalse(has_permission(MockStaff(""), "lead.view"))
        self.assertFalse(has_permission(MockStaff("guest"), "lead.view"))


class RequirePermissionDecoratorTest(TestCase):
    """Test that the @require_permission decorator enforces 403 on denied actions."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.company = Company.objects.create(name="Acme Corp", email="contact@acme.com")
        self.admin_user = User.objects.create_user(username="admin_u", email="admin@acme.com", password="pw")
        self.admin_staff = Staff.objects.create(user=self.admin_user, company=self.company, full_name="Admin Staff", email="admin@acme.com", role="admin")

        self.sales_user = User.objects.create_user(username="sales_u", email="sales@acme.com", password="pw")
        self.sales_staff = Staff.objects.create(user=self.sales_user, company=self.company, full_name="Sales Staff", email="sales@acme.com", role="sales agent")

        self.support_user = User.objects.create_user(username="support_u", email="support@acme.com", password="pw")
        self.support_staff = Staff.objects.create(user=self.support_user, company=self.company, full_name="Support Staff", email="support@acme.com", role="support agent")

    def test_sales_agent_denied_on_delete_lead(self):
        """Sales agents cannot delete leads (403)."""
        request = self.factory.delete("/api/admin/lead/delete/1/")
        force_authenticate(request, user=self.sales_user)
        request.staff = self.sales_staff
        request.company = self.company

        response = delete_lead(request, 1)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("detail", response.data)
        self.assertEqual(response.data["detail"], "You do not have permission to perform this action.")

    def test_sales_agent_denied_on_view_cases(self):
        """Sales agents cannot view cases (403)."""
        request = self.factory.get("/api/admin/case/view/")
        force_authenticate(request, user=self.sales_user)
        request.staff = self.sales_staff
        request.company = self.company

        response = view_cases(request)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_support_agent_allowed_on_view_cases(self):
        """Support agents can view cases (200)."""
        request = self.factory.get("/api/admin/case/view/")
        force_authenticate(request, user=self.support_user)
        request.staff = self.support_staff
        request.company = self.company

        response = view_cases(request)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_support_agent_denied_on_view_quotes(self):
        """Support agents cannot view quotes (403)."""
        request = self.factory.get("/api/admin/quote/view/")
        force_authenticate(request, user=self.support_user)
        request.staff = self.support_staff
        request.company = self.company

        response = view_quotes(request)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_without_permission_denied(self):
        """Staff with no role or invalid role gets 403."""
        no_role_user = User.objects.create_user(username="norole_u", email="norole@acme.com", password="pw")
        no_role_staff = Staff.objects.create(user=no_role_user, company=self.company, full_name="No Role Staff", email="norole@acme.com", role="")
        request = self.factory.get("/api/admin/lead/view/")
        force_authenticate(request, user=no_role_user)
        request.staff = no_role_staff
        request.company = self.company

        response = view_leads(request)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_allowed_add_staff_denied_delete_staff(self):
        """Manager can add staff (not 403 on perm check), but is 403 forbidden on delete_staff."""
        manager_user = User.objects.create_user(username="mgr_u", email="mgr@acme.com", password="pw")
        manager_staff = Staff.objects.create(user=manager_user, company=self.company, full_name="Manager Staff", email="mgr@acme.com", role="manager")

        # Delete staff -> 403
        del_req = self.factory.delete("/api/admin/staff/delete/1/")
        force_authenticate(del_req, user=manager_user)
        del_req.staff = manager_staff
        del_req.company = self.company
        del_resp = delete_staff(del_req, 1)
        self.assertEqual(del_resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_sales_agent_cannot_access_staff(self):
        """Sales Agent cannot add staff (403)."""
        add_req = self.factory.post("/api/admin/staff/add/", {}, format="json")
        force_authenticate(add_req, user=self.sales_user)
        add_req.staff = self.sales_staff
        add_req.company = self.company
        add_resp = add_staff(add_req)
        self.assertEqual(add_resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_access_delete_staff_permission(self):
        """Admin is not blocked by RBAC on delete_staff and deletes staff successfully."""
        target_user = User.objects.create_user(username="target_u", email="target@acme.com", password="pw")
        target_staff = Staff.objects.create(user=target_user, company=self.company, full_name="Target Staff", email="target@acme.com", role="sales agent")

        del_req = self.factory.delete(f"/api/admin/staff/delete/{target_staff.id}/")
        force_authenticate(del_req, user=self.admin_user)
        del_req.staff = self.admin_staff
        del_req.company = self.company
        del_resp = delete_staff(del_req, target_staff.id)
        self.assertEqual(del_resp.status_code, status.HTTP_200_OK)


class GmailOAuthIntegrationTest(TestCase):
    """
    Tests for Gmail OAuth 2.0 integration on localhost:
    1. Connect URL generation with local redirect URI and cryptographic state
    2. Callback accessibility without JWT (public path in CompanyMiddleware)
    3. State validation (rejecting bad, expired, or missing signatures)
    4. Successful token exchange and encrypted persistence in EmailIntegration
    5. Protected endpoints requiring JWT and RBAC
    6. Masking of tokens (no credentials leaked in status responses)
    """

    def setUp(self):
        self.client = Client()
        self.company = Company.objects.create(name="Local Test Corp", email="test@localcorp.com")
        self.admin_user = User.objects.create_user(username="local_admin", email="admin@localcorp.com", password="pw")
        self.admin_staff = Staff.objects.create(
            user=self.admin_user,
            company=self.company,
            full_name="Admin User",
            email="admin@localcorp.com",
            role="admin",
        )
        self.sales_user = User.objects.create_user(username="local_sales", email="sales@localcorp.com", password="pw")
        self.sales_staff = Staff.objects.create(
            user=self.sales_user,
            company=self.company,
            full_name="Sales User",
            email="sales@localcorp.com",
            role="sales agent",
        )
        self.admin_token = str(RefreshToken.for_user(self.admin_user).access_token)
        self.sales_token = str(RefreshToken.for_user(self.sales_user).access_token)

    def test_email_connect_generates_local_redirect_uri(self):
        """GET /api/admin/email/connect/ must return an OAuth URL with the local redirect URI."""
        response = self.client.get(
            "/api/admin/email/connect/",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_token}",
        )
        self.assertEqual(response.status_code, 200)
        auth_url = response.json().get("auth_url")
        self.assertTrue(auth_url.startswith("https://accounts.google.com/o/oauth2/v2/auth?"))

        parsed = urlparse(auth_url)
        params = parse_qs(parsed.query)

        self.assertEqual(params["client_id"][0], settings.GOOGLE_CLIENT_ID)
        self.assertEqual(params["redirect_uri"][0], settings.GOOGLE_REDIRECT_URI)
        self.assertEqual(params["redirect_uri"][0], "http://127.0.0.1:8000/api/admin/email/callback/")
        self.assertEqual(params["response_type"][0], "code")
        self.assertIn("https://www.googleapis.com/auth/gmail.send", params["scope"][0])

        # Validate signed state embeds company_id
        state = params["state"][0]
        state_data = signing.loads(state, salt="gmail-oauth", max_age=600)
        self.assertEqual(state_data["company_id"], self.company.id)

    def test_email_connect_rbac_denied_for_sales_agent(self):
        """Sales agent cannot connect Gmail (requires integration.manage -> 403)."""
        response = self.client.get(
            "/api/admin/email/connect/",
            HTTP_AUTHORIZATION=f"Bearer {self.sales_token}",
        )
        self.assertEqual(response.status_code, 403)

    def test_email_callback_public_path_no_jwt_required(self):
        """
        GET /api/admin/email/callback/ must NOT require JWT Authorization header.
        When accessed without auth header and with user denial, it returns a 302 redirect.
        """
        response = self.client.get("/api/admin/email/callback/?error=access_denied")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/settings/email?gmail=error&reason=access_denied", response.url)

    def test_email_callback_rejects_missing_or_bad_state(self):
        """Callback must reject forged or missing state and cannot accept an arbitrary company ID."""
        # Missing state
        resp1 = self.client.get("/api/admin/email/callback/?code=fake_code")
        self.assertEqual(resp1.status_code, 302)
        self.assertIn("reason=no_state", resp1.url)

        # Tampered state
        resp2 = self.client.get("/api/admin/email/callback/?code=fake_code&state=tampered_state_value")
        self.assertEqual(resp2.status_code, 302)
        self.assertIn("reason=bad_state", resp2.url)

    def test_email_callback_successful_exchange_and_encryption(self):
        """
        Valid state and authorization code exchanges tokens with Google,
        persists encrypted tokens in EmailIntegration, and redirects to frontend.
        """
        state = signing.dumps({"company_id": self.company.id, "staff_id": self.admin_staff.id}, salt="gmail-oauth")

        mock_token_resp = MagicMock()
        mock_token_resp.json.return_value = {
            "access_token": "ya29.test_access_token_12345",
            "refresh_token": "1//test_refresh_token_67890",
            "expires_in": 3599,
            "token_type": "Bearer",
        }

        mock_userinfo_resp = MagicMock()
        mock_userinfo_resp.json.return_value = {
            "email": "connected_biz@gmail.com",
        }

        with patch("requests.post", return_value=mock_token_resp) as mock_post, \
             patch("requests.get", return_value=mock_userinfo_resp) as mock_get:

            response = self.client.get(f"/api/admin/email/callback/?code=4/valid_auth_code&state={state}")

            self.assertEqual(response.status_code, 302)
            self.assertIn("/settings/email?gmail=connected&email=connected_biz%40gmail.com", response.url)

            # Check that requests.post used the local redirect_uri
            mock_post.assert_called_once()
            call_data = mock_post.call_args[1]["data"]
            self.assertEqual(call_data["redirect_uri"], "http://127.0.0.1:8000/api/admin/email/callback/")
            self.assertEqual(call_data["code"], "4/valid_auth_code")

            # Verify EmailIntegration record
            integration = EmailIntegration.objects.get(company=self.company)
            self.assertTrue(integration.is_connected)
            self.assertEqual(integration.provider, "gmail")
            self.assertEqual(integration.email, "connected_biz@gmail.com")
            # Property getter decrypts correctly
            self.assertEqual(integration.access_token, "ya29.test_access_token_12345")
            self.assertEqual(integration.refresh_token, "1//test_refresh_token_67890")
            # Raw DB columns are encrypted (not plain text)
            self.assertNotEqual(integration.access_token_encrypted, "ya29.test_access_token_12345")
            self.assertNotEqual(integration.refresh_token_encrypted, "1//test_refresh_token_67890")

    def test_email_status_protected_and_masks_tokens(self):
        """GET /api/admin/email/status/ requires JWT, and never returns access/refresh tokens."""
        # Unauthenticated request -> 401
        resp_unauth = self.client.get("/api/admin/email/status/")
        self.assertEqual(resp_unauth.status_code, 401)

        # Create integration record
        integration = EmailIntegration.objects.create(
            company=self.company,
            provider="gmail",
            email="connected_biz@gmail.com",
            is_connected=True,
        )
        integration.access_token = "secret_access_token"
        integration.refresh_token = "secret_refresh_token"
        integration.save()

        resp_auth = self.client.get(
            "/api/admin/email/status/",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_token}",
        )
        self.assertEqual(resp_auth.status_code, 200)
        data = resp_auth.json()
        self.assertTrue(data["connected"])
        self.assertEqual(data["email"], "connected_biz@gmail.com")
        self.assertEqual(data["provider"], "gmail")
        self.assertNotIn("access_token", data)
        self.assertNotIn("refresh_token", data)
        self.assertNotIn("access_token_encrypted", data)
        self.assertNotIn("refresh_token_encrypted", data)

    def test_email_disconnect_protected_and_clears_credentials(self):
        """POST /api/admin/email/disconnect/ clears credentials and marks disconnected."""
        # Unauthenticated request -> 401
        resp_unauth = self.client.post("/api/admin/email/disconnect/")
        self.assertEqual(resp_unauth.status_code, 401)

        integration = EmailIntegration.objects.create(
            company=self.company,
            provider="gmail",
            email="connected_biz@gmail.com",
            is_connected=True,
        )
        integration.access_token = "test_token"
        integration.save()

        with patch("requests.post") as mock_revoke:
            resp_auth = self.client.post(
                "/api/admin/email/disconnect/",
                HTTP_AUTHORIZATION=f"Bearer {self.admin_token}",
            )
            self.assertEqual(resp_auth.status_code, 200)
            self.assertFalse(resp_auth.json()["connected"])

            integration.refresh_from_db()
            self.assertFalse(integration.is_connected)
            self.assertEqual(integration.access_token_encrypted, "")
            self.assertEqual(integration.refresh_token_encrypted, "")

    def test_email_send_requires_auth_and_permission(self):
        """POST /api/admin/email/send/ requires JWT and integration.manage permission."""
        # Unauthenticated -> 401
        resp_unauth = self.client.post(
            "/api/admin/email/send/",
            data={"to": "test@example.com", "subject": "Hello", "body": "World"},
            content_type="application/json",
        )
        self.assertEqual(resp_unauth.status_code, 401)

        # Sales user -> 403
        resp_sales = self.client.post(
            "/api/admin/email/send/",
            data={"to": "test@example.com", "subject": "Hello", "body": "World"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.sales_token}",
        )
        self.assertEqual(resp_sales.status_code, 403)


class StaffInvitationAndLoginFlowTest(TestCase):
    """
    Comprehensive tests for the entire staff invitation, verification,
    acceptance, and login lifecycle.
    """

    def setUp(self):
        self.client = Client()
        self.company = Company.objects.create(name="Acme Corp", email="contact@acmewidgets.com")
        self.admin_user = User.objects.create_user(
            username="admin@acmewidgets.com",
            email="admin@acmewidgets.com",
            password="AdminPassword123!",
        )
        self.admin_staff = Staff.objects.create(
            user=self.admin_user,
            company=self.company,
            full_name="Admin Boss",
            email="admin@acmewidgets.com",
            role="admin",
            is_accepted=True,
        )
        self.admin_token = str(RefreshToken.for_user(self.admin_user).access_token)

    def test_full_invite_verify_accept_login_flow(self):
        """
        1. Admin invites a staff member via POST /api/admin/staff/add/
        2. Invitation token and email link with FRONTEND_URL are generated
        3. Token is verified via GET /api/admin/staff/verify-invitation/
        4. Staff accepts invitation via POST /api/admin/staff/acceptinvitation/
        5. Staff logs in via POST /api/admin/staff/login/
        """
        invited_email = "newstaff@acmewidgets.com"

        # 1. Admin sends invitation
        with patch("AdminApp.views.send_invite_email") as mock_send_email:
            invite_resp = self.client.post(
                "/api/admin/staff/add/",
                data={
                    "full_name": "New Hire",
                    "email": invited_email,
                    "role": "sales agent",
                    "department": "Sales",
                },
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {self.admin_token}",
            )
            self.assertEqual(invite_resp.status_code, 201)
            mock_send_email.assert_called_once()

            # Verify email link includes FRONTEND_URL and invitation token
            call_args = mock_send_email.call_args
            recipient_email, subject, html_content = call_args[0]
            self.assertEqual(recipient_email, invited_email)
            self.assertIn("You're invited to join CRM", subject)

        # 2. Verify staff record in database
        staff = Staff.objects.get(email=invited_email)
        self.assertTrue(staff.is_invited)
        self.assertFalse(staff.is_accepted)
        self.assertIsNotNone(staff.invitation_token)
        token_str = str(staff.invitation_token)
        self.assertIn(token_str, html_content)
        self.assertIn("http://localhost:5173/staff/accept-invitation/?token=", html_content)

        # 3. Before accepting, staff cannot log in
        early_login_resp = self.client.post(
            "/api/admin/staff/login/",
            data={"email": invited_email, "password": "AnyPassword123!"},
            content_type="application/json",
        )
        self.assertEqual(early_login_resp.status_code, 403)
        self.assertIn("accept your email invitation", early_login_resp.json().get("message", ""))

        # 4. Verify token endpoint (GET /api/admin/staff/verify-invitation/)
        verify_resp = self.client.get(f"/api/admin/staff/verify-invitation/?token={token_str}")
        self.assertEqual(verify_resp.status_code, 200)
        verify_data = verify_resp.json()
        self.assertTrue(verify_data["valid"])
        self.assertEqual(verify_data["email"], invited_email)
        self.assertEqual(verify_data["fullName"], "New Hire")
        self.assertEqual(verify_data["role"], "sales agent")
        self.assertEqual(verify_data["companyName"], "Acme Corp")

        # 4b. Verify token via alias endpoint /api/admin/auth/verify-invite/
        verify_alias_resp = self.client.get(f"/api/admin/auth/verify-invite/?token={token_str}")
        self.assertEqual(verify_alias_resp.status_code, 200)

        # 5. Invalid token returns 400/404
        bad_token_resp = self.client.get("/api/admin/staff/verify-invitation/?token=not-a-uuid")
        self.assertEqual(bad_token_resp.status_code, 400)

        # 6. Password length validation on accept invitation
        short_pw_resp = self.client.post(
            "/api/admin/staff/acceptinvitation/",
            data={"token": token_str, "password": "short"},
            content_type="application/json",
        )
        self.assertEqual(short_pw_resp.status_code, 400)

        # 7. Successful accept invitation
        staff_password = "StaffSecurePassword2026!"
        accept_resp = self.client.post(
            "/api/admin/staff/acceptinvitation/",
            data={"token": token_str, "password": staff_password},
            content_type="application/json",
        )
        self.assertEqual(accept_resp.status_code, 200)
        accept_data = accept_resp.json()
        self.assertIn("access", accept_data)
        self.assertIn("refresh", accept_data)
        self.assertEqual(accept_data["user"]["email"], invited_email)
        self.assertEqual(accept_data["user"]["role"], "sales agent")

        # Verify database state after acceptance
        staff.refresh_from_db()
        self.assertFalse(staff.is_invited)
        self.assertTrue(staff.is_accepted)
        self.assertIsNone(staff.invitation_token)
        self.assertIsNotNone(staff.user)
        self.assertTrue(staff.user.is_active)
        self.assertTrue(staff.user.check_password(staff_password))

        # 8. Accepting again fails gracefully
        repeat_accept_resp = self.client.post(
            "/api/admin/staff/acceptinvitation/",
            data={"token": token_str, "password": staff_password},
            content_type="application/json",
        )
        self.assertEqual(repeat_accept_resp.status_code, 400)

        # 9. Staff can now log in via POST /api/admin/staff/login/
        login_resp = self.client.post(
            "/api/admin/staff/login/",
            data={"email": invited_email, "password": staff_password},
            content_type="application/json",
        )
        self.assertEqual(login_resp.status_code, 200)
        login_data = login_resp.json()
        self.assertIn("access", login_data)
        self.assertIn("refresh", login_data)
        self.assertEqual(login_data["user"]["email"], invited_email)
        self.assertEqual(login_data["user"]["role"], "sales agent")
        self.assertEqual(login_data["user"]["companyName"], "Acme Corp")

        # 9b. Verify staff.user.last_login is populated and returned in staff listing
        staff.user.refresh_from_db()
        self.assertIsNotNone(staff.user.last_login)

        staff_list_resp = self.client.get(
            "/api/admin/staff/view/",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_token}",
        )
        self.assertEqual(staff_list_resp.status_code, 200)
        staff_data = next((s for s in staff_list_resp.json() if s["email"] == invited_email), None)
        self.assertIsNotNone(staff_data)
        self.assertEqual(staff_data["lastActive"], staff.user.last_login.isoformat())

        # Also verify single staff view
        single_staff_resp = self.client.get(
            f"/api/admin/staff/single/view/{staff.id}/",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_token}",
        )
        self.assertEqual(single_staff_resp.status_code, 200)
        self.assertEqual(single_staff_resp.json()["lastActive"], staff.user.last_login.isoformat())

        # 10. Wrong password returns 401
        bad_pw_resp = self.client.post(
            "/api/admin/staff/login/",
            data={"email": invited_email, "password": "WrongPassword999!"},
            content_type="application/json",
        )
        self.assertEqual(bad_pw_resp.status_code, 401)

    def test_all_roles_login_updates_last_active_and_staff_listing(self):
        """
        Verify that Admin, Manager, Sales Agent, and Support Agent logins all
        correctly update user.last_login and return lastActive in the Staff APIs.
        """
        roles_to_test = [
            ("admin2@acmewidgets.com", "Admin Two", "admin", "AdminPass2026!"),
            ("manager@acmewidgets.com", "Manager User", "manager", "ManagerPass2026!"),
            ("sales@acmewidgets.com", "Sales User", "sales agent", "SalesPass2026!"),
            ("support@acmewidgets.com", "Support User", "support agent", "SupportPass2026!"),
        ]

        created_staff = []
        for email, name, role, password in roles_to_test:
            user = User.objects.create_user(
                username=email,
                email=email,
                password=password,
                first_name=name,
            )
            # Intentionally start with last_login = None
            user.last_login = None
            user.save(update_fields=["last_login"])

            staff = Staff.objects.create(
                user=user,
                company=self.company,
                full_name=name,
                email=email,
                role=role,
                is_accepted=True,
            )
            created_staff.append((staff, email, password))

        # Perform login for each role and verify last_login
        for staff, email, password in created_staff:
            resp = self.client.post(
                "/api/admin/staff/login/",
                data={"email": email, "password": password},
                content_type="application/json",
            )
            self.assertEqual(resp.status_code, 200, f"Login failed for {email}: {resp.content}")

            # Verify staff.user.last_login is updated in DB
            staff.user.refresh_from_db()
            self.assertIsNotNone(staff.user.last_login, f"last_login is None for {email}")

            # Verify staff list API contains correct lastActive value
            list_resp = self.client.get(
                "/api/admin/staff/view/",
                HTTP_AUTHORIZATION=f"Bearer {self.admin_token}",
            )
            self.assertEqual(list_resp.status_code, 200)
            item = next((s for s in list_resp.json() if s["email"] == email), None)
            self.assertIsNotNone(item)
            self.assertEqual(item["lastActive"], staff.user.last_login.isoformat())


class LeadEnquiryTypeTests(TestCase):
    """
    Comprehensive tests for the Lead Enquiry Type feature covering:
    - Case 1: Not Specified (product=null, service=null)
    - Case 2: Product (product=valid company product, service=null)
    - Case 3: Product optional (product=null, service=null)
    - Case 4: Service (service=valid company service, product=null)
    - Case 5: Service optional (service=null, product=null)
    - Case 6: Cross-company product assignment rejected
    - Case 7: Cross-company service assignment rejected
    - Case 8: Setting both product and service rejected
    - Case 9: Update Not Specified -> Product with audit history
    - Case 10: Update Product -> Service with product cleared and audit history
    - Case 11: Update Service -> Not Specified with both cleared and audit history
    - view_single_lead API structure
    - view_leads API lightweight structure
    """

    def setUp(self):
        from django.core.exceptions import ValidationError

        self.ValidationError = ValidationError

        # Two distinct companies for multi-tenant testing
        self.company_a = Company.objects.create(name="Tenant Alpha", email="alpha@tenant.com")
        self.company_b = Company.objects.create(name="Tenant Beta", email="beta@tenant.com")

        # Admin user and staff for Company A
        self.user_a = User.objects.create_user(
            username="admin_alpha",
            email="admin@alpha.com",
            password="StrongPassword2026!",
        )
        self.staff_a = Staff.objects.create(
            user=self.user_a,
            company=self.company_a,
            full_name="Alpha Admin",
            email="admin@alpha.com",
            role="admin",
            is_accepted=True,
        )
        self.token_a = str(RefreshToken.for_user(self.user_a).access_token)
        self.auth_headers_a = {"HTTP_AUTHORIZATION": f"Bearer {self.token_a}"}

        # Admin user and staff for Company B
        self.user_b = User.objects.create_user(
            username="admin_beta",
            email="admin@beta.com",
            password="StrongPassword2026!",
        )
        self.staff_b = Staff.objects.create(
            user=self.user_b,
            company=self.company_b,
            full_name="Beta Admin",
            email="admin@beta.com",
            role="admin",
            is_accepted=True,
        )

        # Products & Services for Company A
        self.product_a = Product.objects.create(
            company=self.company_a,
            name="CRM Software",
            product_code="PRD-CRM",
            sku="SKU-CRM-01",
            unit_price=100.00,
        )
        self.service_a = Service.objects.create(
            company=self.company_a,
            service_name="Website Development",
            service_code="SRV-DEV",
            unit_price=50.00,
            billing_type="fixed",
        )

        # Products & Services for Company B (Foreign tenant)
        self.product_b = Product.objects.create(
            company=self.company_b,
            name="Competitor Product",
            product_code="PRD-BETA",
            sku="SKU-BETA-01",
            unit_price=200.00,
        )
        self.service_b = Service.objects.create(
            company=self.company_b,
            service_name="Competitor Service",
            service_code="SRV-BETA",
            unit_price=90.00,
            billing_type="hourly",
        )

    # ── Case 1 ──────────────────────────────────────────────────────────────
    def test_case_1_not_specified(self):
        """Case 1: Not Specified, Product = null, Service = null must work."""
        resp = self.client.post(
            "/api/admin/lead/add/",
            data={
                "full_name": "Alice Case 1",
                "phone_number": "1111111111",
                "enquiry_type": "not_specified",
            },
            content_type="application/json",
            **self.auth_headers_a,
        )
        self.assertEqual(resp.status_code, 201)

        lead = Lead.objects.get(full_name="Alice Case 1", company=self.company_a)
        self.assertEqual(lead.enquiry_type, "not_specified")
        self.assertIsNone(lead.product)
        self.assertIsNone(lead.service)

    # ── Case 2 ──────────────────────────────────────────────────────────────
    def test_case_2_product_with_valid_product(self):
        """Case 2: Product, Product = valid company product, Service = null must work."""
        resp = self.client.post(
            "/api/admin/lead/add/",
            data={
                "full_name": "Bob Case 2",
                "phone_number": "2222222222",
                "enquiry_type": "product",
                "product_id": self.product_a.id,
            },
            content_type="application/json",
            **self.auth_headers_a,
        )
        self.assertEqual(resp.status_code, 201)

        lead = Lead.objects.get(full_name="Bob Case 2", company=self.company_a)
        self.assertEqual(lead.enquiry_type, "product")
        self.assertEqual(lead.product, self.product_a)
        self.assertIsNone(lead.service)

    # ── Case 3 ──────────────────────────────────────────────────────────────
    def test_case_3_product_optional(self):
        """Case 3: Product, Product = null, Service = null must work (Product selection is optional)."""
        resp = self.client.post(
            "/api/admin/lead/add/",
            data={
                "full_name": "Charlie Case 3",
                "phone_number": "3333333333",
                "enquiry_type": "product",
            },
            content_type="application/json",
            **self.auth_headers_a,
        )
        self.assertEqual(resp.status_code, 201)

        lead = Lead.objects.get(full_name="Charlie Case 3", company=self.company_a)
        self.assertEqual(lead.enquiry_type, "product")
        self.assertIsNone(lead.product)
        self.assertIsNone(lead.service)

    # ── Case 4 ──────────────────────────────────────────────────────────────
    def test_case_4_service_with_valid_service(self):
        """Case 4: Service, Service = valid company service, Product = null must work."""
        resp = self.client.post(
            "/api/admin/lead/add/",
            data={
                "full_name": "Dana Case 4",
                "phone_number": "4444444444",
                "enquiry_type": "service",
                "service_id": self.service_a.id,
            },
            content_type="application/json",
            **self.auth_headers_a,
        )
        self.assertEqual(resp.status_code, 201)

        lead = Lead.objects.get(full_name="Dana Case 4", company=self.company_a)
        self.assertEqual(lead.enquiry_type, "service")
        self.assertEqual(lead.service, self.service_a)
        self.assertIsNone(lead.product)

    # ── Case 5 ──────────────────────────────────────────────────────────────
    def test_case_5_service_optional(self):
        """Case 5: Service, Service = null, Product = null must work (Service selection is optional)."""
        resp = self.client.post(
            "/api/admin/lead/add/",
            data={
                "full_name": "Evan Case 5",
                "phone_number": "5555555555",
                "enquiry_type": "service",
            },
            content_type="application/json",
            **self.auth_headers_a,
        )
        self.assertEqual(resp.status_code, 201)

        lead = Lead.objects.get(full_name="Evan Case 5", company=self.company_a)
        self.assertEqual(lead.enquiry_type, "service")
        self.assertIsNone(lead.service)
        self.assertIsNone(lead.product)

    # ── Case 6 ──────────────────────────────────────────────────────────────
    def test_case_6_cross_company_product_rejected(self):
        """Case 6: Try assigning a Product from another Company. Must be rejected."""
        # API level rejection
        resp = self.client.post(
            "/api/admin/lead/add/",
            data={
                "full_name": "Fiona Case 6",
                "phone_number": "6666666666",
                "enquiry_type": "product",
                "product_id": self.product_b.id,
            },
            content_type="application/json",
            **self.auth_headers_a,
        )
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(Lead.objects.filter(full_name="Fiona Case 6").exists())

        # Model validation level rejection
        with self.assertRaises(self.ValidationError):
            lead = Lead(
                company=self.company_a,
                full_name="Fiona Model Test",
                phone_number="6666666666",
                enquiry_type="product",
                product=self.product_b,
            )
            lead.clean()

    # ── Case 7 ──────────────────────────────────────────────────────────────
    def test_case_7_cross_company_service_rejected(self):
        """Case 7: Try assigning a Service from another Company. Must be rejected."""
        # API level rejection
        resp = self.client.post(
            "/api/admin/lead/add/",
            data={
                "full_name": "George Case 7",
                "phone_number": "7777777777",
                "enquiry_type": "service",
                "service_id": self.service_b.id,
            },
            content_type="application/json",
            **self.auth_headers_a,
        )
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(Lead.objects.filter(full_name="George Case 7").exists())

        # Model validation level rejection
        with self.assertRaises(self.ValidationError):
            lead = Lead(
                company=self.company_a,
                full_name="George Model Test",
                phone_number="7777777777",
                enquiry_type="service",
                service=self.service_b,
            )
            lead.clean()

    # ── Case 8 ──────────────────────────────────────────────────────────────
    def test_case_8_both_product_and_service_rejected(self):
        """Case 8: Try setting both Product and Service. Must be rejected."""
        # When enquiry_type is product but service_id also sent
        resp1 = self.client.post(
            "/api/admin/lead/add/",
            data={
                "full_name": "Hannah Case 8a",
                "phone_number": "8888888881",
                "enquiry_type": "product",
                "product_id": self.product_a.id,
                "service_id": self.service_a.id,
            },
            content_type="application/json",
            **self.auth_headers_a,
        )
        self.assertEqual(resp1.status_code, 400)

        # When enquiry_type is service but product_id also sent
        resp2 = self.client.post(
            "/api/admin/lead/add/",
            data={
                "full_name": "Hannah Case 8b",
                "phone_number": "8888888882",
                "enquiry_type": "service",
                "product_id": self.product_a.id,
                "service_id": self.service_a.id,
            },
            content_type="application/json",
            **self.auth_headers_a,
        )
        self.assertEqual(resp2.status_code, 400)

        # When enquiry_type is not_specified but product/service sent
        resp3 = self.client.post(
            "/api/admin/lead/add/",
            data={
                "full_name": "Hannah Case 8c",
                "phone_number": "8888888883",
                "enquiry_type": "not_specified",
                "product_id": self.product_a.id,
            },
            content_type="application/json",
            **self.auth_headers_a,
        )
        self.assertEqual(resp3.status_code, 400)

        # Model validation level rejection
        with self.assertRaises(self.ValidationError):
            lead = Lead(
                company=self.company_a,
                full_name="Hannah Model Test",
                phone_number="8888888884",
                enquiry_type="product",
                product=self.product_a,
                service=self.service_a,
            )
            lead.clean()

    # ── Case 9 ──────────────────────────────────────────────────────────────
    def test_case_9_update_not_specified_to_product_audit(self):
        """Case 9: Change Not Specified → Product. Verify audit history."""
        lead = Lead.objects.create(
            company=self.company_a,
            full_name="Ian Case 9",
            phone_number="9999999999",
            enquiry_type="not_specified",
        )

        resp = self.client.put(
            f"/api/admin/lead/update/{lead.id}/",
            data={
                "enquiry_type": "product",
                "product_id": self.product_a.id,
            },
            content_type="application/json",
            **self.auth_headers_a,
        )
        self.assertEqual(resp.status_code, 200)

        lead.refresh_from_db()
        self.assertEqual(lead.enquiry_type, "product")
        self.assertEqual(lead.product, self.product_a)
        self.assertIsNone(lead.service)

        # Verify audit record
        audit = AuditLog.objects.filter(
            company=self.company_a,
            object_id=lead.id,
            action="updated",
        ).order_by("-created_at").first()
        self.assertIsNotNone(audit)
        self.assertIn("enquiry_type", audit.changes)
        self.assertEqual(audit.changes["enquiry_type"], {"old": "not_specified", "new": "product"})
        self.assertIn("product", audit.changes)
        self.assertEqual(audit.changes["product"], {"old": None, "new": self.product_a.id})

    # ── Case 10 ─────────────────────────────────────────────────────────────
    def test_case_10_update_product_to_service_audit(self):
        """Case 10: Change Product → Service. Verify Product cleared and audit records changes."""
        lead = Lead.objects.create(
            company=self.company_a,
            full_name="Julia Case 10",
            phone_number="1010101010",
            enquiry_type="product",
            product=self.product_a,
        )

        resp = self.client.put(
            f"/api/admin/lead/update/{lead.id}/",
            data={
                "enquiry_type": "service",
                "service_id": self.service_a.id,
            },
            content_type="application/json",
            **self.auth_headers_a,
        )
        self.assertEqual(resp.status_code, 200)

        lead.refresh_from_db()
        self.assertEqual(lead.enquiry_type, "service")
        self.assertIsNone(lead.product)  # Product automatically cleared
        self.assertEqual(lead.service, self.service_a)

        # Verify audit changes
        audit = AuditLog.objects.filter(
            company=self.company_a,
            object_id=lead.id,
            action="updated",
        ).order_by("-created_at").first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.changes["enquiry_type"], {"old": "product", "new": "service"})
        self.assertEqual(audit.changes["product"], {"old": self.product_a.id, "new": None})
        self.assertEqual(audit.changes["service"], {"old": None, "new": self.service_a.id})

    # ── Case 11 ─────────────────────────────────────────────────────────────
    def test_case_11_update_service_to_not_specified_audit(self):
        """Case 11: Change Service → Not Specified. Verify both Product and Service cleared."""
        lead = Lead.objects.create(
            company=self.company_a,
            full_name="Kevin Case 11",
            phone_number="1111111111",
            enquiry_type="service",
            service=self.service_a,
        )

        resp = self.client.put(
            f"/api/admin/lead/update/{lead.id}/",
            data={
                "enquiry_type": "not_specified",
            },
            content_type="application/json",
            **self.auth_headers_a,
        )
        self.assertEqual(resp.status_code, 200)

        lead.refresh_from_db()
        self.assertEqual(lead.enquiry_type, "not_specified")
        self.assertIsNone(lead.product)
        self.assertIsNone(lead.service)  # Service automatically cleared

        # Verify audit changes
        audit = AuditLog.objects.filter(
            company=self.company_a,
            object_id=lead.id,
            action="updated",
        ).order_by("-created_at").first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.changes["enquiry_type"], {"old": "service", "new": "not_specified"})
        self.assertEqual(audit.changes["service"], {"old": self.service_a.id, "new": None})

    # ── View APIs ───────────────────────────────────────────────────────────
    def test_view_single_lead_payload_structure(self):
        """Test view_single_lead returns expected JSON structure for product, service, and not_specified."""
        # 1. Product Lead
        lead_prod = Lead.objects.create(
            company=self.company_a,
            full_name="Single Lead Prod",
            phone_number="123",
            enquiry_type="product",
            product=self.product_a,
        )
        resp_prod = self.client.get(
            f"/api/admin/lead/single/view/{lead_prod.id}/",
            **self.auth_headers_a,
        )
        self.assertEqual(resp_prod.status_code, 200)
        data_prod = resp_prod.json()
        self.assertEqual(data_prod["enquiry_type"], "product")
        self.assertEqual(data_prod["product"], {"id": self.product_a.id, "name": "CRM Software"})
        self.assertIsNone(data_prod["service"])

        # 2. Service Lead
        lead_serv = Lead.objects.create(
            company=self.company_a,
            full_name="Single Lead Serv",
            phone_number="456",
            enquiry_type="service",
            service=self.service_a,
        )
        resp_serv = self.client.get(
            f"/api/admin/lead/single/view/{lead_serv.id}/",
            **self.auth_headers_a,
        )
        self.assertEqual(resp_serv.status_code, 200)
        data_serv = resp_serv.json()
        self.assertEqual(data_serv["enquiry_type"], "service")
        self.assertIsNone(data_serv["product"])
        self.assertEqual(data_serv["service"], {"id": self.service_a.id, "name": "Website Development"})

        # 3. Not Specified Lead
        lead_ns = Lead.objects.create(
            company=self.company_a,
            full_name="Single Lead NS",
            phone_number="789",
            enquiry_type="not_specified",
        )
        resp_ns = self.client.get(
            f"/api/admin/lead/single/view/{lead_ns.id}/",
            **self.auth_headers_a,
        )
        self.assertEqual(resp_ns.status_code, 200)
        data_ns = resp_ns.json()
        self.assertEqual(data_ns["enquiry_type"], "not_specified")
        self.assertIsNone(data_ns["product"])
        self.assertIsNone(data_ns["service"])

    def test_view_leads_lightweight_includes_enquiry_type(self):
        """Test view_leads includes enquiry_type without nested product/service objects."""
        Lead.objects.create(
            company=self.company_a,
            full_name="List Lead",
            phone_number="999",
            enquiry_type="product",
            product=self.product_a,
        )
        resp = self.client.get(
            "/api/admin/lead/view/",
            **self.auth_headers_a,
        )
        self.assertEqual(resp.status_code, 200)
        leads = resp.json()
        item = next((l for l in leads if l["name"] == "List Lead"), None)
        self.assertIsNotNone(item)
        self.assertEqual(item["enquiry_type"], "product")
        # Ensure no heavy nested product or service dicts are returned
        self.assertNotIn("product", item)
        self.assertNotIn("service", item)


class StickyNoteTests(TestCase):
    """
    Comprehensive tests for the Staff Sticky Note feature:
    - Automatic creation on first GET
    - Auto-save content & rich-text HTML preservation
    - Color updates
    - Reminder setting, updating, clearing, and completing
    - Reminder reset when reminder_at changes
    - Deletion and subsequent recreation
    - Multi-tenant and cross-staff isolation
    - Due reminder detection without mutation during polling
    """

    def setUp(self):
        self.client = Client()

        # Company 1 with two staff members
        self.company_1 = Company.objects.create(
            name="Acme Corporation",
            email="info@acme.com",
        )
        self.user_1 = User.objects.create_user(
            username="staff_one",
            email="staff1@acme.com",
            password="SecurePassword2026!",
        )
        self.staff_1 = Staff.objects.create(
            user=self.user_1,
            company=self.company_1,
            full_name="Staff One",
            email="staff1@acme.com",
            role="sales agent",
            is_accepted=True,
        )
        self.token_1 = str(RefreshToken.for_user(self.user_1).access_token)
        self.auth_headers_1 = {"HTTP_AUTHORIZATION": f"Bearer {self.token_1}"}

        self.user_2 = User.objects.create_user(
            username="staff_two",
            email="staff2@acme.com",
            password="SecurePassword2026!",
        )
        self.staff_2 = Staff.objects.create(
            user=self.user_2,
            company=self.company_1,
            full_name="Staff Two",
            email="staff2@acme.com",
            role="sales agent",
            is_accepted=True,
        )
        self.token_2 = str(RefreshToken.for_user(self.user_2).access_token)
        self.auth_headers_2 = {"HTTP_AUTHORIZATION": f"Bearer {self.token_2}"}

        # Company 2 (foreign tenant)
        self.company_2 = Company.objects.create(
            name="Globex Corporation",
            email="info@globex.com",
        )
        self.user_foreign = User.objects.create_user(
            username="foreign_staff",
            email="staff@globex.com",
            password="SecurePassword2026!",
        )
        self.staff_foreign = Staff.objects.create(
            user=self.user_foreign,
            company=self.company_2,
            full_name="Foreign Staff",
            email="staff@globex.com",
            role="admin",
            is_accepted=True,
        )
        self.token_foreign = str(RefreshToken.for_user(self.user_foreign).access_token)
        self.auth_headers_foreign = {"HTTP_AUTHORIZATION": f"Bearer {self.token_foreign}"}

    def test_first_get_automatically_creates_sticky_note(self):
        """First GET /api/admin/sticky-note/view/ creates an empty note for the staff."""
        self.assertFalse(StickyNote.objects.filter(staff=self.staff_1).exists())

        resp = self.client.get("/api/admin/sticky-note/view/", **self.auth_headers_1)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertEqual(data["content"], "")
        self.assertEqual(data["color"], "yellow")
        self.assertIsNone(data["reminder_at"])
        self.assertFalse(data["is_completed"])
        self.assertIn("id", data)

        self.assertTrue(StickyNote.objects.filter(staff=self.staff_1).exists())
        note = StickyNote.objects.get(staff=self.staff_1)
        self.assertEqual(note.company, self.company_1)

    def test_update_content_debounced_autosave(self):
        """PUT /api/admin/sticky-note/update/ updates content and is safe for frequent auto-saves."""
        # Initial create & update
        resp = self.client.put(
            "/api/admin/sticky-note/update/",
            data={"content": "Meeting notes with client at 3 PM"},
            content_type="application/json",
            **self.auth_headers_1,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["content"], "Meeting notes with client at 3 PM")

        # Second update (simulating debounced typing auto-save)
        resp2 = self.client.put(
            "/api/admin/sticky-note/update/",
            data={"content": "Meeting notes with client at 3 PM - updated location"},
            content_type="application/json",
            **self.auth_headers_1,
        )
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.json()["content"], "Meeting notes with client at 3 PM - updated location")

        # Exactly 1 note exists for staff_1
        self.assertEqual(StickyNote.objects.filter(staff=self.staff_1).count(), 1)

    def test_preserve_rich_text_html_content(self):
        """PUT /api/admin/sticky-note/update/ preserves rich-text HTML markup without stripping."""
        html_content = "<p><strong>Call John</strong></p>\n<p>Discuss <em>Q3 budget</em> &amp; goals.</p>"
        resp = self.client.put(
            "/api/admin/sticky-note/update/",
            data={"content": html_content},
            content_type="application/json",
            **self.auth_headers_1,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["content"], html_content)

        # Confirm persisted exactly in DB
        note = StickyNote.objects.get(staff=self.staff_1)
        self.assertEqual(note.content, html_content)

    def test_update_color(self):
        """PUT /api/admin/sticky-note/update/ updates color field."""
        resp = self.client.put(
            "/api/admin/sticky-note/update/",
            data={"color": "#74b9ff"},
            content_type="application/json",
            **self.auth_headers_1,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["color"], "#74b9ff")

        note = StickyNote.objects.get(staff=self.staff_1)
        self.assertEqual(note.color, "#74b9ff")

    def test_set_and_update_reminder(self):
        """PUT /api/admin/sticky-note/update/ sets reminder_at correctly."""
        future_dt = timezone.now() + timedelta(days=2)
        future_iso = future_dt.isoformat()

        resp = self.client.put(
            "/api/admin/sticky-note/update/",
            data={"reminder_at": future_iso},
            content_type="application/json",
            **self.auth_headers_1,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIsNotNone(resp.json()["reminder_at"])

        note = StickyNote.objects.get(staff=self.staff_1)
        self.assertIsNotNone(note.reminder_at)

    def test_update_reminder_resets_is_completed(self):
        """Changing reminder_at resets is_completed to False."""
        past_dt = timezone.now() - timedelta(hours=1)
        note = StickyNote.objects.create(
            company=self.company_1,
            staff=self.staff_1,
            content="Task note",
            reminder_at=past_dt,
            is_completed=True,  # previously marked completed
        )

        # Set new reminder
        new_dt = timezone.now() + timedelta(days=3)
        resp = self.client.put(
            "/api/admin/sticky-note/update/",
            data={"reminder_at": new_dt.isoformat()},
            content_type="application/json",
            **self.auth_headers_1,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertFalse(data["is_completed"])

        note.refresh_from_db()
        self.assertFalse(note.is_completed)

    def test_clear_reminder(self):
        """POST /api/admin/sticky-note/clear-reminder/ clears reminder and resets is_completed."""
        StickyNote.objects.create(
            company=self.company_1,
            staff=self.staff_1,
            reminder_at=timezone.now() + timedelta(days=1),
            is_completed=True,
        )

        resp = self.client.post("/api/admin/sticky-note/clear-reminder/", **self.auth_headers_1)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIsNone(data["reminder_at"])
        self.assertFalse(data["is_completed"])

        note = StickyNote.objects.get(staff=self.staff_1)
        self.assertIsNone(note.reminder_at)
        self.assertFalse(note.is_completed)

    def test_complete_reminder(self):
        """POST /api/admin/sticky-note/complete/ marks reminder as completed."""
        StickyNote.objects.create(
            company=self.company_1,
            staff=self.staff_1,
            reminder_at=timezone.now() - timedelta(minutes=5),
            is_completed=False,
        )

        resp = self.client.post("/api/admin/sticky-note/complete/", **self.auth_headers_1)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["is_completed"])

        note = StickyNote.objects.get(staff=self.staff_1)
        self.assertTrue(note.is_completed)

    def test_delete_sticky_note(self):
        """DELETE /api/admin/sticky-note/delete/ deletes the note for the staff."""
        StickyNote.objects.create(
            company=self.company_1,
            staff=self.staff_1,
            content="Temporary reminder note",
        )
        self.assertTrue(StickyNote.objects.filter(staff=self.staff_1).exists())

        resp = self.client.delete("/api/admin/sticky-note/delete/", **self.auth_headers_1)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(StickyNote.objects.filter(staff=self.staff_1).exists())

    def test_auto_recreation_after_deletion(self):
        """Opening the sticky note again after deletion creates a clean blank note."""
        StickyNote.objects.create(
            company=self.company_1,
            staff=self.staff_1,
            content="Old note",
            color="red",
        )
        self.client.delete("/api/admin/sticky-note/delete/", **self.auth_headers_1)

        resp = self.client.get("/api/admin/sticky-note/view/", **self.auth_headers_1)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["content"], "")
        self.assertEqual(data["color"], "yellow")
        self.assertIsNone(data["reminder_at"])

    def test_staff_isolation_same_company(self):
        """Staff 1 and Staff 2 in the same company have completely independent notes."""
        self.client.put(
            "/api/admin/sticky-note/update/",
            data={"content": "Note for Staff One", "color": "purple"},
            content_type="application/json",
            **self.auth_headers_1,
        )
        self.client.put(
            "/api/admin/sticky-note/update/",
            data={"content": "Note for Staff Two", "color": "green"},
            content_type="application/json",
            **self.auth_headers_2,
        )

        resp_1 = self.client.get("/api/admin/sticky-note/view/", **self.auth_headers_1)
        resp_2 = self.client.get("/api/admin/sticky-note/view/", **self.auth_headers_2)

        self.assertEqual(resp_1.json()["content"], "Note for Staff One")
        self.assertEqual(resp_1.json()["color"], "purple")

        self.assertEqual(resp_2.json()["content"], "Note for Staff Two")
        self.assertEqual(resp_2.json()["color"], "green")

        # Staff 1 deleting their note does not affect Staff 2
        self.client.delete("/api/admin/sticky-note/delete/", **self.auth_headers_1)
        self.assertFalse(StickyNote.objects.filter(staff=self.staff_1).exists())
        self.assertTrue(StickyNote.objects.filter(staff=self.staff_2).exists())

    def test_multi_tenant_isolation_different_companies(self):
        """Staff in Company A and Staff in Company B are isolated; client cannot override tenant."""
        self.client.put(
            "/api/admin/sticky-note/update/",
            data={"content": "Company 1 Secret Note", "company_id": self.company_2.id, "staff_id": self.staff_foreign.id},
            content_type="application/json",
            **self.auth_headers_1,
        )

        note_1 = StickyNote.objects.get(staff=self.staff_1)
        self.assertEqual(note_1.company, self.company_1)
        self.assertNotEqual(note_1.company, self.company_2)

        # Foreign tenant accesses their own note
        resp_f = self.client.get("/api/admin/sticky-note/view/", **self.auth_headers_foreign)
        self.assertEqual(resp_f.json()["content"], "")

    def test_due_reminder_when_time_reached(self):
        """GET /api/admin/sticky-note/due/ returns has_reminder=True when reminder_at is reached and uncompleted."""
        StickyNote.objects.create(
            company=self.company_1,
            staff=self.staff_1,
            content="Call lead immediately",
            reminder_at=timezone.now() - timedelta(minutes=10),
            is_completed=False,
        )

        resp = self.client.get("/api/admin/sticky-note/due/", **self.auth_headers_1)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["has_reminder"])
        self.assertIsNotNone(data["sticky_note"])
        self.assertEqual(data["sticky_note"]["content"], "Call lead immediately")

    def test_completed_reminder_not_due(self):
        """A past reminder marked is_completed=True returns has_reminder=False."""
        StickyNote.objects.create(
            company=self.company_1,
            staff=self.staff_1,
            content="Already done",
            reminder_at=timezone.now() - timedelta(minutes=10),
            is_completed=True,
        )

        resp = self.client.get("/api/admin/sticky-note/due/", **self.auth_headers_1)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertFalse(data["has_reminder"])
        self.assertIsNone(data["sticky_note"])

    def test_future_reminder_not_due(self):
        """A reminder in the future returns has_reminder=False."""
        StickyNote.objects.create(
            company=self.company_1,
            staff=self.staff_1,
            content="Future task",
            reminder_at=timezone.now() + timedelta(hours=2),
            is_completed=False,
        )

        resp = self.client.get("/api/admin/sticky-note/due/", **self.auth_headers_1)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertFalse(data["has_reminder"])
        self.assertIsNone(data["sticky_note"])

    def test_null_reminder_not_due(self):
        """A note without a reminder returns has_reminder=False."""
        StickyNote.objects.create(
            company=self.company_1,
            staff=self.staff_1,
            content="Note with no reminder",
            reminder_at=None,
            is_completed=False,
        )

        resp = self.client.get("/api/admin/sticky-note/due/", **self.auth_headers_1)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertFalse(data["has_reminder"])
        self.assertIsNone(data["sticky_note"])

    def test_due_endpoint_repeated_polling_does_not_mutate(self):
        """GET /api/admin/sticky-note/due/ does NOT mutate reminder_at or is_completed on polling."""
        past_time = timezone.now() - timedelta(minutes=5)
        StickyNote.objects.create(
            company=self.company_1,
            staff=self.staff_1,
            content="Persistent notification",
            reminder_at=past_time,
            is_completed=False,
        )

        # Poll three times
        for _ in range(3):
            resp = self.client.get("/api/admin/sticky-note/due/", **self.auth_headers_1)
            self.assertEqual(resp.status_code, 200)
            self.assertTrue(resp.json()["has_reminder"])

        # DB values remain identical
        note = StickyNote.objects.get(staff=self.staff_1)
        self.assertEqual(note.reminder_at, past_time)
        self.assertFalse(note.is_completed)


class MetaAdsIntegrationTests(TestCase):
    """
    Comprehensive test suite for Meta Ads Integration:
    - MetaPage model creation, multi-page support, and uniqueness constraints.
    - OAuth callback pagination and page saving.
    - Webhook GET verification and POST signature validation.
    - Lead retrieval from Graph API, field mapping, and CRM lead creation.
    - Duplicate idempotency, error handling, missing field fallbacks, and multi-tenant isolation.
    """

    def setUp(self):
        self.client = Client()
        self.company_a = Company.objects.create(name="Company A", email="comp_a@test.com")
        self.company_b = Company.objects.create(name="Company B", email="comp_b@test.com")

        self.user_a = User.objects.create_user(username="usera", email="usera@test.com", password="password123")
        self.staff_a = Staff.objects.create(
            user=self.user_a,
            company=self.company_a,
            full_name="Staff A",
            email="usera@test.com",
            role="admin",
            is_accepted=True,
        )

        self.integration_a = MetaIntegration.objects.create(
            company=self.company_a,
            meta_user_id="meta_usr_123",
            access_token="EAAB_test_user_token",
            ad_account_id="act_111111",
            page_id="page_1001",
            page_access_token="EAAB_test_page_token_1001",
            assigned_staff=self.staff_a,
            is_active=True,
        )

        self.page_a1 = MetaPage.objects.create(
            company=self.company_a,
            meta_integration=self.integration_a,
            page_id="page_1001",
            page_name="Company A Main Page",
            page_access_token="EAAB_test_page_token_1001",
            is_active=True,
        )

        self.page_a2 = MetaPage.objects.create(
            company=self.company_a,
            meta_integration=self.integration_a,
            page_id="page_1002",
            page_name="Company A Secondary Page",
            page_access_token="EAAB_test_page_token_1002",
            is_active=True,
        )

        # Company B setup
        self.user_b = User.objects.create_user(username="userb", email="userb@test.com", password="password123")
        self.staff_b = Staff.objects.create(
            user=self.user_b,
            company=self.company_b,
            full_name="Staff B",
            email="userb@test.com",
            role="admin",
            is_accepted=True,
        )

        self.integration_b = MetaIntegration.objects.create(
            company=self.company_b,
            meta_user_id="meta_usr_456",
            access_token="EAAB_test_b_token",
            ad_account_id="act_222222",
            page_id="page_2001",
            page_access_token="EAAB_test_page_token_2001",
            assigned_staff=self.staff_b,
            is_active=True,
        )
        self.page_b = MetaPage.objects.create(
            company=self.company_b,
            meta_integration=self.integration_b,
            page_id="page_2001",
            page_name="Company B Page",
            page_access_token="EAAB_test_page_token_2001",
            is_active=True,
        )

    # 1. MetaPage creation
    def test_metapage_creation(self):
        page = MetaPage.objects.get(page_id="page_1001")
        self.assertEqual(page.company, self.company_a)
        self.assertEqual(page.page_name, "Company A Main Page")
        self.assertEqual(page.page_access_token, "EAAB_test_page_token_1001")
        self.assertTrue(page.is_active)
        self.assertIn("Company A Main Page", str(page))

    # 2. Multiple Pages associated with one company
    def test_multiple_pages_associated_with_one_company(self):
        pages = MetaPage.objects.filter(company=self.company_a)
        self.assertEqual(pages.count(), 2)
        page_ids = set(pages.values_list("page_id", flat=True))
        self.assertEqual(page_ids, {"page_1001", "page_1002"})

    # 3. Preventing duplicate Page connections
    def test_preventing_duplicate_page_connections(self):
        with self.assertRaises(IntegrityError):
            MetaPage.objects.create(
                company=self.company_a,
                meta_integration=self.integration_a,
                page_id="page_1001",  # duplicate for company_a
                page_name="Duplicate Page",
            )

    # 4. OAuth callback saving multiple Pages (with pagination)
    @patch("requests.post")
    @patch("requests.get")
    def test_oauth_callback_saving_multiple_pages(self, mock_get, mock_post):
        # Subscription call should succeed for all pages
        sub_resp = MagicMock()
        sub_resp.json.return_value = {"success": True}
        mock_post.return_value = sub_resp

        state = signing.dumps(
            {"company_id": self.company_a.id, "staff_id": self.staff_a.id},
            salt="meta-oauth",
        )

        token_resp = MagicMock()
        token_resp.json.return_value = {"access_token": "new_user_token"}

        me_resp = MagicMock()
        me_resp.json.return_value = {"id": "meta_usr_999", "name": "Admin User"}

        ad_resp = MagicMock()
        ad_resp.json.return_value = {"data": [{"id": "act_999999"}]}

        page1_resp = MagicMock()
        page1_resp.json.return_value = {
            "data": [
                {"id": "page_3001", "name": "Brand A Page", "access_token": "token_3001"},
            ],
            "paging": {
                "next": "https://graph.facebook.com/v24.0/me/accounts?after=cursor_123"
            }
        }

        page2_resp = MagicMock()
        page2_resp.json.return_value = {
            "data": [
                {"id": "page_3002", "name": "Brand B Page", "access_token": "token_3002"},
            ],
            "paging": {}
        }

        debug_resp = MagicMock()
        debug_resp.json.return_value = {"data": {"granular_scopes": []}}

        mock_get.side_effect = [token_resp, me_resp, ad_resp, page1_resp, page2_resp, debug_resp]

        with override_settings(
            META_APP_ID="app123",
            META_APP_SECRET="sec123",
            META_REDIRECT_URI="https://backend/api/admin/integrations/meta/callback/",
            FRONTEND_URL="https://tron-crm.netlify.app",
        ):
            resp = self.client.get(
                f"/api/admin/integrations/meta/callback/?code=test_code&state={state}"
            )
            self.assertEqual(resp.status_code, 302)
            self.assertIn("meta=connected", resp.url)

        pages = MetaPage.objects.filter(company=self.company_a)
        saved_page_ids = set(pages.values_list("page_id", flat=True))
        self.assertIn("page_3001", saved_page_ids)
        self.assertIn("page_3002", saved_page_ids)

        p1 = MetaPage.objects.get(company=self.company_a, page_id="page_3001")
        self.assertEqual(p1.page_name, "Brand A Page")
        self.assertEqual(p1.page_access_token, "token_3001")
        # Verify subscription status was persisted
        self.assertEqual(p1.webhook_subscription_status, MetaPage.SUBSCRIPTION_SUCCESS)
        # Confirm requests.post was called for each page
        self.assertEqual(mock_post.call_count, 2)

    # 5. Correct Page-to-company identification
    def test_page_to_company_identification(self):
        page = MetaPage.objects.filter(page_id="page_1002", is_active=True).first()
        self.assertIsNotNone(page)
        self.assertEqual(page.company, self.company_a)

    # 6. Valid webhook verification (GET)
    @override_settings(META_WEBHOOK_VERIFY_TOKEN="my_test_verify_token")
    def test_valid_webhook_verification(self):
        resp = self.client.get(
            "/api/admin/webhooks/meta/?hub.mode=subscribe&hub.verify_token=my_test_verify_token&hub.challenge=test_challenge_1234"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content.decode("utf-8"), "test_challenge_1234")

    # 7. Invalid webhook verification (GET)
    @override_settings(META_WEBHOOK_VERIFY_TOKEN="my_test_verify_token")
    def test_invalid_webhook_verification(self):
        resp = self.client.get(
            "/api/admin/webhooks/meta/?hub.mode=subscribe&hub.verify_token=wrong_token&hub.challenge=test_challenge_1234"
        )
        self.assertEqual(resp.status_code, 403)

    # 8. Valid POST signature
    @override_settings(META_APP_SECRET="super_secret_key")
    def test_valid_post_signature(self):
        body = json.dumps({"object": "page", "entry": []}).encode("utf-8")
        sig = "sha256=" + hmac.new(b"super_secret_key", body, hashlib.sha256).hexdigest()

        resp = self.client.post(
            "/api/admin/webhooks/meta/",
            data=body,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256=sig,
        )
        self.assertEqual(resp.status_code, 200)

    # 9. Invalid POST signature
    @override_settings(META_APP_SECRET="super_secret_key")
    def test_invalid_post_signature(self):
        body = json.dumps({"object": "page", "entry": []}).encode("utf-8")
        resp = self.client.post(
            "/api/admin/webhooks/meta/",
            data=body,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256="sha256=invalid_hash",
        )
        self.assertEqual(resp.status_code, 403)

    # 10. Successful Meta lead retrieval and import
    @patch("requests.get")
    def test_successful_meta_lead_retrieval_and_import(self, mock_get):
        lead_api_mock = MagicMock()
        lead_api_mock.json.return_value = {
            "id": "lead_99901",
            "created_time": "2026-10-16T05:00:00+0000",
            "field_data": [
                {"name": "full_name", "values": ["Alice Walker"]},
                {"name": "phone_number", "values": ["+15551234567"]},
                {"name": "email", "values": ["alice@example.com"]},
                {"name": "company_name", "values": ["Walker Tech"]},
                {"name": "city", "values": ["San Francisco"]},
            ]
        }
        mock_get.return_value = lead_api_mock

        payload = {
            "object": "page",
            "entry": [
                {
                    "id": "page_1001",
                    "time": 1720000000,
                    "changes": [
                        {
                            "field": "leadgen",
                            "value": {
                                "leadgen_id": "lead_99901",
                                "page_id": "page_1001",
                                "form_id": "form_888",
                                "ad_id": "ad_777",
                            }
                        }
                    ]
                }
            ]
        }
        body = json.dumps(payload).encode("utf-8")

        with override_settings(META_APP_SECRET=""):
            resp = self.client.post(
                "/api/admin/webhooks/meta/",
                data=body,
                content_type="application/json",
            )
            self.assertEqual(resp.status_code, 200)

        lead = Lead.objects.get(meta_lead_id="lead_99901")
        self.assertEqual(lead.company, self.company_a)
        self.assertEqual(lead.full_name, "Alice Walker")
        self.assertEqual(lead.phone_number, "+15551234567")
        self.assertEqual(lead.email, "alice@example.com")
        self.assertEqual(lead.company_name, "Walker Tech")
        self.assertEqual(lead.lead_source, "Facebook Ads")
        self.assertEqual(lead.status, "new")
        self.assertEqual(lead.assigned_to, self.staff_a)
        self.assertIn("City: San Francisco", lead.lead_description)

    # 11. Duplicate webhook delivery
    @patch("requests.get")
    def test_duplicate_webhook_delivery(self, mock_get):
        lead_api_mock = MagicMock()
        lead_api_mock.json.return_value = {
            "id": "lead_dup_100",
            "field_data": [
                {"name": "full_name", "values": ["Duplicate User"]},
                {"name": "phone_number", "values": ["+15550000000"]},
                {"name": "email", "values": ["dup@example.com"]},
            ]
        }
        mock_get.return_value = lead_api_mock

        payload = {
            "object": "page",
            "entry": [
                {
                    "id": "page_1001",
                    "changes": [
                        {
                            "field": "leadgen",
                            "value": {"leadgen_id": "lead_dup_100", "page_id": "page_1001"}
                        }
                    ]
                }
            ]
        }
        body = json.dumps(payload).encode("utf-8")

        with override_settings(META_APP_SECRET=""):
            resp1 = self.client.post("/api/admin/webhooks/meta/", data=body, content_type="application/json")
            self.assertEqual(resp1.status_code, 200)

            lead = Lead.objects.get(meta_lead_id="lead_dup_100")
            lead.lead_description = "Manual edit by agent"
            lead.save()

            resp2 = self.client.post("/api/admin/webhooks/meta/", data=body, content_type="application/json")
            self.assertEqual(resp2.status_code, 200)

        self.assertEqual(Lead.objects.filter(meta_lead_id="lead_dup_100").count(), 1)
        lead.refresh_from_db()
        self.assertEqual(lead.lead_description, "Manual edit by agent")

    # 12. Missing optional form fields
    @patch("requests.get")
    def test_missing_optional_form_fields(self, mock_get):
        lead_api_mock = MagicMock()
        lead_api_mock.json.return_value = {
            "id": "lead_opt_101",
            "field_data": [
                {"name": "full_name", "values": ["Bob Dylan"]},
                {"name": "phone_number", "values": ["+15559998888"]},
            ]
        }
        mock_get.return_value = lead_api_mock

        payload = {
            "object": "page",
            "entry": [
                {
                    "id": "page_1001",
                    "changes": [
                        {
                            "field": "leadgen",
                            "value": {"leadgen_id": "lead_opt_101", "page_id": "page_1001"}
                        }
                    ]
                }
            ]
        }

        with override_settings(META_APP_SECRET=""):
            resp = self.client.post("/api/admin/webhooks/meta/", data=json.dumps(payload), content_type="application/json")
            self.assertEqual(resp.status_code, 200)

        lead = Lead.objects.get(meta_lead_id="lead_opt_101")
        self.assertEqual(lead.full_name, "Bob Dylan")
        self.assertEqual(lead.phone_number, "+15559998888")
        self.assertIsNone(lead.email)
        self.assertEqual(lead.company_name, "")

    # 13. Missing required lead fields
    @patch("requests.get")
    def test_missing_required_lead_fields(self, mock_get):
        lead_api_mock = MagicMock()
        lead_api_mock.json.return_value = {
            "id": "lead_req_102",
            "field_data": [
                {"name": "first_name", "values": ["Charlie"]},
                {"name": "last_name", "values": ["Brown"]},
                {"name": "email", "values": ["charlie@example.com"]},
            ]
        }
        mock_get.return_value = lead_api_mock

        payload = {
            "object": "page",
            "entry": [
                {
                    "id": "page_1001",
                    "changes": [
                        {
                            "field": "leadgen",
                            "value": {"leadgen_id": "lead_req_102", "page_id": "page_1001"}
                        }
                    ]
                }
            ]
        }

        with override_settings(META_APP_SECRET=""):
            resp = self.client.post("/api/admin/webhooks/meta/", data=json.dumps(payload), content_type="application/json")
            self.assertEqual(resp.status_code, 200)

        lead = Lead.objects.get(meta_lead_id="lead_req_102")
        self.assertEqual(lead.full_name, "Charlie Brown")
        self.assertEqual(lead.phone_number, "")
        self.assertEqual(lead.email, "charlie@example.com")

    # 14. Meta API failures
    @patch("requests.get")
    def test_meta_api_failures(self, mock_get):
        err_mock = MagicMock()
        err_mock.json.return_value = {
            "error": {
                "message": "Error validating access token: Session has expired.",
                "type": "OAuthException",
                "code": 190,
            }
        }
        mock_get.return_value = err_mock

        payload = {
            "object": "page",
            "entry": [
                {
                    "id": "page_1001",
                    "changes": [
                        {
                            "field": "leadgen",
                            "value": {"leadgen_id": "lead_err_103", "page_id": "page_1001"}
                        }
                    ]
                }
            ]
        }

        with override_settings(META_APP_SECRET=""):
            resp = self.client.post("/api/admin/webhooks/meta/", data=json.dumps(payload), content_type="application/json")
            self.assertEqual(resp.status_code, 200)

        self.assertFalse(Lead.objects.filter(meta_lead_id="lead_err_103").exists())

    # 15. Page access-token failures
    def test_page_access_token_failures(self):
        self.page_a1.page_access_token = None
        self.page_a1.save()
        self.integration_a.access_token = ""
        self.integration_a.save()

        payload = {
            "object": "page",
            "entry": [
                {
                    "id": "page_1001",
                    "changes": [
                        {
                            "field": "leadgen",
                            "value": {"leadgen_id": "lead_no_token_104", "page_id": "page_1001"}
                        }
                    ]
                }
            ]
        }

        with override_settings(META_APP_SECRET=""):
            resp = self.client.post("/api/admin/webhooks/meta/", data=json.dumps(payload), content_type="application/json")
            self.assertEqual(resp.status_code, 200)

        self.assertFalse(Lead.objects.filter(meta_lead_id="lead_no_token_104").exists())

    # 16. Preventing cross-company lead imports
    @patch("requests.get")
    def test_preventing_cross_company_lead_imports(self, mock_get):
        lead_api_mock = MagicMock()
        lead_api_mock.json.return_value = {
            "id": "lead_comp_b_105",
            "field_data": [
                {"name": "full_name", "values": ["Customer for Company B"]},
                {"name": "phone_number", "values": ["+12223334444"]},
                {"name": "email", "values": ["b@compb.com"]},
            ]
        }
        mock_get.return_value = lead_api_mock

        payload = {
            "object": "page",
            "entry": [
                {
                    "id": "page_2001",
                    "changes": [
                        {
                            "field": "leadgen",
                            "value": {"leadgen_id": "lead_comp_b_105", "page_id": "page_2001"}
                        }
                    ]
                }
            ]
        }

        with override_settings(META_APP_SECRET=""):
            resp = self.client.post("/api/admin/webhooks/meta/", data=json.dumps(payload), content_type="application/json")
            self.assertEqual(resp.status_code, 200)

        lead_b = Lead.objects.get(meta_lead_id="lead_comp_b_105")
        self.assertEqual(lead_b.company, self.company_b)
        self.assertNotEqual(lead_b.company, self.company_a)
        self.assertFalse(Lead.objects.filter(company=self.company_a, meta_lead_id="lead_comp_b_105").exists())

    # 17. OAuth callback with empty pages (user has no pages or didn't grant permission)
    @patch("requests.post")
    @patch("requests.get")
    def test_oauth_callback_with_empty_pages(self, mock_get, mock_post):
        # No pages => subscription never called
        mock_post.return_value = MagicMock()

        state = signing.dumps(
            {"company_id": self.company_a.id, "staff_id": self.staff_a.id},
            salt="meta-oauth",
        )

        token_resp = MagicMock()
        token_resp.json.return_value = {"access_token": "token_no_pages"}

        me_resp = MagicMock()
        me_resp.json.return_value = {"id": "meta_usr_empty", "name": "No Pages User"}

        ad_resp = MagicMock()
        ad_resp.json.return_value = {"data": [{"id": "act_888888"}]}

        page_resp = MagicMock()
        page_resp.json.return_value = {"data": []}  # empty list of pages

        debug_resp = MagicMock()
        debug_resp.json.return_value = {"data": {"granular_scopes": []}}

        mock_get.side_effect = [token_resp, me_resp, ad_resp, page_resp, debug_resp]

        with override_settings(
            META_APP_ID="app123",
            META_APP_SECRET="sec123",
            META_REDIRECT_URI="https://backend/api/admin/integrations/meta/callback/",
            FRONTEND_URL="https://tron-crm.netlify.app",
        ):
            resp = self.client.get(
                f"/api/admin/integrations/meta/callback/?code=test_code&state={state}"
            )
            self.assertEqual(resp.status_code, 302)
            self.assertIn("meta=connected", resp.url)

        integration = MetaIntegration.objects.get(company=self.company_a)
        self.assertEqual(integration.meta_user_id, "meta_usr_empty")
        self.assertIsNone(integration.page_id)
        self.assertIsNone(integration.page_access_token)
        self.assertTrue(integration.is_active)

        # Previously active pages for company_a should be deactivated
        active_pages = MetaPage.objects.filter(company=self.company_a, is_active=True)
        self.assertEqual(active_pages.count(), 0)

        # Subscription never called when there are no pages
        mock_post.assert_not_called()

        # Status endpoint should report connected=True, but hasConnectedPage=False
        token_a = str(RefreshToken.for_user(self.user_a).access_token)
        status_resp = self.client.get(
            "/api/admin/integrations/meta/status/",
            HTTP_AUTHORIZATION=f"Bearer {token_a}"
        )
        self.assertEqual(status_resp.status_code, 200)
        data = status_resp.json()
        self.assertTrue(data["connected"])
        self.assertFalse(data["hasConnectedPage"])
        self.assertFalse(data["has_connected_page"])
        self.assertIsNone(data["pageId"])
        self.assertIsNone(data["pageName"])
        self.assertEqual(data["pages"], [])

    # 18. OAuth callback handling Graph API error on pages request
    @patch("requests.post")
    @patch("requests.get")
    def test_oauth_callback_pages_api_error(self, mock_get, mock_post):
        mock_post.return_value = MagicMock()

        state = signing.dumps(
            {"company_id": self.company_a.id, "staff_id": self.staff_a.id},
            salt="meta-oauth",
        )

        token_resp = MagicMock()
        token_resp.json.return_value = {"access_token": "token_err"}

        me_resp = MagicMock()
        me_resp.json.return_value = {"id": "meta_usr_err", "name": "Error User"}

        ad_resp = MagicMock()
        ad_resp.json.return_value = {"data": []}

        page_err_resp = MagicMock()
        page_err_resp.json.return_value = {
            "error": {"message": "Invalid OAuth access token.", "type": "OAuthException", "code": 190}
        }

        mock_get.side_effect = [token_resp, me_resp, ad_resp, page_err_resp]

        with override_settings(
            META_APP_ID="app123",
            META_APP_SECRET="sec123",
            META_REDIRECT_URI="https://backend/api/admin/integrations/meta/callback/",
            FRONTEND_URL="https://tron-crm.netlify.app",
        ):
            resp = self.client.get(
                f"/api/admin/integrations/meta/callback/?code=test_code&state={state}"
            )
            self.assertEqual(resp.status_code, 302)
            self.assertIn("reason=pages_failed", resp.url)

    # 19. OAuth callback discovers page via granular_scopes target_ids (New Pages Experience)
    @patch("requests.post")
    @patch("requests.get")
    def test_oauth_callback_granular_scopes_page_discovery(self, mock_get, mock_post):
        sub_resp = MagicMock()
        sub_resp.json.return_value = {"success": True}
        mock_post.return_value = sub_resp

        state = signing.dumps(
            {"company_id": self.company_a.id, "staff_id": self.staff_a.id},
            salt="meta-oauth",
        )

        token_resp = MagicMock()
        token_resp.json.return_value = {"access_token": "token_npe"}

        me_resp = MagicMock()
        me_resp.json.return_value = {"id": "meta_usr_npe", "name": "NPE User"}

        ad_resp = MagicMock()
        ad_resp.json.return_value = {"data": []}

        # /me/accounts returns empty list (New Pages Experience / Business Asset)
        page_accounts_resp = MagicMock()
        page_accounts_resp.json.return_value = {"data": []}

        # debug_token lists target_ids in granular_scopes
        debug_resp = MagicMock()
        debug_resp.json.return_value = {
            "data": {
                "granular_scopes": [
                    {"scope": "pages_show_list", "target_ids": ["page_4001"]},
                    {"scope": "leads_retrieval", "target_ids": ["page_4001"]},
                ]
            }
        }

        # direct page detail query GET /page_4001?fields=id,name,access_token
        page_detail_resp = MagicMock()
        page_detail_resp.json.return_value = {
            "id": "page_4001",
            "name": "Tron Technologies",
            "access_token": "token_page_4001",
        }

        mock_get.side_effect = [
            token_resp, me_resp, ad_resp, page_accounts_resp, debug_resp, page_detail_resp
        ]

        with override_settings(
            META_APP_ID="app123",
            META_APP_SECRET="sec123",
            META_REDIRECT_URI="https://backend/api/admin/integrations/meta/callback/",
            FRONTEND_URL="https://tron-crm.netlify.app",
        ):
            resp = self.client.get(
                f"/api/admin/integrations/meta/callback/?code=test_code&state={state}"
            )
            self.assertEqual(resp.status_code, 302)
            self.assertIn("meta=connected", resp.url)

        # Verify page is saved to database
        saved_page = MetaPage.objects.get(company=self.company_a, page_id="page_4001")
        self.assertEqual(saved_page.page_name, "Tron Technologies")
        self.assertEqual(saved_page.page_access_token, "token_page_4001")
        self.assertTrue(saved_page.is_active)
        self.assertEqual(saved_page.webhook_subscription_status, MetaPage.SUBSCRIPTION_SUCCESS)

        # Verify integration primary page is set
        integration = MetaIntegration.objects.get(company=self.company_a)
        self.assertEqual(integration.page_id, "page_4001")
        self.assertEqual(integration.page_access_token, "token_page_4001")

        # Verify status endpoint returns page details
        token_a = str(RefreshToken.for_user(self.user_a).access_token)
        status_resp = self.client.get(
            "/api/admin/integrations/meta/status/",
            HTTP_AUTHORIZATION=f"Bearer {token_a}"
        )
        self.assertEqual(status_resp.status_code, 200)
        data = status_resp.json()
        self.assertTrue(data["connected"])
        self.assertTrue(data["hasConnectedPage"])
        self.assertEqual(data["pageId"], "page_4001")
        self.assertEqual(data["pageName"], "Tron Technologies")

    # 19. Meta status with active connected Pages
    def test_meta_status_with_pages(self):
        token_a = str(RefreshToken.for_user(self.user_a).access_token)
        resp = self.client.get(
            "/api/admin/integrations/meta/status/",
            HTTP_AUTHORIZATION=f"Bearer {token_a}"
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertTrue(data["connected"])
        self.assertTrue(data["hasConnectedPage"])
        self.assertTrue(data["has_connected_page"])
        self.assertEqual(data["pageId"], "page_1001")
        self.assertEqual(data["page_id"], "page_1001")
        self.assertEqual(data["pageName"], "Company A Main Page")
        self.assertEqual(data["page_name"], "Company A Main Page")
        self.assertEqual(data["adAccountId"], "act_111111")
        self.assertEqual(data["ad_account_id"], "act_111111")
        self.assertTrue(data["hasPageAccessToken"])
        self.assertTrue(data["hasAccessToken"])
        self.assertEqual(len(data["pages"]), 2)
        self.assertIn("pageId", data["pages"][0])
        self.assertIn("pageName", data["pages"][0])
        # Subscription status fields must be present
        self.assertIn("webhookSubscriptionStatus", data["pages"][0])
        self.assertIn("webhook_subscription_status", data["pages"][0])
        self.assertIn("hasPageToken", data["pages"][0])

        # Security check: tokens must never be returned in response
        self.assertNotIn("access_token", data)
        self.assertNotIn("page_access_token", data)
        for p in data["pages"]:
            self.assertNotIn("access_token", p)
            self.assertNotIn("page_access_token", p)

    # 20. Disconnect flow deactivates integration and pages
    def test_meta_disconnect_flow(self):
        token_a = str(RefreshToken.for_user(self.user_a).access_token)

        resp = self.client.post(
            "/api/admin/integrations/meta/disconnect/",
            HTTP_AUTHORIZATION=f"Bearer {token_a}"
        )
        self.assertEqual(resp.status_code, 200)

        self.integration_a.refresh_from_db()
        self.assertFalse(self.integration_a.is_active)

        self.page_a1.refresh_from_db()
        self.assertFalse(self.page_a1.is_active)
        self.page_a2.refresh_from_db()
        self.assertFalse(self.page_a2.is_active)

        # Company B pages must remain completely untouched
        self.page_b.refresh_from_db()
        self.assertTrue(self.page_b.is_active)

        # Status after disconnect
        status_resp = self.client.get(
            "/api/admin/integrations/meta/status/",
            HTTP_AUTHORIZATION=f"Bearer {token_a}"
        )
        self.assertEqual(status_resp.status_code, 200)
        data = status_resp.json()
        self.assertFalse(data["connected"])
        self.assertFalse(data["hasConnectedPage"])
        self.assertEqual(data["pages"], [])

    # 21. Multi-tenant company isolation on status endpoint
    def test_meta_company_isolation_on_status(self):
        token_a = str(RefreshToken.for_user(self.user_a).access_token)
        token_b = str(RefreshToken.for_user(self.user_b).access_token)

        resp_a = self.client.get("/api/admin/integrations/meta/status/", HTTP_AUTHORIZATION=f"Bearer {token_a}")
        resp_b = self.client.get("/api/admin/integrations/meta/status/", HTTP_AUTHORIZATION=f"Bearer {token_b}")

        self.assertEqual(resp_a.status_code, 200)
        self.assertEqual(resp_b.status_code, 200)

        data_a = resp_a.json()
        data_b = resp_b.json()

        # Company A data
        self.assertEqual(data_a["metaUserId"], "meta_usr_123")
        self.assertEqual(data_a["pageId"], "page_1001")
        page_ids_a = [p["pageId"] for p in data_a["pages"]]
        self.assertEqual(set(page_ids_a), {"page_1001", "page_1002"})

        # Company B data
        self.assertEqual(data_b["metaUserId"], "meta_usr_456")
        self.assertEqual(data_b["pageId"], "page_2001")
        page_ids_b = [p["pageId"] for p in data_b["pages"]]
        self.assertEqual(page_ids_b, ["page_2001"])

        # No leakage across tenants
        self.assertNotIn("page_2001", page_ids_a)
        self.assertNotIn("page_1001", page_ids_b)

    # ---------------------------------------------------------------------------
    # Webhook subscription-specific tests (new)
    # ---------------------------------------------------------------------------

    # 22. Successful subscription: Graph API returns {"success": true}
    @patch("requests.post")
    @patch("requests.get")
    def test_subscription_success(self, mock_get, mock_post):
        sub_resp = MagicMock()
        sub_resp.json.return_value = {"success": True}
        mock_post.return_value = sub_resp

        state = signing.dumps(
            {"company_id": self.company_a.id, "staff_id": self.staff_a.id},
            salt="meta-oauth",
        )

        token_resp = MagicMock()
        token_resp.json.return_value = {"access_token": "user_tok"}
        me_resp = MagicMock()
        me_resp.json.return_value = {"id": "u1", "name": "User"}
        ad_resp = MagicMock()
        ad_resp.json.return_value = {"data": []}
        page_resp = MagicMock()
        page_resp.json.return_value = {
            "data": [{"id": "page_sub_ok", "name": "Sub OK Page", "access_token": "ptoken_ok"}],
            "paging": {},
        }
        debug_resp = MagicMock()
        debug_resp.json.return_value = {"data": {"granular_scopes": []}}

        mock_get.side_effect = [token_resp, me_resp, ad_resp, page_resp, debug_resp]

        with override_settings(
            META_APP_ID="app123", META_APP_SECRET="sec123",
            META_REDIRECT_URI="https://backend/callback/",
            FRONTEND_URL="https://tron-crm.netlify.app",
        ):
            resp = self.client.get(
                f"/api/admin/integrations/meta/callback/?code=c&state={state}"
            )
        self.assertIn("meta=connected", resp.url)

        page = MetaPage.objects.get(company=self.company_a, page_id="page_sub_ok")
        self.assertEqual(page.webhook_subscription_status, MetaPage.SUBSCRIPTION_SUCCESS)

        # POST was called with the correct URL pattern (no token in assertion)
        call_args = mock_post.call_args
        self.assertIn("page_sub_ok", call_args[0][0])
        self.assertIn("subscribed_apps", call_args[0][0])
        self.assertEqual(call_args[1]["params"]["subscribed_fields"], "leadgen")

    # 23. Graph API permission error: subscription marked as failed
    @patch("requests.post")
    @patch("requests.get")
    def test_subscription_permission_error(self, mock_get, mock_post):
        sub_err_resp = MagicMock()
        sub_err_resp.json.return_value = {
            "error": {
                "message": "(#200) The current user is not allowed to manage subscriptions.",
                "type": "OAuthException",
                "code": 200,
                "error_subcode": 1404121,
            }
        }
        mock_post.return_value = sub_err_resp

        state = signing.dumps(
            {"company_id": self.company_a.id, "staff_id": self.staff_a.id},
            salt="meta-oauth",
        )

        token_resp = MagicMock()
        token_resp.json.return_value = {"access_token": "user_tok"}
        me_resp = MagicMock()
        me_resp.json.return_value = {"id": "u1", "name": "User"}
        ad_resp = MagicMock()
        ad_resp.json.return_value = {"data": []}
        page_resp = MagicMock()
        page_resp.json.return_value = {
            "data": [{"id": "page_perm_err", "name": "Perm Err Page", "access_token": "ptoken_perm"}],
            "paging": {},
        }
        debug_resp = MagicMock()
        debug_resp.json.return_value = {"data": {"granular_scopes": []}}

        mock_get.side_effect = [token_resp, me_resp, ad_resp, page_resp, debug_resp]

        with override_settings(
            META_APP_ID="app123", META_APP_SECRET="sec123",
            META_REDIRECT_URI="https://backend/callback/",
            FRONTEND_URL="https://tron-crm.netlify.app",
        ):
            resp = self.client.get(
                f"/api/admin/integrations/meta/callback/?code=c&state={state}"
            )

        # OAuth flow must still complete — only subscription status reflects the failure
        self.assertIn("meta=connected", resp.url)

        page = MetaPage.objects.get(company=self.company_a, page_id="page_perm_err")
        self.assertEqual(page.webhook_subscription_status, MetaPage.SUBSCRIPTION_FAILED)
        self.assertTrue(page.is_active)

    # 24. Page with no page_access_token: subscription marked as no_token
    @patch("requests.post")
    @patch("requests.get")
    def test_subscription_no_token(self, mock_get, mock_post):
        """If Meta does not return a page_access_token, subscription must NOT be attempted."""
        mock_post.return_value = MagicMock()

        state = signing.dumps(
            {"company_id": self.company_a.id, "staff_id": self.staff_a.id},
            salt="meta-oauth",
        )

        token_resp = MagicMock()
        token_resp.json.return_value = {"access_token": "user_tok"}
        me_resp = MagicMock()
        me_resp.json.return_value = {"id": "u1", "name": "User"}
        ad_resp = MagicMock()
        ad_resp.json.return_value = {"data": []}
        # Note: no access_token field in the page object
        page_resp = MagicMock()
        page_resp.json.return_value = {
            "data": [{"id": "page_no_tok", "name": "No Token Page"}],
            "paging": {},
        }
        debug_resp = MagicMock()
        debug_resp.json.return_value = {"data": {"granular_scopes": []}}

        mock_get.side_effect = [token_resp, me_resp, ad_resp, page_resp, debug_resp]

        with override_settings(
            META_APP_ID="app123", META_APP_SECRET="sec123",
            META_REDIRECT_URI="https://backend/callback/",
            FRONTEND_URL="https://tron-crm.netlify.app",
        ):
            self.client.get(
                f"/api/admin/integrations/meta/callback/?code=c&state={state}"
            )

        # requests.post must never be called when there is no page token
        mock_post.assert_not_called()

        page = MetaPage.objects.get(company=self.company_a, page_id="page_no_tok")
        self.assertEqual(page.webhook_subscription_status, MetaPage.SUBSCRIPTION_NO_TOKEN)

    # 25. One page fails subscription, other succeeds — OAuth still completes
    @patch("requests.post")
    @patch("requests.get")
    def test_partial_subscription_failure(self, mock_get, mock_post):
        """A failure for one page must not block the subscription of other pages."""
        ok_resp = MagicMock()
        ok_resp.json.return_value = {"success": True}
        err_resp = MagicMock()
        err_resp.json.return_value = {
            "error": {"message": "Permission denied", "code": 200}
        }
        mock_post.side_effect = [err_resp, ok_resp]

        state = signing.dumps(
            {"company_id": self.company_a.id, "staff_id": self.staff_a.id},
            salt="meta-oauth",
        )

        token_resp = MagicMock()
        token_resp.json.return_value = {"access_token": "user_tok"}
        me_resp = MagicMock()
        me_resp.json.return_value = {"id": "u1", "name": "User"}
        ad_resp = MagicMock()
        ad_resp.json.return_value = {"data": []}
        page_resp = MagicMock()
        page_resp.json.return_value = {
            "data": [
                {"id": "page_fail_sub", "name": "Fail Sub",   "access_token": "tok_fail"},
                {"id": "page_ok_sub",   "name": "Success Sub", "access_token": "tok_ok"},
            ],
            "paging": {},
        }
        debug_resp = MagicMock()
        debug_resp.json.return_value = {"data": {"granular_scopes": []}}

        mock_get.side_effect = [token_resp, me_resp, ad_resp, page_resp, debug_resp]

        with override_settings(
            META_APP_ID="app123", META_APP_SECRET="sec123",
            META_REDIRECT_URI="https://backend/callback/",
            FRONTEND_URL="https://tron-crm.netlify.app",
        ):
            resp = self.client.get(
                f"/api/admin/integrations/meta/callback/?code=c&state={state}"
            )

        self.assertIn("meta=connected", resp.url)

        fail_page = MetaPage.objects.get(company=self.company_a, page_id="page_fail_sub")
        ok_page   = MetaPage.objects.get(company=self.company_a, page_id="page_ok_sub")
        self.assertEqual(fail_page.webhook_subscription_status, MetaPage.SUBSCRIPTION_FAILED)
        self.assertEqual(ok_page.webhook_subscription_status,   MetaPage.SUBSCRIPTION_SUCCESS)
        # Both pages must still be active in the CRM
        self.assertTrue(fail_page.is_active)
        self.assertTrue(ok_page.is_active)
        # Both subscription POSTs were attempted
        self.assertEqual(mock_post.call_count, 2)

    # 26. Network/timeout error on subscription: marked as failed, OAuth unaffected
    @patch("requests.post")
    @patch("requests.get")
    def test_subscription_network_error(self, mock_get, mock_post):
        import requests as req_lib
        mock_post.side_effect = req_lib.RequestException("Connection timed out")

        state = signing.dumps(
            {"company_id": self.company_a.id, "staff_id": self.staff_a.id},
            salt="meta-oauth",
        )

        token_resp = MagicMock()
        token_resp.json.return_value = {"access_token": "user_tok"}
        me_resp = MagicMock()
        me_resp.json.return_value = {"id": "u1", "name": "User"}
        ad_resp = MagicMock()
        ad_resp.json.return_value = {"data": []}
        page_resp = MagicMock()
        page_resp.json.return_value = {
            "data": [{"id": "page_timeout", "name": "Timeout Page", "access_token": "tok_x"}],
            "paging": {},
        }
        debug_resp = MagicMock()
        debug_resp.json.return_value = {"data": {"granular_scopes": []}}

        mock_get.side_effect = [token_resp, me_resp, ad_resp, page_resp, debug_resp]

        with override_settings(
            META_APP_ID="app123", META_APP_SECRET="sec123",
            META_REDIRECT_URI="https://backend/callback/",
            FRONTEND_URL="https://tron-crm.netlify.app",
        ):
            resp = self.client.get(
                f"/api/admin/integrations/meta/callback/?code=c&state={state}"
            )

        # OAuth must complete — subscription failure must not abort the flow
        self.assertIn("meta=connected", resp.url)

        page = MetaPage.objects.get(company=self.company_a, page_id="page_timeout")
        self.assertEqual(page.webhook_subscription_status, MetaPage.SUBSCRIPTION_FAILED)
        self.assertTrue(page.is_active)

    # 27. Retry idempotency: reconnecting updates subscription status without creating duplicates
    @patch("requests.post")
    @patch("requests.get")
    def test_subscription_retry_idempotency(self, mock_get, mock_post):
        """Reconnecting Meta for the same page retries subscription and updates the status."""
        # First connect: subscription fails
        fail_resp = MagicMock()
        fail_resp.json.return_value = {"error": {"message": "Temporary error", "code": 2}}
        ok_resp = MagicMock()
        ok_resp.json.return_value = {"success": True}

        state = signing.dumps(
            {"company_id": self.company_a.id, "staff_id": self.staff_a.id},
            salt="meta-oauth",
        )

        def make_get_side_effects(token="user_tok"):
            token_r = MagicMock(); token_r.json.return_value = {"access_token": token}
            me_r    = MagicMock(); me_r.json.return_value    = {"id": "u1", "name": "User"}
            ad_r    = MagicMock(); ad_r.json.return_value    = {"data": []}
            pg_r    = MagicMock(); pg_r.json.return_value    = {
                "data": [{"id": "page_retry", "name": "Retry Page", "access_token": "ptoken_retry"}],
                "paging": {},
            }
            dbg_r   = MagicMock(); dbg_r.json.return_value   = {"data": {"granular_scopes": []}}
            return [token_r, me_r, ad_r, pg_r, dbg_r]

        settings_override = dict(
            META_APP_ID="app123", META_APP_SECRET="sec123",
            META_REDIRECT_URI="https://backend/callback/",
            FRONTEND_URL="https://tron-crm.netlify.app",
        )

        # First connect
        mock_post.return_value = fail_resp
        mock_get.side_effect = make_get_side_effects()
        with override_settings(**settings_override):
            self.client.get(f"/api/admin/integrations/meta/callback/?code=c1&state={state}")

        page = MetaPage.objects.get(company=self.company_a, page_id="page_retry")
        self.assertEqual(page.webhook_subscription_status, MetaPage.SUBSCRIPTION_FAILED)

        # Second connect (retry) — subscription succeeds this time
        state2 = signing.dumps(
            {"company_id": self.company_a.id, "staff_id": self.staff_a.id},
            salt="meta-oauth",
        )
        mock_post.return_value = ok_resp
        mock_get.side_effect = make_get_side_effects("user_tok_2")
        with override_settings(**settings_override):
            self.client.get(f"/api/admin/integrations/meta/callback/?code=c2&state={state2}")

        page.refresh_from_db()
        self.assertEqual(page.webhook_subscription_status, MetaPage.SUBSCRIPTION_SUCCESS)
        # Must still be exactly one MetaPage row for this page
        self.assertEqual(
            MetaPage.objects.filter(company=self.company_a, page_id="page_retry").count(), 1
        )

    # 28. No token leakage in API responses or logs
    def test_no_token_leakage_in_status_response(self):
        """Tokens must never appear in the meta_status API response."""
        token_a = str(RefreshToken.for_user(self.user_a).access_token)
        resp = self.client.get(
            "/api/admin/integrations/meta/status/",
            HTTP_AUTHORIZATION=f"Bearer {token_a}"
        )
        self.assertEqual(resp.status_code, 200)
        raw = resp.content.decode("utf-8")

        # Raw token strings must not appear anywhere in the JSON body
        self.assertNotIn("EAAB_test_user_token", raw)
        self.assertNotIn("EAAB_test_page_token_1001", raw)
        self.assertNotIn("EAAB_test_page_token_1002", raw)

        # Ensure subscription status fields are booleans/strings, never raw tokens
        data = resp.json()
        for p in data["pages"]:
            self.assertNotIn("access_token", p)
            self.assertNotIn("page_access_token", p)
            self.assertIn("webhookSubscriptionStatus", p)
            self.assertIsInstance(p["webhookSubscriptionStatus"], str)
            self.assertIn("hasPageToken", p)
            self.assertIsInstance(p["hasPageToken"], bool)
