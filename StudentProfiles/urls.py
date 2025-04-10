from django.urls import path
from . import views

urlpatterns = [
    # ... your existing urls ...
    path('profile/<int:student_id>/', views.student_profile, name='student_profile'),
    path('dashboard/<int:student_id>/', views.student_dashboard, name='student_dashboard'),
    path('profile/<int:student_id>/update/', views.update_profile, name='update_profile'),
    path('dashboard/<int:student_id>/create-test-grades/', views.create_test_grades, name='create_test_grades'),
    path('dashboard/<int:student_id>/diagnostics/', views.diagnostics, name='diagnostics'),
]