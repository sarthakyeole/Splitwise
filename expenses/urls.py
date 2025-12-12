from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('groups/create/', views.create_group, name='create_group'),
    path('groups/<int:group_id>/', views.group_detail, name='group_detail'),
    path('groups/<int:group_id>/add-expense/', views.add_expense, name='add_expense'),
]