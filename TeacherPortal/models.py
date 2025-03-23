from django.db import models
from django.utils import timezone
from dashboard.models import Student, Subject, Teachers

class Grade(models.Model):
    student = models.CharField(max_length=100, default='')  # Student ID or name
    grade = models.FloatField(default=0.0)                 # The actual grade value
    quarter = models.IntegerField(default=1)             # Quarter (1, 2, 3, or 4)
    school_year = models.CharField(max_length=20, default='')  # e.g., "2023-2024"
    teacher = models.CharField(max_length=100, default='')  # Teacher who uploaded the grade
    uploaded_at = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"{self.student} - Q{self.quarter}: {self.grade}"
    
    class Meta:
        ordering = ['-uploaded_at']

