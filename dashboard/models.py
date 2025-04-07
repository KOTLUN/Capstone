from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


# Create your models here.
class Student(models.Model):
    student_id = models.CharField(max_length=50, unique=True)
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True, null=True)
    last_name = models.CharField(max_length=100)
    gender = models.CharField(max_length=10)
    religion = models.CharField(max_length=50)
    date_of_birth = models.DateField()
    email = models.EmailField(unique=True)
    mobile_number = models.CharField(max_length=15)
    address = models.TextField()
    school_year = models.CharField(max_length=20, blank=True, null=True)  # e.g., "2023-2024"
    status = models.CharField(max_length=20, default='Not Enrolled', 
                             choices=[('Not Enrolled', 'Not Enrolled'),
                                     ('Enrolled', 'Enrolled'), 
                                     ('Transferred', 'Transferred'),
                                     ('Dropped', 'Dropped'),
                                     ('Completed', 'Completed')])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    has_account = models.BooleanField(default=False)
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='student_profile')
    student_photo = models.ImageField(upload_to='student_photos/', null=True, blank=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.student_id})"

    class Meta:
        ordering = ['-created_at']

    def get_grade_for_subject(self, subject):
        """Get the latest grade for this student in the given subject"""
        from TeacherPortal.models import Grade
        try:
            # Try to get the latest grade for this student in this subject
            grade = Grade.objects.filter(
                student=self.student_id,
                course=subject.subject_id
            ).order_by('-uploaded_at').first()
            
            return grade.grade if grade else None
        except Exception:
            return None


class Teachers(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    teacher_id = models.CharField(max_length=50, unique=True)
    username = models.CharField(max_length=150, unique=True)
    password = models.CharField(max_length=128)
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True, null=True)
    last_name = models.CharField(max_length=100)
    gender = models.CharField(max_length=10)
    religion = models.CharField(max_length=50)
    date_of_birth = models.DateField()
    email = models.EmailField()
    mobile_number = models.CharField(max_length=15)
    address = models.TextField()
    class_sched = models.CharField(max_length=50)
    teacher_photo = models.ImageField(upload_to='teacher_photos/', null=True, blank=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def photo_url(self):
        if self.teacher_photo and hasattr(self.teacher_photo, 'url'):
            return self.teacher_photo.url
        return None

    def sync_password_from_user(self):
        """Sync the password from the associated User model"""
        if self.user:
            self.password = self.user.password
            self.save(update_fields=['password'])
            return True
        return False




class Subject(models.Model):
    subject_id = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Schedules(models.Model):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    teacher_id = models.ForeignKey(Teachers, on_delete=models.CASCADE)
    grade_level = models.IntegerField()
    section = models.ForeignKey('Sections', on_delete=models.CASCADE)
    day = models.CharField(max_length=10)
    start_time = models.TimeField()
    end_time = models.TimeField()
    room = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Schedule'
        verbose_name_plural = 'Schedules'
        # Add unique constraint to prevent conflicts
        unique_together = ['teacher_id', 'section', 'day', 'start_time']
        db_table = 'schedules'

    def __str__(self):
        return f"{self.subject.name} - {self.section.section_id} ({self.day})"

    class Meta:
        ordering = ['-created_at']

    @classmethod
    def exists_time_conflict(cls, queryset, start_time, end_time):
        """Check if there's a time conflict in the queryset."""
        return queryset.filter(
            models.Q(start_time__lt=end_time) & 
            models.Q(end_time__gt=start_time)
        ).exists()

    def get_schedule_info(self):
        """Get formatted schedule information"""
        return {
            'subject_name': self.subject.name,
            'subject_id': self.subject.subject_id,
            'section': self.section.section_id,
            'day': self.day,
            'time': f"{self.start_time.strftime('%I:%M %p')} - {self.end_time.strftime('%I:%M %p')}",
            'room': self.room,
            'teacher': f"{self.teacher_id.first_name} {self.teacher_id.last_name}"
        }

    def get_enrolled_students(self):
        """Get enrolled students based on grade level"""
        enrollment_model = {
            7: 'enrollments',
            8: 'grade8_enrollments',
            9: 'grade9_enrollments',
            10: 'grade10_enrollments',
            11: 'grade11_enrollments',
            12: 'grade12_enrollments'
        }.get(self.section.grade_level, 'enrollments')

        return Student.objects.filter(
            **{f"{enrollment_model}__section": self.section,
               f"{enrollment_model}__status": 'Active'}
        ).distinct()


class Sections(models.Model):
    section_id = models.CharField(max_length=50, unique=True)
    grade_level = models.IntegerField()  # Store as number (7-12)
    adviser = models.ForeignKey(Teachers, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.section_id} - Grade {self.grade_level}"

    def get_grade_level_display(self):
        return f"Grade {self.grade_level}"

    def get_section_info(self):
        """Get section information"""
        return {
            'section_id': self.section_id,
            'grade_level': self.grade_level,
            'adviser': f"{self.adviser.first_name} {self.adviser.last_name}",
            'student_count': self.get_student_count(),
            'schedules': list(self.schedules_set.values('day', 'start_time', 'end_time', 'subject__name'))
        }

    def get_student_count(self):
        """Get count of enrolled students"""
        enrollment_model = {
            7: 'enrollments',
            8: 'grade8_enrollments',
            9: 'grade9_enrollments',
            10: 'grade10_enrollments',
            11: 'grade11_enrollments',
            12: 'grade12_enrollments'
        }.get(self.grade_level, 'enrollments')

        return Student.objects.filter(
            **{f"{enrollment_model}__section": self,
               f"{enrollment_model}__status": 'Active'}
        ).count()

    class Meta:
        ordering = ['grade_level', 'section_id']
        verbose_name_plural = "Sections"


class Enrollment(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='enrollments')
    section = models.ForeignKey(Sections, on_delete=models.CASCADE, related_name='enrollments')
    school_year = models.CharField(max_length=20)  # e.g., "2023-2024"
    enrollment_date = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=20, default='Active', 
                             choices=[('Active', 'Active'), 
                                     ('Withdrawn', 'Withdrawn'),
                                     ('Completed', 'Completed'),
                                     ('Dropped', 'Dropped'),
                                     ('Transferred', 'Transferred')])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.student} - {self.section} ({self.school_year})"

    class Meta:
        ordering = ['-created_at']
        unique_together = ['student', 'section', 'school_year']

