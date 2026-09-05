from django.urls import path
from AdminApp import views

urlpatterns= [
    path('staff/signup/', views.user_signup, name='signup'),
    path('staff/login/', views.user_login, name='login'),
    path('staff/logout/', views.user_logout, name='logout'),

    path('lead/add/', views.add_lead, name='lead-add'),
    path('lead/view/', views.view_leads, name='lead-view'),
    path('lead/single/view/<int:id>/', views.view_single_lead, name='view-single-lead'),
    path('lead/update/<int:id>/', views.update_lead, name='lead-update'),
    path('lead/delete/<int:id>/', views.delete_lead, name='lead-delete'),

    path('deal/add/', views.add_deal, name='deal-add'),
    path('deal/view/', views.view_deals, name='deal-view'),
    path('deal/single/view/<int:id>/', views.view_single_deals, name='view-single-deals'),
    path('deal/update/<int:id>/', views.update_deal, name='deal-update'),
    path('deal/delete/<int:id>/', views.delete_deal, name='deal-delete'),

    path('customer/add/', views.add_customer, name='customer-add'),
    path('customer/view/', views.view_customers, name='customer-view'),
    path('customer/single/view/<int:id>/', views.view_single_customer, name='view-single-customer'),
    path('customer/update/<int:id>/', views.update_customer, name='customer-update'),
    path('customer/delete/<int:id>/', views.delete_customer, name='customer-delete'),

    path('task/add/', views.add_task, name='task-add'),
    path('task/view/', views.view_tasks, name='task-view'),
    path('task/single/view/<int:id>/', views.view_single_task, name='view-single-task'),
    path('task/update/<int:id>/', views.update_task, name='task-update'),
    path('task/delete/<int:id>/', views.delete_task, name='task-delete'),

    path('staff/acceptinvitation/', views.accept_invitation, name='accept-invitation'),
    path('staff/add/', views.add_staff, name='staff-add'),
    path('staff/view/', views.view_staff, name='staff-view'),
    path('staff/single/view/<int:id>/', views.view_single_staff, name='view-single-staff'),
    path('staff/update/<int:id>/', views.update_staff, name='staff-update'),
    path('staff/delete/<int:id>/', views.delete_staff, name='staff-delete'),

    path('report/dashboard/', views.report_view, name='report-dashboard'),
    path('report/pdf/', views.report_pdf, name='report-pdf'),

    path('lead/customer/prefill/<int:lead_id>/', views.get_lead_to_customer_prefill, name='lead-to-customer'),
    path('lead/convert/<int:lead_id>/', views.convert_lead, name='lead-convert'),
    path('leads/unconverted/', views.get_unconverted_leads, name='unconverted-leads'),
    path('deals/linkable/', views.get_linkable_deals, name='linkable-deals'),

    path('leads/by-source/', views.leads_by_source, name='leads-by-source'),

    path('picklists/view/', views.view_picklists, name='picklists-view'),
    path('picklists/add/', views.add_picklist_option, name='picklists-add'),
    path('picklists/update/<int:id>/', views.update_picklist_option, name='picklists-update'),
    path('picklists/delete/<int:id>/', views.delete_picklist_option, name='picklists-delete'),

    path('account/add/', views.add_account, name='acc-add'),
    path('account/view/', views.view_accounts, name='view-acc'),
    path('account/single/view/<int:id>/', views.view_single_account, name='account-single'),
    path('account/update/<int:id>/', views.update_account, name='update-acc'),
    path('account/delete/<int:id>/', views.delete_account, name='delete-acc'),

    path('quote/add/', views.add_quote, name='quote-add'),
    path('quote/view/', views.view_quotes, name='quote-view'),
    path('quote/single/view/<int:id>/', views.view_single_quote, name='quote-single'),
    path('quote/update/<int:id>/', views.update_quote, name='quote-update'),
    path('quote/delete/<int:id>/', views.delete_quote, name='quote-delete'),

    path('meeting/add/', views.add_meeting, name='meeting-add'),
    path('meeting/view/', views.view_meetings, name='meeting-view'),
    path('meeting/single/view/<int:id>/', views.view_single_meeting, name='meeting-single'),
    path('meeting/update/<int:id>/', views.update_meeting, name='meeting-update'),
    path('meeting/delete/<int:id>/', views.delete_meeting, name='meeting-delete'),

    path('call/add/', views.add_call, name='call-add'),
    path('call/view/', views.view_calls, name='call-view'),
    path('call/single/view/<int:id>/', views.view_single_call, name='call-single'),
    path('call/update/<int:id>/', views.update_call, name='call-update'),
    path('call/delete/<int:id>/', views.delete_call, name='call-delete'),

    path('vendor/prefill/<int:vendor_id>/', views.get_vendor_prefill, name='vendor-prefill'),
    path('vendor/add/', views.add_vendor, name='vendor-add'),
    path('vendor/view/', views.view_vendors, name='vendor-view'),
    path('vendor/single/view/<int:id>/', views.view_single_vendor, name='vendor-single'),
    path('vendor/update/<int:id>/', views.update_vendor, name='vendor-update'),
    path('vendor/delete/<int:id>/', views.delete_vendor, name='vendor-delete'),

    path('product/add/', views.add_product, name='product-add'),
    path('product/view/', views.view_products, name='product-view'),
    path('product/single/view/<int:id>/', views.view_single_product, name='product-single'),
    path('product/update/<int:id>/', views.update_product, name='product-update'),
    path('product/delete/<int:id>/', views.delete_product, name='product-delete'),

    path('pricebooks/add/', views.add_price_book, name='add_price_book'),
    path('pricebooks/view/', views.view_price_books, name='view_price_books'),
    path('pricebooks/single/view/<int:id>/', views.view_single_price_book, name='view_single_price_book'),
    path('pricebooks/update/<int:id>/', views.update_price_book, name='update_price_book'),
    path('pricebooks/delete/<int:id>/', views.delete_price_book, name='delete_price_book'),

    path('pricebook/items/add/', views.add_price_book_item, name='add_price_book_item'),
    path('pricebook/items/view/', views.view_price_book_items, name='view_price_book_items'),
    path('pricebook/items/single/view/<int:id>/', views.view_single_price_book_item, name='view_single_price_book_item'),
    path('pricebook/items/update/<int:id>/', views.update_price_book_item, name='update_price_book_item'),
    path('pricebook/items/delete/<int:id>/', views.delete_price_book_item, name='delete_price_book_item'),

    path('salesorder/add/', views.add_sales_order, name='sales-order-add'),
    path('salesorder/view/', views.view_sales_orders, name='sales-order-view'),
    path('salesorder/single/view/<int:id>/', views.view_single_sales_order, name='sales-order-single'),
    path('salesorder/update/<int:id>/', views.update_sales_order, name='sales-order-update'),
    path('salesorder/delete/<int:id>/', views.delete_sales_order, name='sales-order-delete'),

    path('salesorder/quote-prefill/<int:quote_id>/', views.get_quote_prefill, name='sales-order-quote-prefill'),

    path('invoice/add/', views.add_invoice, name='invoice-add'),
    path('invoice/view/', views.view_invoices, name='invoice-view'),
    path('invoice/single/view/<int:id>/', views.view_single_invoice, name='invoice-single'),
    path('invoice/update/<int:id>/', views.update_invoice, name='invoice-update'),
    path('invoice/delete/<int:id>/', views.delete_invoice, name='invoice-delete'),
    path("invoice/<int:pk>/pdf/", views.invoice_pdf, name="invoice-pdf"),
    
    path('invoice/sales-order-prefill/<int:sales_order_id>/', views.get_sales_order_prefill, name='invoice-sales-order-prefill'),

    path('purchaseorder/add/', views.add_purchase_order, name='purchase-order-add'),
    path('purchaseorder/view/', views.view_purchase_orders, name='purchase-order-view'),
    path('purchaseorder/single/view/<int:id>/', views.view_single_purchase_order, name='purchase-order-single'),
    path('purchaseorder/update/<int:id>/', views.update_purchase_order, name='purchase-order-update'),
    path('purchaseorder/delete/<int:id>/', views.delete_purchase_order, name='purchase-order-delete'),

    path('case/add/', views.add_case, name='case-add'),
    path('case/view/', views.view_cases, name='case-view'),
    path('case/single/view/<int:id>/', views.view_single_case, name='case-single'),
    path('case/update/<int:id>/', views.update_case, name='case-update'),
    path('case/delete/<int:id>/', views.delete_case, name='case-delete'),

    path('casesolutions/add/', views.add_case_solution, name='add_case_solution'),
    path('casesolutions/view/', views.view_case_solutions, name='view_case_solutions'),
    path('casesolutions/single/view/<int:id>/', views.view_single_case_solution, name='view_single_case_solution'),
    path('casesolutions/update/<int:id>/', views.update_case_solution, name='update_case_solution'),
    path('casesolutions/delete/<int:id>/', views.delete_case_solution, name='delete_case_solution'),

    path('service/add/', views.add_service, name='service-add'),
    path('service/view/', views.view_services, name='service-view'),
    path('service/single/view/<int:id>/', views.view_single_service, name='service-single'),
    path('service/update/<int:id>/', views.update_service, name='service-update'),
    path('service/delete/<int:id>/', views.delete_service, name='service-delete'),

    path("profile/view/", views.get_profile, name="profile-view"),
    path("profile/update/", views.update_profile, name="profile-update"),

    path('preferences/', views.notification_preferences, name='notification_preferences'),
    path("notifications/", views.get_notifications, name='get_notifications'),
    path("notifications/unread-count/", views.get_unread_count, name='get_unread_count'),
    path("notifications/<int:id>/read/", views.mark_notification_read, name='mark_notification_read'),
    path("notifications/read-all/", views.mark_all_notifications_read, name='mark_all_notifications_read'),

    path('change-password/', views.change_password, name='change_password'),

    path('integrations/meta/connect/', views.meta_connect, name='meta-connect'),
    path("integrations/meta/disconnect/", views.meta_disconnect, name="meta_disconnect"),
    path('integrations/meta/callback/', views.meta_callback, name='meta-callback'),
    path('webhooks/meta/', views.meta_webhook, name='meta-webhook'),
    path('integrations/meta/status/', views.meta_status, name='meta-status'),

    path('calls/dial-out/', views.dial_out, name='call-dial-out'),
    path('calls/connect-twiml/', views.connect_twiml, name='call-connect-twiml'),
    path('calls/status-callback/', views.call_status_callback, name='call-status-callback'),
    path('calls/history/', views.call_history, name='call-history'),
]