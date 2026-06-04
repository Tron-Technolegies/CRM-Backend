from django.urls import path
from AdminApp import views

urlpatterns= [
    path('lead/add/', views.add_lead, name='lead/add/'),
    path('lead/view/', views.view_leads, name='lead/view/'),
    path('lead/update/<int:id>/', views.update_lead, name='lead/update/<int:id>/'),
    path('lead/delete/<int:id>/', views.delete_lead, name='lead/delete/<int:id>/'),

    path('deal/add/', views.add_deal, name='deal/add/'),
    path('deal/view/', views.view_deals, name='deal/view/'),
    path('deal/update/<int:id>/', views.update_deal, name='deal/update/<int:id>/'),
    path('deal/delete/<int:id>/', views.delete_deal, name='deal/delete/<int:id>/'),

    path('customer/add/', views.add_customer, name='customer/add/'),
    path('customer/view/', views.view_customers, name='customer/view/'),
    path('customer/update/<int:id>/', views.update_customer, name='customer/update/<int:id>/'),
    path('customer/delete/<int:id>/', views.delete_customer, name='customer/delete/<int:id>/'),

    path('task/add/', views.add_task, name='task/add/'),
    path('task/view/', views.view_tasks, name='task/view/'),
    path('task/update/<int:id>/', views.update_task, name='task/update/<int:id>/'),
    path('task/delete/<int:id>/', views.delete_task, name='task/delete/<int:id>/'),

    path('staff/add/', views.add_staff, name='staff/add/'),
    path('staff/view/', views.view_staff, name='staff/view/'),
    path('staff/update/<int:id>/', views.update_staff, name='staff/update/<int:id>/'),
    path('staff/delete/<int:id>/', views.delete_staff, name='staff/delete/<int:id>/'),
]