# New models for different statuses
class DroppedStudent(models.Model):
    enrollment = models.OneToOneField(Enrollment, on_delete=models.CASCADE, related_name='dropped_details')
    drop_date = models.DateField(auto_now_add=True)
    reason = models.TextField()
    remarks = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.enrollment.student} - Dropped on {self.drop_date}"

class TransferredStudent(models.Model):
    enrollment = models.OneToOneField(Enrollment, on_delete=models.CASCADE, related_name='transfer_details')
    transfer_date = models.DateField(auto_now_add=True)
    transfer_school = models.CharField(max_length=255)
    reason = models.TextField()
    remarks = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.enrollment.student} - Transferred to {self.transfer_school}"

class CompletedStudent(models.Model):
    enrollment = models.OneToOneField(Enrollment, on_delete=models.CASCADE, related_name='completion_details')
    completion_date = models.DateField(auto_now_add=True)
    final_grade = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    remarks = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.enrollment.student} - Completed on {self.completion_date}"


class StudentAccount(models.Model):
    student = models.OneToOneField(Student, on_delete=models.CASCADE, related_name='account')
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_account')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Student Account"
        verbose_name_plural = "Student Accounts"
    
    def __str__(self):
        return f"Account for {self.student.first_name} {self.student.last_name}"
    
    @classmethod
    def create_account(cls, student, username, email, password, guardian_data=None, student_photo=None):
        """
        Create a new student account only if the student is registered and enrolled
        
        Parameters:
        - student: Student object
        - username: string
        - email: string
        - password: string
        - guardian_data: dict containing guardian information (optional)
        - student_photo: uploaded file (optional)
        """
        # Check if student is enrolled
        is_enrolled = Enrollment.objects.filter(
            student=student,
            status='Active'
        ).exists()
        
        if not is_enrolled:
            raise ValueError("Student must be enrolled to create an account")
        
        # Create user
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=student.first_name,
            last_name=student.last_name
        )
        
        # Create account
        account = cls.objects.create(
            student=student,
            user=user
        )
        
        # Update student model
        student.has_account = True
        student.user = user
        
        # Handle student photo if provided
        if student_photo:
            student.student_photo = student_photo
        
        student.save(update_fields=['has_account', 'user', 'student_photo'])
        
        # Create guardian record if data provided
        if guardian_data:
            Guardian.objects.create(
                student=student,
                first_name=guardian_data.get('first_name', ''),
                middle_name=guardian_data.get('middle_name', ''),
                last_name=guardian_data.get('last_name', ''),
                contact_number=guardian_data.get('contact_number', ''),
                relationship=guardian_data.get('relationship', 'Guardian')
            )
        
        return account
    
    
    

