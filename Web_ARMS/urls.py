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


urlpatterns = [
    path('admin/', admin.site.urls),
    path('administrator/', include(('dashboard.urls', 'dashboard'), namespace='administrator')),
    path('teacher/', include('TeacherPortal.urls')),
    path('', include('login.urls')),
    path('student-profile/<int:student_id>/', dashboard_views.student_profile_view, name='student_profile'),
    path('student/', include('StudentProfiles.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
