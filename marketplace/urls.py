from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('products/', views.available_products, name='available_products'),
    path('market-rates/', views.market_rates, name='market_rates'),
    path('forms/', views.forms_hub, name='forms_hub'),
    path('orders/', views.orders_status, name='orders_status'),
    path('advisory/', views.crop_advisory, name='crop_advisory'),
    path('farmer-login/', views.farmer_login, name='farmer_login'),
    path('buyer-login/', views.buyer_login, name='buyer_login'),
    path('buyers/', views.buyer_contacts, name='buyer_contacts'),
]