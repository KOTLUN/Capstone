from django.urls import path
from . import views

urlpatterns = [
    # ... your existing urls ...
    path('profile/<int:student_id>/', views.student_profile, name='student_profile'),
    path('dashboard/<int:student_id>/', views.student_dashboard, name='student_dashboard'),
    path('profile/<int:student_id>/update/', views.update_profile, name='update_profile'),
]