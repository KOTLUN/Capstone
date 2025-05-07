from django.db import models
from django.conf import settings
from django.utils import timezone
import os

def form_upload_path(instance, filename):
    """Generate upload path for form files"""
    date = timezone.now().strftime('%Y/%m/%d')
    return os.path.join('forms', date, filename)

class SchoolForm(models.Model):
    CATEGORY_CHOICES = [
        ('enrollment', 'Enrollment'),
        ('grades', 'Grades'),
        ('attendance', 'Attendance'),
        ('financial', 'Financial'),
        ('other', 'Other'),
    ]

    title = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    description = models.TextField(blank=True, default='')
    file = models.FileField(upload_to=form_upload_path)
    uploaded_by = models.CharField(max_length=150)
    date_uploaded = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-date_uploaded']

    def __str__(self):
        return self.title

    def get_category_display(self):
        return dict(self.CATEGORY_CHOICES).get(self.category, self.category)

    @property
    def file_icon_class(self):
        """Return appropriate Font Awesome icon class based on file extension"""
        ext = os.path.splitext(self.file.name)[1].lower()
        icon_map = {
            '.pdf': 'fa-file-pdf',
            '.doc': 'fa-file-word',
            '.docx': 'fa-file-word',
            '.xls': 'fa-file-excel',
            '.xlsx': 'fa-file-excel',
            '.ppt': 'fa-file-powerpoint',
            '.pptx': 'fa-file-powerpoint',
            '.jpg': 'fa-file-image',
            '.jpeg': 'fa-file-image',
            '.png': 'fa-file-image',
        }
        return icon_map.get(ext, 'fa-file')

class TeacherForm(models.Model):
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    form = models.ForeignKey(SchoolForm, on_delete=models.CASCADE)
    is_completed = models.BooleanField(default=False)
    completed_date = models.DateTimeField(null=True, blank=True)
    date_assigned = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['teacher', 'form']
        ordering = ['-date_assigned']

    def __str__(self):
        return f"{self.teacher.username} - {self.form.title}"

class FormSubmission(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    teacher_form = models.ForeignKey(TeacherForm, on_delete=models.CASCADE)
    submitted_file = models.FileField(upload_to='form_submissions/')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    feedback = models.TextField(blank=True)
    submitted_date = models.DateTimeField(auto_now_add=True)
    review_date = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_submissions'
    )

    class Meta:
        ordering = ['-submitted_date']

    def __str__(self):
        return f"{self.teacher_form} - {self.status}" 