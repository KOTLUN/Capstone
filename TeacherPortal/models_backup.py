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


class SchoolForm(models.Model):
    """Model for school forms and documents"""
    
    CATEGORY_CHOICES = [
        ('enrollment', 'Enrollment'),
        ('grades', 'Grades'),
        ('attendance', 'Attendance'),
        ('financial', 'Financial'),
        ('other', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('archived', 'Archived'),
    ]
    
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    file = models.FileField(upload_to='school_forms/')
    file_type = models.CharField(max_length=50, blank=True)  # Will be automatically populated
    file_size = models.PositiveIntegerField(default=0)  # Size in bytes
    uploaded_by = models.CharField(max_length=100)  # User who uploaded
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    school_year = models.CharField(max_length=20, blank=True, null=True)
    date_uploaded = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)
    downloads = models.PositiveIntegerField(default=0)  # Track number of downloads
    
    class Meta:
        ordering = ['-date_uploaded']
        
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        # Set file type based on extension
        if self.file:
            file_extension = self.file.name.split('.')[-1].lower()
            
            # Map extensions to friendly types
            extension_map = {
                'pdf': 'PDF Document',
                'doc': 'Word Document',
                'docx': 'Word Document',
                'xls': 'Excel Spreadsheet',
                'xlsx': 'Excel Spreadsheet',
                'ppt': 'PowerPoint Presentation',
                'pptx': 'PowerPoint Presentation',
                'jpg': 'Image',
                'jpeg': 'Image',
                'png': 'Image',
                'txt': 'Text Document',
            }
            
            self.file_type = extension_map.get(file_extension, file_extension.upper())
            
            # Set file size if available
            if hasattr(self.file, 'size'):
                self.file_size = self.file.size
                
        super().save(*args, **kwargs)
    
    @property
    def file_size_display(self):
        """Return a human-readable file size"""
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} TB"
    
    @property
    def file_extension(self):
        """Return the file extension"""
        if self.file:
            return self.file.name.split('.')[-1].lower()
        return ""
    
    @property
    def file_icon_class(self):
        """Return a Font Awesome icon class based on file type"""
        extension = self.file_extension
        
        if extension in ['pdf']:
            return 'fa-file-pdf text-danger'
        elif extension in ['doc', 'docx']:
            return 'fa-file-word text-primary'
        elif extension in ['xls', 'xlsx']:
            return 'fa-file-excel text-success'
        elif extension in ['ppt', 'pptx']:
            return 'fa-file-powerpoint text-warning'
        elif extension in ['jpg', 'jpeg', 'png', 'gif', 'bmp']:
            return 'fa-file-image text-info'
        elif extension in ['zip', 'rar', '7z']:
            return 'fa-file-archive text-secondary'
        elif extension in ['txt', 'csv']:
            return 'fa-file-alt text-dark'
        else:
            return 'fa-file text-secondary'

