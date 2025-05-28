from django.urls import path
from . import views

urlpatterns = [
    # ... your existing urls ...
    path('profile/<int:student_id>/', views.student_profile, name='student_profile'),
    path('dashboard/<int:student_id>/', views.student_dashboard, name='student_dashboard'),
    path('profile/<int:student_id>/update/', views.update_profile, name='update_profile'),
    path('dashboard/<int:student_id>/create-test-grades/', views.create_test_grades, name='create_test_grades'),
    path('dashboard/<int:student_id>/diagnostics/', views.diagnostics, name='diagnostics'),
    path('admin/all-grades/', views.all_grades, name='all_grades'),
    # New URLs for separate views
    path('grades/<int:student_id>/', views.student_grades, name='student_grades'),
    path('subjects/<int:student_id>/', views.student_subjects, name='student_subjects'),
    path('schedule/<int:student_id>/', views.student_schedule, name='student_schedule'),
    path('analytics/grades/<int:student_id>/', views.get_grade_analytics, name='grade_analytics'),
    path('student/<int:student_id>/change-password/', views.change_password, name='change_password'),
    path('feedback/send/', views.send_feedback, name='send_feedback'),
]