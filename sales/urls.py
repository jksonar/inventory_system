from django.urls import path
from . import views

app_name = 'sales'

urlpatterns = [
    path('', views.sales_list, name='sales_list'),
    path('add/', views.sale_add, name='sale_add'),
    path('<int:pk>/', views.sale_detail, name='sale_detail'),
    path('<int:pk>/edit/', views.sale_edit, name='sale_edit'),
    path('<int:pk>/delete/', views.sale_delete, name='sale_delete'),
    path('<int:pk>/receipt/', views.sale_receipt, name='sale_receipt'),
]