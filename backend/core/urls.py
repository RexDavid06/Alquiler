"""Core / auth API routes."""

from django.urls import path

from . import views

app_name = 'core'

urlpatterns = [
    path('register/', views.register, name='register'),
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    path('me/', views.me, name='me'),
    path('profile/', views.update_profile, name='profile'),
    path('change-password/', views.change_password, name='change-password'),
    path('password-reset/', views.password_reset_request, name='password-reset'),
    path(
        'password-reset/confirm/',
        views.password_reset_confirm,
        name='password-reset-confirm',
    ),
]
