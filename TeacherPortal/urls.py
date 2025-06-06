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
from . import form_views

app_name = 'TeacherPortal'

urlpatterns = [
    path('profile/', views.profile_view, name='profile'),
    path('edit_profile/', views.update_profile, name='edit_profile'),
    path('logout/', views.logout_view, name='logout'),
    path('subjects/', views.teacher_subjects_view, name='teacher_subjects'),
    path('schedule/', views.teacher_schedule_view, name='teacher_schedule'),
    
    # Grade management
    path('grades/', views.grades_view, name='grades'),
    path('api/update_grade/', views.update_grade, name='update_grade'),
    path('import-grades/', views.import_grades_view, name='import_grades'),
    path('upload-grades/', views.upload_grades, name='upload_grades'),
    path('upload-grades-ajax/', views.upload_grades_ajax, name='upload_grades_ajax'),
    path('confirm-import-grades-ajax/', views.confirm_import_grades_ajax, name='confirm_import_grades_ajax'),
    path('generate-grade-template/', views.generate_grade_template, name='generate_grade_template'),
    
    # Student management
    path('student-registration/', views.student_registration, name='student_registration'),
    path('student-enrollment/', views.student_enrollment, name='student_enrollment'),
    path('get-sections/', views.get_sections, name='get_sections'),
    path('search-student/', views.search_student, name='search_student'),
    path('advisory-enrollment/', views.advisory_enrollment, name='advisory_enrollment'),
    path('search-students/', views.search_students, name='search_students'),
    path('get-enrolled-students/', views.get_enrolled_students, name='get_enrolled_students'),
    path('get_sections_for_subject/', views.get_sections_for_subject, name='get_sections_for_subject'),
    path('subject-students/<int:subject_id>/<int:grade_level>/<str:section_id>/', views.subject_students_view, name='subject_students'),
    path('get-subject-students/', views.get_subject_students, name='get_subject_students'),
    
    # Form management
    path('forms/', form_views.upload_forms_page, name='forms'),
    path('forms/upload/', form_views.upload_form, name='upload_form'),
    path('forms/download/<int:form_id>/', form_views.download_form, name='download_form'),
    path('forms/delete/<int:form_id>/', form_views.delete_form, name='delete_form'),
    path('view-form/<int:form_id>/', form_views.view_form, name='view_form'),
    path('forms-search-ajax/', form_views.forms_search_ajax, name='forms_search_ajax'),
    path('api/get_subjects/', views.get_subjects, name='get_subjects'),
    path('api/get_sections_for_subject/', views.get_sections_for_subject, name='get_sections_for_subject'),
    path('api/generate_grade_template/', views.generate_grade_template, name='generate_grade_template'),
    path('api/upload_grades/', views.upload_grades_ajax, name='upload_grades'),
    path('api/confirm_import_grades/', views.confirm_import_grades_ajax, name='confirm_import_grades'),
    path('preview_grades/', views.preview_grades, name='preview_grades'),
    path('api/subjects/', views.get_teacher_subjects, name='get_teacher_subjects'),
    path('api/sections/', views.get_teacher_sections, name='get_teacher_sections'),
    path('api/upload-grades/', views.upload_grades, name='upload_grades'),
    path('api/events/', views.teacher_events_api, name='teacher_events_api'),
    path('api/get_grades/', views.get_grades, name='get_grades'),
    path('api/get_section_grades/', views.get_section_grades, name='get_section_grades'),
    # New URL for account settings
    path('account/', views.account_settings, name='account_settings'),
    path('registrar/', views.registrar, name='registrar'),
    path('registrar/get_student_grades/', views.get_student_grades, name='get_student_grades'),
    path('calendar/', views.teacher_calendar_view, name='teacher_calendar'),
    path('api/generate_grade_template/', views.generate_grade_template, name='generate_grade_template'),
    path('api/get_all_subjects_sections/', views.get_all_subjects_sections, name='get_all_subjects_sections'),
    path('api/generate_all_templates/', views.generate_all_templates, name='generate_all_templates'),
]





