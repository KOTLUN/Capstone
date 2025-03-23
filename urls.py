from django.urls import path
from . import views

urlpatterns = [
    path('enrollment/', views.enrollment_page, name='enrollment_page'),
    path('api/students/', views.get_students, name='get_students'),
    path('api/school-years/', views.get_school_years, name='get_school_years'),
    path('api/grades/', views.get_grades, name='get_grades'),
    path('api/sections/', views.get_sections, name='get_sections'),
    path('api/enroll/', views.enroll_student, name='enroll_student'),
]