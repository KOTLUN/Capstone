from django.db import models
from django.utils import timezone

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