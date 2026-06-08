from django.urls import path
from AdminApp import views

urlpatterns= [
    path('lead/add/', views.add_lead, name='lead-add'),
    path('lead/view/', views.view_leads, name='lead-view'),
    path('lead/update/<int:id>/', views.update_lead, name='lead-update'),
    path('lead/delete/<int:id>/', views.delete_lead, name='lead-delete'),

    path('deal/add/', views.add_deal, name='deal-add'),
    path('deal/view/', views.view_deals, name='deal-view'),
    path('deal/update/<int:id>/', views.update_deal, name='deal-update'),
    path('deal/delete/<int:id>/', views.delete_deal, name='deal-delete'),

    path('customer/add/', views.add_customer, name='customer-add'),
    path('customer/view/', views.view_customers, name='customer-view'),
    path('customer/update/<int:id>/', views.update_customer, name='customer-update'),
    path('customer/delete/<int:id>/', views.delete_customer, name='customer-delete'),

    path('task/add/', views.add_task, name='task-add'),
    path('task/view/', views.view_tasks, name='task-view'),
    path('task/update/<int:id>/', views.update_task, name='task-update'),
    path('task/delete/<int:id>/', views.delete_task, name='task-delete'),

    path('staff/add/', views.add_staff, name='staff-add'),
    path('staff/view/', views.view_staff, name='staff-view'),
    path('staff/update/<int:id>/', views.update_staff, name='staff-update'),
    path('staff/delete/<int:id>/', views.delete_staff, name='staff-delete'),

    path('report/dashboard/', views.report_view, name='report-dashboard'),

    path('leads/<int:lead_id>/convert/', views.convert_lead_to_deal, name='lead-to-deal'),
    path('leads/unconverted/', views.get_unconverted_leads, name='unconverted-leads'),
]