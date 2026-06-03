from django.urls import path
from AdminApp import views

urlpatterns= [
    path('add_lead', views.add_lead, name='add_lead'),
    path('view_leads', views.view_leads, name='view_leads'),
    path('update_lead/<int:id>', views.update_lead, name='update_lead'),
    path('delete_lead/<int:id>', views.delete_lead, name='delete_lead'),

    path('add_deal', views.add_deal, name='add_deal'),
    path('view_deals', views.view_deals, name='view_deals'),
    path('update_deal/<int:id>', views.update_deal, name='update_deal'),
    path('delete_deal/<int:id>', views.delete_deal, name='delete_deal'),
]