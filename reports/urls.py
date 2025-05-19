from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('', views.reports_home, name='home'),
    path('sales/', views.sales_report, name='sales_report'),
    path('inventory/', views.inventory_report, name='inventory_report'),
    path('low-stock/', views.low_stock_report, name='low_stock_report'),
    path('custom/', views.custom_report, name='custom_report'),
    path('download/<int:pk>/', views.download_report, name='download_report'),
]