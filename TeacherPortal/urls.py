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

urlpatterns = [
    path('profile/', views.profile_view, name='profile'),
    path('edit_profile/', views.update_profile, name='edit_profile'),
    path('logout/', views.logout_view, name='logout'),
    # Comment out or remove this line until you create the students_view
    # path('students/', views.students_view, name='students'),
    path('subjects/', views.teacher_subjects_view, name='teacher_subjects'),
    path('schedule/', views.teacher_schedule_view, name='teacher_schedule'),
    path('import-grades/', views.import_grades_view, name='import_grades'),
    path('upload-grades/', views.upload_grades, name='upload_grades'),
    path('upload-grades-ajax/', views.upload_grades_ajax, name='upload_grades_ajax'),
    path('confirm-import-grades-ajax/', views.confirm_import_grades_ajax, name='confirm_import_grades_ajax'),
    path('get-enrolled-students/', views.get_enrolled_students, name='get_enrolled_students'),
    path('student-registration/', views.student_registration, name='student_registration'),
]





