# Role-Based Access Control (RBAC) — Implementation Documentation

## 1. Executive Summary

This document outlines the complete Role-Based Access Control (RBAC) system implemented in the CRM backend.

The system secures all CRM modules while strictly preserving:
- Existing 4 Staff roles: `admin`, `manager`, `sales agent`, `support agent`.
- `Staff.role` as the single source of truth.
- Company data isolation via `CompanyMiddleware` and `company=request.company` query scoping.
- Existing JWT authentication and request lifecycle.
- **Zero** database schema modifications or migrations.
- **Zero** URL route changes.

---

## 2. Core Architecture

### Layered Security Model
```
┌─────────────────────────────────────────────────────────────┐
│ 1. HTTP Request (with JWT Bearer Token)                    │
└──────────────────────────────┬──────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. CompanyMiddleware                                        │
│    - Validates JWT Token                                    │
│    - Attaches request.user, request.staff, request.company   │
│    - Rejects unauthenticated requests with 401              │
└──────────────────────────────┬──────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. DRF @api_view Wrapper                                    │
│    - Initializes DRF Request, parsers, format negotiation   │
└──────────────────────────────┬──────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. @require_permission('<permission_key>')                  │
│    - Checks Staff.role against ROLE_PERMISSIONS matrix      │
│    - If unauthorized -> returns 403 Forbidden Response      │
└──────────────────────────────┬──────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. View Logic (AdminApp/views.py)                           │
│    - Enforces tenant isolation: filter(company=req.company) │
│    - Executes business logic and returns response           │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Codebase Inventory & Verification

During the final audit of the codebase:
- **Total URL Routes (`AdminApp/urls.py`)**: `134` (Line count was 170, but actual route count is 134).
- **Views Protected by RBAC**: `118` (Enforced via `@require_permission`).
- **Unprotected Views**: `16` (Public auth, webhooks, callbacks, personal profile/notifications).
- **Distinct Permission Keys**: `84` (Structured as `<module>.<action>`).
- **All 134 views** reside inside [`AdminApp/views.py`](file:///c:/Users/HP/OneDrive/Desktop/CRM%20Project/AdminApp/views.py).

---

## 4. Role Permission Matrix & Boundaries

| Role | Total Perms | Key Permissions | Strictly Prohibited / Denied |
|---|:---:|---|---|
| **`admin`** | **84** | Full access to all CRM modules, Staff CRUD, Picklist CRUD, Meta/Twilio Integrations, Reports export. | None (wildcard full access). |
| **`manager`** | **76** | Full CRUD on operational CRM modules (Leads, Deals, Accounts, Customers, Tasks, Meetings, Calls, Products, Services, Price Books, Quotes, Orders, Invoices, Cases), create/edit Staff, export reports, Twilio dial-out, view picklists. | ❌ Delete Staff (`staff.delete`)<br>❌ Picklist modifications (`picklist.create/edit/delete`)<br>❌ Meta integration (`integration.*`)<br>❌ Twilio settings (`twilio.*`) |
| **`sales agent`** | **30** | Sales pipeline operations: Leads (create, view, edit, convert), Deals (create, view, edit), Customers & Accounts (create, view, edit), Tasks, Meetings, Calls (create, dial, view), View-only for Quotes, Orders, Invoices, Products, Services, Price Books, Picklists, View report dashboard. | ❌ Delete on ANY module (`*.delete`)<br>❌ Staff access (`staff.*`)<br>❌ Vendors & Purchase Orders (`vendor.*`, `purchaseorder.*`)<br>❌ Cases & Solutions (`case.*`, `casesolution.*`)<br>❌ Create/Edit on Quotes, Orders, Invoices, Products, Services, Price Books<br>❌ Export reports (`report.export`)<br>❌ Integrations & Settings |
| **`support agent`** | **24** | Customer Support operations: Cases & Solutions (create, view, edit), Customers (view, edit), Tasks, Meetings, Calls (create, dial, view), View-only for Leads, Deals, Accounts, Products, Services, Picklists, View report dashboard. | ❌ Delete on ANY module (`*.delete`)<br>❌ Create Customers (`customer.create`)<br>❌ Create/Edit/Convert Leads or Deals (`lead.create/edit/delete/convert`, `deal.create/edit/delete`)<br>❌ Staff access (`staff.*`)<br>❌ Vendors & Purchase Orders (`vendor.*`, `purchaseorder.*`)<br>❌ Quotes, Price Books, Orders, Invoices (`quote.*`, `pricebook.*`, `salesorder.*`, `invoice.*`)<br>❌ Export reports (`report.export`)<br>❌ Integrations & Settings |

---

## 5. File Changes Summary

### 1. New File: [`AdminApp/permissions.py`](file:///c:/Users/HP/OneDrive/Desktop/CRM%20Project/AdminApp/permissions.py)
Contains:
- `ROLE_PERMISSIONS`: Centralized dictionary containing the exact permission sets for each role.
- `has_permission(staff, perm)`: Core validator function. Handles role normalization and admin bypass.
- `require_permission(perm)`: Decorator wrapping view functions. Validates `request.staff` (with fallback to `request.user.staff`) and returns:
  ```json
  {
    "detail": "You do not have permission to perform this action.",
    "message": "You do not have permission to perform this action."
  }
  ```
  with HTTP status `403 Forbidden`.

### 2. Modified File: [`AdminApp/views.py`](file:///c:/Users/HP/OneDrive/Desktop/CRM%20Project/AdminApp/views.py)
- Imported `from AdminApp.permissions import require_permission`.
- Decorated all 118 operational views with `@require_permission('<module>.<action>')`.
- Preserved all 16 public/webhook/personal endpoints without permission checks.

### 3. Modified File: [`AdminApp/tests.py`](file:///c:/Users/HP/OneDrive/Desktop/CRM%20Project/AdminApp/tests.py)
Implemented 13 unit and integration tests:
- `RBACPermissionsUnitTest`: Tests role permission sets, admin wildcard, manager restrictions, sales agent restrictions, support agent restrictions, and invalid roles.
- `RequirePermissionDecoratorTest`: Tests view-level enforcement, asserting 403 on denied actions, 200 on authorized actions, and verification of staff deletion restrictions.

---

## 6. Complete Endpoint Mapping Reference

### 6.1 Leads
| URL | View Function | Permission | Admin | Manager | Sales Agent | Support Agent |
|---|---|---|:---:|:---:|:---:|:---:|
| `lead/add/` | `add_lead` | `lead.create` | ✅ | ✅ | ✅ | ❌ |
| `lead/view/` | `view_leads` | `lead.view` | ✅ | ✅ | ✅ | ✅ |
| `lead/single/view/<id>/` | `view_single_lead` | `lead.view` | ✅ | ✅ | ✅ | ✅ |
| `lead/update/<id>/` | `update_lead` | `lead.edit` | ✅ | ✅ | ✅ | ❌ |
| `lead/delete/<id>/` | `delete_lead` | `lead.delete` | ✅ | ✅ | ❌ | ❌ |
| `lead/convert/<lead_id>/` | `convert_lead` | `lead.convert` | ✅ | ✅ | ✅ | ❌ |
| `lead/customer/prefill/<lead_id>/` | `get_lead_to_customer_prefill` | `lead.convert` | ✅ | ✅ | ✅ | ❌ |
| `leads/unconverted/` | `get_unconverted_leads` | `lead.view` | ✅ | ✅ | ✅ | ✅ |
| `leads/by-source/` | `leads_by_source` | `lead.view` | ✅ | ✅ | ✅ | ✅ |

### 6.2 Deals
| URL | View Function | Permission | Admin | Manager | Sales Agent | Support Agent |
|---|---|---|:---:|:---:|:---:|:---:|
| `deal/add/` | `add_deal` | `deal.create` | ✅ | ✅ | ✅ | ❌ |
| `deal/view/` | `view_deals` | `deal.view` | ✅ | ✅ | ✅ | ✅ |
| `deal/single/view/<id>/` | `view_single_deals` | `deal.view` | ✅ | ✅ | ✅ | ✅ |
| `deal/update/<id>/` | `update_deal` | `deal.edit` | ✅ | ✅ | ✅ | ❌ |
| `deal/delete/<id>/` | `delete_deal` | `deal.delete` | ✅ | ✅ | ❌ | ❌ |
| `deals/linkable/` | `get_linkable_deals` | `deal.view` | ✅ | ✅ | ✅ | ✅ |

### 6.3 Customers
| URL | View Function | Permission | Admin | Manager | Sales Agent | Support Agent |
|---|---|---|:---:|:---:|:---:|:---:|
| `customer/add/` | `add_customer` | `customer.create` | ✅ | ✅ | ✅ | ❌ |
| `customer/view/` | `view_customers` | `customer.view` | ✅ | ✅ | ✅ | ✅ |
| `customer/single/view/<id>/` | `view_single_customer` | `customer.view` | ✅ | ✅ | ✅ | ✅ |
| `customer/update/<id>/` | `update_customer` | `customer.edit` | ✅ | ✅ | ✅ | ✅ |
| `customer/delete/<id>/` | `delete_customer` | `customer.delete` | ✅ | ✅ | ❌ | ❌ |

### 6.4 Accounts
| URL | View Function | Permission | Admin | Manager | Sales Agent | Support Agent |
|---|---|---|:---:|:---:|:---:|:---:|
| `account/add/` | `add_account` | `account.create` | ✅ | ✅ | ✅ | ❌ |
| `account/view/` | `view_accounts` | `account.view` | ✅ | ✅ | ✅ | ✅ |
| `account/single/view/<id>/` | `view_single_account` | `account.view` | ✅ | ✅ | ✅ | ✅ |
| `account/update/<id>/` | `update_account` | `account.edit` | ✅ | ✅ | ✅ | ❌ |
| `account/delete/<id>/` | `delete_account` | `account.delete` | ✅ | ✅ | ❌ | ❌ |

### 6.5 Tasks
| URL | View Function | Permission | Admin | Manager | Sales Agent | Support Agent |
|---|---|---|:---:|:---:|:---:|:---:|
| `task/add/` | `add_task` | `task.create` | ✅ | ✅ | ✅ | ✅ |
| `task/view/` | `view_tasks` | `task.view` | ✅ | ✅ | ✅ | ✅ |
| `task/single/view/<id>/` | `view_single_task` | `task.view` | ✅ | ✅ | ✅ | ✅ |
| `task/update/<id>/` | `update_task` | `task.edit` | ✅ | ✅ | ✅ | ✅ |
| `task/delete/<id>/` | `delete_task` | `task.delete` | ✅ | ✅ | ❌ | ❌ |

### 6.6 Meetings
| URL | View Function | Permission | Admin | Manager | Sales Agent | Support Agent |
|---|---|---|:---:|:---:|:---:|:---:|
| `meeting/add/` | `add_meeting` | `meeting.create` | ✅ | ✅ | ✅ | ✅ |
| `meeting/view/` | `view_meetings` | `meeting.view` | ✅ | ✅ | ✅ | ✅ |
| `meeting/single/view/<id>/` | `view_single_meeting` | `meeting.view` | ✅ | ✅ | ✅ | ✅ |
| `meeting/update/<id>/` | `update_meeting` | `meeting.edit` | ✅ | ✅ | ✅ | ✅ |
| `meeting/delete/<id>/` | `delete_meeting` | `meeting.delete` | ✅ | ✅ | ❌ | ❌ |

### 6.7 Calls & Twilio
| URL | View Function | Permission | Admin | Manager | Sales Agent | Support Agent |
|---|---|---|:---:|:---:|:---:|:---:|
| `call/add/` | `add_call` | `call.create` | ✅ | ✅ | ✅ | ✅ |
| `call/view/` | `view_calls` | `call.view` | ✅ | ✅ | ✅ | ✅ |
| `call/single/view/<id>/` | `view_single_call` | `call.view` | ✅ | ✅ | ✅ | ✅ |
| `call/update/<id>/` | `update_call` | `call.edit` | ✅ | ✅ | ❌ | ❌ |
| `call/delete/<id>/` | `delete_call` | `call.delete` | ✅ | ✅ | ❌ | ❌ |
| `calls/dial-out/` | `dial_out` | `call.dial` | ✅ | ✅ | ✅ | ✅ |
| `calls/history/` | `call_history` | `call.view` | ✅ | ✅ | ✅ | ✅ |
| `calls/twilio-settings/` | `get_twilio_settings` | `twilio.view` | ✅ | ❌ | ❌ | ❌ |
| `calls/twilio-settings/save/` | `save_twilio_settings` | `twilio.manage` | ✅ | ❌ | ❌ | ❌ |
| `calls/twilio-settings/disconnect/` | `disconnect_twilio` | `twilio.manage` | ✅ | ❌ | ❌ | ❌ |
| `calls/connect-twiml/` | `connect_twiml` | *None (Webhook)* | — | — | — | — |
| `calls/status-callback/` | `call_status_callback` | *None (Webhook)* | — | — | — | — |

### 6.8 Staff Management
| URL | View Function | Permission | Admin | Manager | Sales Agent | Support Agent |
|---|---|---|:---:|:---:|:---:|:---:|
| `staff/add/` | `add_staff` | `staff.create` | ✅ | ✅ | ❌ | ❌ |
| `staff/view/` | `view_staff` | `staff.view` | ✅ | ✅ | ❌ | ❌ |
| `staff/single/view/<id>/` | `view_single_staff` | `staff.view` | ✅ | ✅ | ❌ | ❌ |
| `staff/update/<id>/` | `update_staff` | `staff.edit` | ✅ | ✅ | ❌ | ❌ |
| `staff/delete/<id>/` | `delete_staff` | `staff.delete` | ✅ | ❌ | ❌ | ❌ |

### 6.9 Products & Services
| URL | View Function | Permission | Admin | Manager | Sales Agent | Support Agent |
|---|---|---|:---:|:---:|:---:|:---:|
| `product/add/` | `add_product` | `product.create` | ✅ | ✅ | ❌ | ❌ |
| `product/view/` | `view_products` | `product.view` | ✅ | ✅ | ✅ | ✅ |
| `product/single/view/<id>/` | `view_single_product` | `product.view` | ✅ | ✅ | ✅ | ✅ |
| `product/update/<id>/` | `update_product` | `product.edit` | ✅ | ✅ | ❌ | ❌ |
| `product/delete/<id>/` | `delete_product` | `product.delete` | ✅ | ✅ | ❌ | ❌ |
| `service/add/` | `add_service` | `service.create` | ✅ | ✅ | ❌ | ❌ |
| `service/view/` | `view_services` | `service.view` | ✅ | ✅ | ✅ | ✅ |
| `service/single/view/<id>/` | `view_single_service` | `service.view` | ✅ | ✅ | ✅ | ✅ |
| `service/update/<id>/` | `update_service` | `service.edit` | ✅ | ✅ | ❌ | ❌ |
| `service/delete/<id>/` | `delete_service` | `service.delete` | ✅ | ✅ | ❌ | ❌ |

### 6.10 Price Books & Items
| URL | View Function | Permission | Admin | Manager | Sales Agent | Support Agent |
|---|---|---|:---:|:---:|:---:|:---:|
| `pricebooks/add/` | `add_price_book` | `pricebook.create` | ✅ | ✅ | ❌ | ❌ |
| `pricebooks/view/` | `view_price_books` | `pricebook.view` | ✅ | ✅ | ✅ | ❌ |
| `pricebooks/single/view/<id>/` | `view_single_price_book` | `pricebook.view` | ✅ | ✅ | ✅ | ❌ |
| `pricebooks/update/<id>/` | `update_price_book` | `pricebook.edit` | ✅ | ✅ | ❌ | ❌ |
| `pricebooks/delete/<id>/` | `delete_price_book` | `pricebook.delete` | ✅ | ✅ | ❌ | ❌ |
| `pricebook/items/add/` | `add_price_book_item` | `pricebook.create` | ✅ | ✅ | ❌ | ❌ |
| `pricebook/items/view/` | `view_price_book_items` | `pricebook.view` | ✅ | ✅ | ✅ | ❌ |
| `pricebook/items/single/view/<id>/` | `view_single_price_book_item` | `pricebook.view` | ✅ | ✅ | ✅ | ❌ |
| `pricebook/items/update/<id>/` | `update_price_book_item` | `pricebook.edit` | ✅ | ✅ | ❌ | ❌ |
| `pricebook/items/delete/<id>/` | `delete_price_book_item` | `pricebook.delete` | ✅ | ✅ | ❌ | ❌ |

### 6.11 Quotes, Sales Orders, Invoices
| URL | View Function | Permission | Admin | Manager | Sales Agent | Support Agent |
|---|---|---|:---:|:---:|:---:|:---:|
| `quote/add/` | `add_quote` | `quote.create` | ✅ | ✅ | ❌ | ❌ |
| `quote/view/` | `view_quotes` | `quote.view` | ✅ | ✅ | ✅ | ❌ |
| `quote/single/view/<id>/` | `view_single_quote` | `quote.view` | ✅ | ✅ | ✅ | ❌ |
| `quote/update/<id>/` | `update_quote` | `quote.edit` | ✅ | ✅ | ❌ | ❌ |
| `quote/delete/<id>/` | `delete_quote` | `quote.delete` | ✅ | ✅ | ❌ | ❌ |
| `salesorder/add/` | `add_sales_order` | `salesorder.create` | ✅ | ✅ | ❌ | ❌ |
| `salesorder/view/` | `view_sales_orders` | `salesorder.view` | ✅ | ✅ | ✅ | ❌ |
| `salesorder/single/view/<id>/` | `view_single_sales_order` | `salesorder.view` | ✅ | ✅ | ✅ | ❌ |
| `salesorder/update/<id>/` | `update_sales_order` | `salesorder.edit` | ✅ | ✅ | ❌ | ❌ |
| `salesorder/delete/<id>/` | `delete_sales_order` | `salesorder.delete` | ✅ | ✅ | ❌ | ❌ |
| `salesorder/quote-prefill/<quote_id>/` | `get_quote_prefill` | `salesorder.create` | ✅ | ✅ | ❌ | ❌ |
| `invoice/add/` | `add_invoice` | `invoice.create` | ✅ | ✅ | ❌ | ❌ |
| `invoice/view/` | `view_invoices` | `invoice.view` | ✅ | ✅ | ✅ | ❌ |
| `invoice/single/view/<id>/` | `view_single_invoice` | `invoice.view` | ✅ | ✅ | ✅ | ❌ |
| `invoice/update/<id>/` | `update_invoice` | `invoice.edit` | ✅ | ✅ | ❌ | ❌ |
| `invoice/delete/<id>/` | `delete_invoice` | `invoice.delete` | ✅ | ✅ | ❌ | ❌ |
| `invoice/<pk>/pdf/` | `invoice_pdf` | `invoice.view` | ✅ | ✅ | ✅ | ❌ |
| `invoice/sales-order-prefill/<id>/` | `get_sales_order_prefill` | `invoice.create` | ✅ | ✅ | ❌ | ❌ |

### 6.12 Vendors & Purchase Orders
| URL | View Function | Permission | Admin | Manager | Sales Agent | Support Agent |
|---|---|---|:---:|:---:|:---:|:---:|
| `vendor/add/` | `add_vendor` | `vendor.create` | ✅ | ✅ | ❌ | ❌ |
| `vendor/view/` | `view_vendors` | `vendor.view` | ✅ | ✅ | ❌ | ❌ |
| `vendor/single/view/<id>/` | `view_single_vendor` | `vendor.view` | ✅ | ✅ | ❌ | ❌ |
| `vendor/update/<id>/` | `update_vendor` | `vendor.edit` | ✅ | ✅ | ❌ | ❌ |
| `vendor/delete/<id>/` | `delete_vendor` | `vendor.delete` | ✅ | ✅ | ❌ | ❌ |
| `vendor/prefill/<vendor_id>/` | `get_vendor_prefill` | `vendor.view` | ✅ | ✅ | ❌ | ❌ |
| `purchaseorder/add/` | `add_purchase_order` | `purchaseorder.create` | ✅ | ✅ | ❌ | ❌ |
| `purchaseorder/view/` | `view_purchase_orders` | `purchaseorder.view` | ✅ | ✅ | ❌ | ❌ |
| `purchaseorder/single/view/<id>/` | `view_single_purchase_order` | `purchaseorder.view` | ✅ | ✅ | ❌ | ❌ |
| `purchaseorder/update/<id>/` | `update_purchase_order` | `purchaseorder.edit` | ✅ | ✅ | ❌ | ❌ |
| `purchaseorder/delete/<id>/` | `delete_purchase_order` | `purchaseorder.delete` | ✅ | ✅ | ❌ | ❌ |

### 6.13 Cases & Case Solutions
| URL | View Function | Permission | Admin | Manager | Sales Agent | Support Agent |
|---|---|---|:---:|:---:|:---:|:---:|
| `case/add/` | `add_case` | `case.create` | ✅ | ✅ | ❌ | ✅ |
| `case/view/` | `view_cases` | `case.view` | ✅ | ✅ | ❌ | ✅ |
| `case/single/view/<id>/` | `view_single_case` | `case.view` | ✅ | ✅ | ❌ | ✅ |
| `case/update/<id>/` | `update_case` | `case.edit` | ✅ | ✅ | ❌ | ✅ |
| `case/delete/<id>/` | `delete_case` | `case.delete` | ✅ | ✅ | ❌ | ❌ |
| `casesolutions/add/` | `add_case_solution` | `casesolution.create` | ✅ | ✅ | ❌ | ✅ |
| `casesolutions/view/` | `view_case_solutions` | `casesolution.view` | ✅ | ✅ | ❌ | ✅ |
| `casesolutions/single/view/<id>/` | `view_single_case_solution` | `casesolution.view` | ✅ | ✅ | ❌ | ✅ |
| `casesolutions/update/<id>/` | `update_case_solution` | `casesolution.edit` | ✅ | ✅ | ❌ | ✅ |
| `casesolutions/delete/<id>/` | `delete_case_solution` | `casesolution.delete` | ✅ | ✅ | ❌ | ❌ |

### 6.14 Picklists, Reports & Meta Integration
| URL | View Function | Permission | Admin | Manager | Sales Agent | Support Agent |
|---|---|---|:---:|:---:|:---:|:---:|
| `picklists/view/` | `view_picklists` | `picklist.view` | ✅ | ✅ | ✅ | ✅ |
| `picklists/add/` | `add_picklist_option` | `picklist.create` | ✅ | ❌ | ❌ | ❌ |
| `picklists/update/<id>/` | `update_picklist_option` | `picklist.edit` | ✅ | ❌ | ❌ | ❌ |
| `picklists/delete/<id>/` | `delete_picklist_option` | `picklist.delete` | ✅ | ❌ | ❌ | ❌ |
| `report/dashboard/` | `report_view` | `report.view` | ✅ | ✅ | ✅ | ✅ |
| `report/pdf/` | `report_pdf` | `report.export` | ✅ | ✅ | ❌ | ❌ |
| `integrations/meta/connect/` | `meta_connect` | `integration.manage` | ✅ | ❌ | ❌ | ❌ |
| `integrations/meta/disconnect/` | `meta_disconnect` | `integration.manage` | ✅ | ❌ | ❌ | ❌ |
| `integrations/meta/status/` | `meta_status` | `integration.view` | ✅ | ❌ | ❌ | ❌ |

### 6.15 Public / Webhook / Personal Endpoints (No Role Check)
| URL | View Function | Reason |
|---|---|---|
| `staff/signup/` | `user_signup` | Public registration |
| `staff/login/` | `user_login` | Public authentication |
| `staff/logout/` | `user_logout` | Any authenticated user |
| `staff/acceptinvitation/` | `accept_invitation` | Public token acceptance |
| `calls/connect-twiml/` | `connect_twiml` | Twilio incoming webhook |
| `calls/status-callback/` | `call_status_callback` | Twilio status callback |
| `integrations/meta/callback/` | `meta_callback` | Meta OAuth callback |
| `webhooks/meta/` | `meta_webhook` | Meta platform webhook |
| `profile/view/` | `get_profile` | Personal user profile |
| `profile/update/` | `update_profile` | Personal user profile |
| `change-password/` | `change_password` | Personal password change |
| `preferences/` | `notification_preferences` | Personal notifications |
| `notifications/` | `get_notifications` | Personal notifications |
| `notifications/unread-count/` | `get_unread_count` | Personal notifications |
| `notifications/<id>/read/` | `mark_notification_read` | Personal notifications |
| `notifications/read-all/` | `mark_all_notifications_read` | Personal notifications |

---

## 7. Verification & Testing

1. **Django System Check**:
   ```bash
   python manage.py check
   ```
   Output: `System check identified no issues (0 silenced).`

2. **Automated Test Suite (`AdminApp.tests`)**:
   ```bash
   python manage.py test AdminApp
   ```
   Output: `Ran 13 tests in 37.658s. OK.`
   All 13 unit tests passed, covering role permission logic, allowed access, forbidden access across all roles, and edge cases.
