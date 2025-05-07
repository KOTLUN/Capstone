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
from .forms_views import all_forms_view, upload_form, delete_form, submit_form, review_submission
from django.conf.urls.static import static
from django.conf import settings
from django.contrib import admin

app_name = 'dashboard'

def log_admin_activity(user, action, action_type):
    from .models import AdminActivity
    AdminActivity.objects.create(
        admin=user,
        action=action,
        action_type=action_type
    )

urlpatterns = [
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('students/', views.students_view, name='students'),
    path('teachers/', views.teachers_view, name='teachers'),
    path('add_teacher/', views.add_teacher, name='add_teacher'),
    path('delete-teacher/', views.delete_teacher, name='delete_teacher'),
    path('add_student/', views.add_student, name='add_student'),
    path('teacher-portal/', views.teacher_portal_view, name='teacherPortal'),
    path('edit_teacher/', views.edit_teacher, name='edit_teacher'),
    path('add-subject/', views.add_subject, name='add_subject'),
    path('subjects/', views.subject_view, name='subjects'),
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
    path('student-grades/', views.student_grades_view, name='student_grades'),
    path('student-profile/<int:student_id>/', views.student_profile_view, name='student_profile'),
    path('get_sections/', views.get_sections, name='get_sections'),
    path('schedules/', views.schedule_view, name='schedules'),
    path('add_schedule/', views.add_schedule, name='add_schedule'),
    path('get_sections_by_grade/', views.get_sections_by_grade, name='get_sections_by_grade'),
    path('get_available_time_slots/', views.get_available_time_slots, name='get_available_time_slots'),
    path('get-section-schedule/', views.get_section_schedule, name='get_section_schedule'),
    path('get-enrolled-students/', views.get_enrolled_students, name='get_enrolled_students'),
    path('get-enrolled-students/<int:section_id>/', views.get_enrolled_students, name='get_enrolled_students_by_section'),
    path('get-eligible-students/', views.get_eligible_students, name='get_eligible_students'),
    path('admin-profile/', views.admin_profile, name='admin_profile'),
    path('admin-profile/update/', views.admin_profile_update, name='admin_profile_update'),
    path('get_section_grade/', views.get_section_grade, name='get_section_grade'),
    path('school-year-management/', views.school_year_management, name='school_year_management'),
    path('set-active-school-year/', views.set_active_school_year, name='set_active_school_year'),
    path('add-school-year/', views.add_school_year, name='add_school_year'),
    path('get-teacher-schedule/', views.get_teacher_schedule, name='get_teacher_schedule'),
    path('api/dashboard-data/', views.get_dashboard_data, name='dashboard_data'),
    path('get-data/', views.get_dashboard_data, name='get_dashboard_data'),
    path('event/', views.event_calendar, name='event'),
    path('event/add/', views.add_event, name='add_event'),
    path('event/delete/<int:event_id>/', views.delete_event, name='delete_event'),
    # Archive URLs
    path('archive/', views.archive_view, name='archive_view'),
    path('archive/create/', views.archive_data, name='archive_data'),
    path('archive/save/', views.save_archive, name='save_archive'),
    path('archive/<int:archive_id>/', views.view_archive_detail, name='view_archive_detail'),
    # Announcement URLs
    path('announcement/', views.announcement_view, name='announcement'),
    path('announcement/add/', views.add_announcement, name='add_announcement'),
    path('announcement/delete/<int:announcement_id>/', views.delete_announcement, name='delete_announcement'),
    # Form URLs
    path('allforms/', all_forms_view, name='allforms'),
    path('allforms/upload/', upload_form, name='upload_form'),
    path('allforms/delete/<int:form_id>/', delete_form, name='delete_form'),
    path('allforms/submit/<int:form_id>/', submit_form, name='submit_form'),
    path('allforms/review/<int:submission_id>/', review_submission, name='review_submission'),
    # File Upload URLs
    path('edit-subject/', views.edit_subject, name='edit_subject'),
    path('delete-subject/', views.delete_subject, name='delete_subject'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

admin.site.site_header = "Web ARMS"
admin.site.site_title = "Web ARMS"
admin.site.index_title = "Welcome to Web ARMS"  