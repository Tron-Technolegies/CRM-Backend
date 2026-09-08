from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework import status

from AdminApp.models import Company, Staff
from AdminApp.permissions import (
    ROLE_PERMISSIONS,
    has_permission,
    require_permission,
)
from AdminApp.views import view_leads, delete_lead, add_staff, delete_staff, view_cases, view_quotes


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
