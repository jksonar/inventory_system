from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.dashboard_home, name='home'),
    path('alerts/', views.alerts_list, name='alerts'),
    path('activity-logs/', views.activity_logs, name='activity_logs'),
]