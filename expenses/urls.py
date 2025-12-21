from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('groups/create/', views.create_group, name='create_group'),
    path('groups/<int:group_id>/quick-settle/', views.quick_settle, name='quick_settle'),
    path('groups/<int:group_id>/activity/', views.activity_log, name='activity_log'),
    path('groups/<int:group_id>/', views.group_detail, name='group_detail'),
    path('groups/<int:group_id>/add-expense/', views.add_expense, name='add_expense'),
    path('accounts/register/', views.register, name='register'),
    path('groups/<int:group_id>/export/csv/', views.export_group_csv, name='export_group_csv'),
]