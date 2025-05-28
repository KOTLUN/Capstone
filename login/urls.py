# myproject/urls.py

from django.contrib import admin
from django.urls import path
from login import views
from django.contrib.auth import views as auth_views
from .views import (
    login_view, logout_view, home_view, 
    CustomPasswordResetView, CustomPasswordResetDoneView,
    CustomPasswordResetConfirmView, CustomPasswordResetCompleteView,
    forgot_password, force_password_change, proceed_to_login
)


urlpatterns = [

    path('', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('home/', views.home_view, name='home'),
    path('force-password-change/', views.force_password_change, name='force_password_change'),
    path('proceed-to-login/', views.proceed_to_login, name='proceed_to_login'),

    # Custom password reset URLs
    path('password-reset/', CustomPasswordResetView.as_view(), name='password_reset'),
    path('password-reset/done/', CustomPasswordResetDoneView.as_view(), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', CustomPasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('reset/done/', CustomPasswordResetCompleteView.as_view(), name='password_reset_complete'),
    path('forgot-password/', forgot_password, name='forgot_password'),

]