class Guardian(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='guardians')
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True, null=True)
    last_name = models.CharField(max_length=100)
    contact_number = models.CharField(max_length=15)
    relationship = models.CharField(max_length=20, choices=[
        ('Parent', 'Parent'),
        ('Guardian', 'Guardian'),
        ('Sibling', 'Sibling'),
        ('Relative', 'Other Relative')
    ])
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} - Guardian of {self.student.first_name}"
    
    def full_name(self):
        if self.middle_name:
            return f"{self.first_name} {self.middle_name} {self.last_name}"
        return f"{self.first_name} {self.last_name}"
    
    
    

class Grades(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='grades')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    teacher = models.ForeignKey(Teachers, on_delete=models.CASCADE)
    school_year = models.CharField(max_length=9)  # e.g., "2023-2024"
    q1_grade = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    q2_grade = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    q3_grade = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    q4_grade = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    final_grade = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Grade'
        verbose_name_plural = 'Grades'
        unique_together = ['student', 'subject', 'teacher', 'school_year']

    def __str__(self):
        return f"{self.student.first_name} {self.student.last_name} - {self.subject.name} ({self.school_year})"

    def calculate_final_grade(self):
        grades = [self.q1_grade, self.q2_grade, self.q3_grade, self.q4_grade]
        valid_grades = [grade for grade in grades if grade is not None]
        if valid_grades:
            self.final_grade = sum(valid_grades) / len(valid_grades)
        return self.final_grade
    
    
    

class AdminProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    profile_photo = models.ImageField(upload_to='admin_photos/', null=True, blank=True)
    
    def __str__(self):
        return f"Profile of {self.user.username}"
    
    
    

class AdminActivity(models.Model):
    admin = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=255)
    action_type = models.CharField(max_length=50)  # For icon selection
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.admin.username} - {self.action}"

    def get_time_ago(self):
        from django.utils import timezone
        from datetime import timedelta
        
        now = timezone.now()
        diff = now - self.timestamp

        if diff < timedelta(minutes=1):
            return 'just now'
        elif diff < timedelta(hours=1):
            minutes = int(diff.total_seconds() / 60)
            return f'{minutes} minute{"s" if minutes != 1 else ""} ago'
        elif diff < timedelta(days=1):
            hours = int(diff.total_seconds() / 3600)
            return f'{hours} hour{"s" if hours != 1 else ""} ago'
        elif diff < timedelta(days=30):
            days = diff.days
            return f'{days} day{"s" if days != 1 else ""} ago'
        else:
            return self.timestamp.strftime('%B %d, %Y')
    
    
    

class Grade8Enrollment(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='grade8_enrollments')
    section = models.ForeignKey(Sections, on_delete=models.CASCADE, related_name='grade8_enrollments')
    school_year = models.CharField(max_length=20)  # e.g., "2023-2024"
    enrollment_date = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=20, default='Active', 
                             choices=[('Active', 'Active'), 
                                     ('Withdrawn', 'Withdrawn'),
                                     ('Completed', 'Completed'),
                                     ('Dropped', 'Dropped'),
                                     ('Transferred', 'Transferred')])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.student} - {self.section} ({self.school_year})"

    class Meta:
        ordering = ['-created_at']
        unique_together = ['student', 'section', 'school_year']

