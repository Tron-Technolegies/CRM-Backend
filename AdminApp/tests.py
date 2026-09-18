from unittest.mock import patch, MagicMock
from urllib.parse import urlparse, parse_qs
from django.test import TestCase, Client
from django.core import signing
from django.conf import settings
from django.contrib.auth.models import User
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from AdminApp.models import Company, Staff, EmailIntegration, Product, Service, Lead, AuditLog
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



