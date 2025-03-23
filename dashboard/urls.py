"""
URL configuration for Web_ARMS project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import path
from . import views 
from .views import add_student, teacher_portal_view,add_subject
from django.conf.urls.static import static
from django.conf import settings
from django.contrib import admin
urlpatterns = [
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('students/', views.students_view, name='students'),
    path('teachers/', views.teachers_view, name='teachers'),
    path('add_teacher/', views.add_teacher, name='add_teacher'),
    path('delete-teacher/', views.delete_teacher, name='delete_teacher'),
    path('add_student/', views.add_student, name='add_student'),
    path('teacher-portal/', teacher_portal_view, name='teacherPortal'),
    path('edit_teacher/', views.edit_teacher, name='edit_teacher'),
    path('add-subject', add_subject, name='add_subject'),
    path('add-section/', views.add_section, name='add_section'),
    path('sections/', views.sections_view, name='sections'),
    path('delete-section/<int:pk>/', views.delete_section, name='delete_section'),
    path('edit-section/<int:pk>/', views.edit_section, name='edit_section'),
    path('add-section/', views.add_section, name='add_section'),
    path('enrollment/', views.enrollment_view, name='enrollment'),
    path('add-enrollment/', views.add_enrollment, name='add_enrollment'),
    path('edit-enrollment/', views.edit_enrollment, name='edit_enrollment'),
    path('delete-enrollment/', views.delete_enrollment, name='delete_enrollment'),
    path('edit-student/', views.edit_student, name='edit_student'),
    path('create-student-account/', views.create_student_account, name='create_student_account'),
    path('student/<int:student_id>/grades/', views.student_grades_view, name='student_grades'),
    path('grades/', views.grades_view, name='grades'),
    path('add-grade/', views.add_grade, name='add_grade'),
    path('student-profile/<int:student_id>/', views.student_profile_view, name='student_profile'),
    path('get_sections/', views.get_sections, name='get_sections'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)



admin.site.site_header = "Web ARMS"
admin.site.site_title = "Web ARMS"
admin.site.index_title = "Welcome to Web ARMS"  