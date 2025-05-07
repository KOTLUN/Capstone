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
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from dashboard import views as dashboard_views
from login import views as login_views


urlpatterns = [
    path('', login_views.root_view, name='root'),
    path('admin/', admin.site.urls),
    path('social-auth/', include('social_django.urls', namespace='social')),
    path('dashboard/', include(('dashboard.urls', 'dashboard'), namespace='dashboard')),
    path('teacher/', include(('TeacherPortal.urls', 'TeacherPortal'), namespace='TeacherPortal')),
    path('login/', include('login.urls')),
    path('student-profile/<int:student_id>/', dashboard_views.student_profile_view, name='student_profile'),
    path('student/', include('StudentProfiles.urls')),
    
    # Add these new URL patterns for dashboard redirects
    path('teacher-dashboard/', login_views.teacher_dashboard, name='teacher_dashboard'),
    path('admin-dashboard/', login_views.admin_dashboard, name='admin_dashboard'),
    path('student-dashboard/', login_views.student_dashboard, name='student_dashboard'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) 
