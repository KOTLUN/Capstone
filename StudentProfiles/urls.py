from django.urls import path
from . import views

urlpatterns = [
    # ... your existing urls ...
    path('profile/<int:student_id>/', views.student_profile, name='student_profile'),
]