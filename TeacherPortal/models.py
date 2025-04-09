from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from .sync_utils import sync_grades_to_dashboard

class Grade(models.Model):
    QUARTER_CHOICES = [
        ('1', 'First Quarter'),
        ('2', 'Second Quarter'),
        ('3', 'Third Quarter'),
        ('4', 'Fourth Quarter'),
    ]
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('returned', 'Returned for Revision'),
    ]
    
    student = models.CharField(max_length=20)  # Student ID
    course = models.CharField(max_length=20, default='')   # Subject ID
    grade = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(100)])
    quarter = models.CharField(max_length=2, choices=QUARTER_CHOICES)
    school_year = models.CharField(max_length=20)
    teacher = models.CharField(max_length=100, default='')  # Teacher who entered the grade
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)
    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)
    date_submitted = models.DateTimeField(null=True, blank=True)
    date_approved = models.DateTimeField(null=True, blank=True)
    uploaded_at = models.DateTimeField(default=timezone.now)  # When the grade was uploaded

    class Meta:
        unique_together = ['student', 'course', 'quarter', 'school_year']
        ordering = ['-date_created']

    def __str__(self):
        return f"{self.student} - {self.course} - Q{self.quarter} - {self.grade}"
    
    def save(self, *args, **kwargs):
        # Set default status if not provided
        if self.status is None:
            self.status = 'draft'
            
        # If status changed to submitted, update the submitted timestamp
        if self.status == 'submitted' and not self.date_submitted:
            self.date_submitted = timezone.now()
            
        # If status changed to approved, update the approved timestamp
        if self.status == 'approved' and not self.date_approved:
            self.date_approved = timezone.now()
            
        super().save(*args, **kwargs)
        
        # Sync with dashboard after saving
        try:
            sync_grades_to_dashboard()
        except Exception as e:
            print(f"Error syncing grade to dashboard: {e}")
    
    @property
    def letter_grade(self):
        """Convert numerical grade to letter grade"""
        if self.grade >= 90:
            return "A"
        elif self.grade >= 80:
            return "B"
        elif self.grade >= 70:
            return "C"
        elif self.grade >= 60:
            return "D"
        else:
            return "F"
    
    @property
    def is_passing(self):
        """Check if grade is passing (assumes 75 as passing)"""
        return self.grade >= 75


class GradeComment(models.Model):
    """Model for comments on grades (teachers, coordinators, etc.)"""
    grade = models.ForeignKey(Grade, on_delete=models.CASCADE, related_name='comments')
    author = models.CharField(max_length=100)  # Teacher ID
    comment = models.TextField()
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_created']

    def __str__(self):
        return f"Comment on {self.grade} by {self.author}"

