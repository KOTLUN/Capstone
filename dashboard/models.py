from django.db import models
from django.contrib.auth.models import User


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
                                     ('Dropped', 'Dropped')])
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
    grade_level = models.CharField(max_length=50)
    section = models.ForeignKey('Sections', on_delete=models.CASCADE)
    day = models.CharField(max_length=20)
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

    def __str__(self):
        return f"{self.subject.name} - {self.section.section_id} ({self.day})"

    class Meta:
        ordering = ['-created_at']


class Sections(models.Model):
    section_id = models.CharField(max_length=50, unique=True)
    grade_level = models.CharField(max_length=50)
    adviser = models.ForeignKey(Teachers, on_delete=models.CASCADE, related_name='sections')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.section_id} - Grade {self.grade_level}"
    
    class Meta:
        ordering = ['-created_at']
    
    
    

class Enrollment(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='enrollments')
    section = models.ForeignKey(Sections, on_delete=models.CASCADE, related_name='enrollments')
    school_year = models.CharField(max_length=20)  # e.g., "2023-2024"
    enrollment_date = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=20, default='Active', 
                             choices=[('Active', 'Active'), 
                                     ('Withdrawn', 'Withdrawn'),
                                     ('Completed', 'Completed')])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.student} - {self.section} ({self.school_year})"

    class Meta:
        ordering = ['-created_at']
        # Ensure a student can only be enrolled once in a section for a given school year
        unique_together = ['student', 'section', 'school_year']
    
    
    

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
    
    
    
