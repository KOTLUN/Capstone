from django.db import models
from django.utils import timezone
from dashboard.models import Student, Subject, Teachers

class Grade(models.Model):
    student = models.CharField(max_length=20)  # Student ID
    course = models.CharField(max_length=20)   # Subject ID
    grade = models.DecimalField(max_digits=5, decimal_places=2)
    quarter = models.CharField(max_length=20)
    school_year = models.CharField(max_length=20)
    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['student', 'course', 'quarter', 'school_year']

    def __str__(self):
        return f"{self.student} - Q{self.quarter}: {self.grade}"
    
    class Meta:
        ordering = ['-date_created']