class Grade9Enrollment(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='grade9_enrollments')
    section = models.ForeignKey(Sections, on_delete=models.CASCADE, related_name='grade9_enrollments')
    school_year = models.CharField(max_length=20)  # e.g., "2023-2024"
    enrollment_date = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=20, default='Active', 
                             choices=[('Active', 'Active'), 
                                     ('Withdrawn', 'Withdrawn'),
                                     ('Completed', 'Completed'),
                                     ('Dropped', 'Dropped'),
                                     ('Transferred', 'Transferred')])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.student} - {self.section} ({self.school_year})"

    class Meta:
        ordering = ['-created_at']
        unique_together = ['student', 'section', 'school_year']

class Grade10Enrollment(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='grade10_enrollments')
    section = models.ForeignKey(Sections, on_delete=models.CASCADE, related_name='grade10_enrollments')
    school_year = models.CharField(max_length=20)  # e.g., "2023-2024"
    enrollment_date = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=20, default='Active', 
                            choices=[('Active', 'Active'), 
                                    ('Withdrawn', 'Withdrawn'),
                                    ('Completed', 'Completed'),
                                    ('Dropped', 'Dropped'),
                                    ('Transferred', 'Transferred')])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.student} - {self.section} ({self.school_year})"

    class Meta:
        ordering = ['-created_at']
        unique_together = ['student', 'section', 'school_year']

class Grade11Enrollment(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='grade11_enrollments')
    section = models.ForeignKey(Sections, on_delete=models.CASCADE, related_name='grade11_enrollments')
    track = models.CharField(max_length=20)
    school_year = models.CharField(max_length=20)  # e.g., "2023-2024"
    enrollment_date = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=20, default='Active', 
                             choices=[('Active', 'Active'), 
                                     ('Withdrawn', 'Withdrawn'),
                                     ('Completed', 'Completed'),
                                     ('Dropped', 'Dropped'),
                                     ('Transferred', 'Transferred')])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.student} - {self.section} ({self.school_year})"

    class Meta:
        ordering = ['-created_at']
        unique_together = ['student', 'section', 'school_year']

class Grade12Enrollment(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='grade12_enrollments')
    section = models.ForeignKey(Sections, on_delete=models.CASCADE, related_name='grade12_enrollments')
    track = models.CharField(max_length=20)
    school_year = models.CharField(max_length=20)  # e.g., "2023-2024"
    enrollment_date = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=20, default='Active', 
                             choices=[('Active', 'Active'), 
                                     ('Withdrawn', 'Withdrawn'),
                                     ('Completed', 'Completed'),
                                     ('Dropped', 'Dropped'),
                                     ('Transferred', 'Transferred')])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.student} - {self.section} ({self.school_year})"

    class Meta:
        ordering = ['-created_at']
        unique_together = ['student', 'section', 'school_year']

class SchoolYear(models.Model):
    year_start = models.IntegerField()
    year_end = models.IntegerField()
    is_active = models.BooleanField(default=False)
    is_previous = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def display_name(self):
        return f"{self.year_start}-{self.year_end}"

    def save(self, *args, **kwargs):
        if self.is_active:
            # Set all other years as inactive and update previous year
            try:
                current_active = SchoolYear.objects.get(is_active=True)
                if current_active and current_active.id != self.id:
                    current_active.is_active = False
                    current_active.is_previous = True
                    current_active.save()
            except SchoolYear.DoesNotExist:
                pass

            # Set all other years as inactive
            SchoolYear.objects.exclude(id=self.id).update(is_active=False)

        super().save(*args, **kwargs)

    @classmethod
    def get_active(cls):
        try:
            return cls.objects.get(is_active=True)
        except cls.DoesNotExist:
            return None

    @classmethod
    def get_all_years(cls):
        return cls.objects.all().order_by('-year_start')

    def __str__(self):
        status = " (Active)" if self.is_active else " (Previous)" if self.is_previous else ""
        return f"{self.display_name}{status}"
    
    
    
