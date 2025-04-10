from django.contrib.auth.models import User
from django.utils import timezone
from django.apps import apps
from datetime import date
import traceback

def sync_grades_to_dashboard():
    """
    Synchronize grades from TeacherPortal to Dashboard database.
    This function should be called whenever grades are updated in TeacherPortal.
    """
    # Get models using apps.get_model to avoid circular imports
    TeacherGrade = apps.get_model('TeacherPortal', 'Grade')
    Student = apps.get_model('dashboard', 'Student')
    Subject = apps.get_model('dashboard', 'Subject')
    Teachers = apps.get_model('dashboard', 'Teachers')
    DashboardGrade = apps.get_model('dashboard', 'Grades')
    
    # Get all grades from TeacherPortal
    teacher_grades = TeacherGrade.objects.all()
    print(f"Found {teacher_grades.count()} grades in TeacherPortal")
    
    success_count = 0
    error_count = 0
    
    for teacher_grade in teacher_grades:
        try:
            print(f"\nProcessing grade for student {teacher_grade.student}, course {teacher_grade.course}, quarter {teacher_grade.quarter}")
            
            # Get corresponding student and subject from dashboard
            student = Student.objects.filter(student_id=teacher_grade.student).first()
            if not student:
                print(f"Warning: Student {teacher_grade.student} not found in dashboard")
                error_count += 1
                continue
            else:
                print(f"Found student: {student}")
                
            subject = Subject.objects.filter(subject_id=teacher_grade.course).first()
            if not subject:
                print(f"Warning: Subject {teacher_grade.course} not found in dashboard")
                error_count += 1
                continue
            else:
                print(f"Found subject: {subject}")
            
            # Get or create teacher in dashboard if needed
            teacher = None
            if teacher_grade.teacher:
                try:
                    teacher = Teachers.objects.get(teacher_id=teacher_grade.teacher)
                    print(f"Found existing teacher: {teacher}")
                except Teachers.DoesNotExist:
                    print(f"Creating new teacher record for ID: {teacher_grade.teacher}")
                    # Create user account first
                    username = f"teacher_{teacher_grade.teacher}"
                    user, user_created = User.objects.get_or_create(
                        username=username,
                        defaults={
                            'email': f'{username}@example.com',
                            'first_name': 'Unknown',
                            'last_name': 'Teacher'
                        }
                    )
                    if user_created:
                        # Set a default password
                        user.set_password('changeme123')
                        user.save()
                        print(f"Created user account for teacher: {username}")
                    
                    # Now create the teacher record with required fields
                    teacher = Teachers.objects.create(
                        user=user,
                        teacher_id=teacher_grade.teacher,
                        username=username,
                        password=user.password,
                        first_name=user.first_name,
                        middle_name=None,
                        last_name=user.last_name,
                        gender='Unknown',
                        religion='Not Specified',
                        date_of_birth=date(1990, 1, 1),  # Default date
                        email=user.email,
                        mobile_number='0000000000',
                        address='TBD',
                        class_sched=''  # Empty string as default
                    )
                    print(f"Created teacher record for ID: {teacher_grade.teacher}")
            
            print(f"Creating/updating grade with data:")
            print(f"- Student: {student}")
            print(f"- Subject: {subject}")
            print(f"- Quarter: {teacher_grade.quarter}")
            print(f"- School Year: {teacher_grade.school_year}")
            print(f"- Grade: {teacher_grade.grade}")
            print(f"- Teacher: {teacher}")
            
            # Create or update the grade in dashboard
            dashboard_grade, created = DashboardGrade.objects.update_or_create(
                student=student,
                subject=subject,
                quarter=teacher_grade.quarter,
                school_year=teacher_grade.school_year,
                defaults={
                    'grade': teacher_grade.grade,
                    'teacher': teacher,
                    'status': teacher_grade.status or 'draft',
                    'remarks': teacher_grade.remarks,
                    'date_submitted': teacher_grade.date_submitted,
                    'date_approved': teacher_grade.date_approved
                }
            )
            
            success_count += 1
            if created:
                print(f"Created new grade record in dashboard for {student} - {subject}")
            else:
                print(f"Updated existing grade record in dashboard for {student} - {subject}")
                
        except Exception as e:
            error_count += 1
            print(f"Error syncing grade: {str(e)}")
            print("Traceback:")
            traceback.print_exc()
            continue
    
    print(f"\nSync Summary:")
    print(f"Total grades processed: {teacher_grades.count()}")
    print(f"Successfully synced: {success_count}")
    print(f"Errors: {error_count}")
    
    return f"Sync completed. Success: {success_count}, Errors: {error_count}"

def sync_grades_from_dashboard():
    """
    Synchronize grades from Dashboard to TeacherPortal database.
    This function should be called whenever grades are updated in Dashboard.
    """
    # Get models using apps.get_model to avoid circular imports
    TeacherGrade = apps.get_model('TeacherPortal', 'Grade')
    DashboardGrade = apps.get_model('dashboard', 'Grades')
    
    # Get all grades from Dashboard
    dashboard_grades = DashboardGrade.objects.all()
    
    for dashboard_grade in dashboard_grades:
        try:
            # Create or update the grade in TeacherPortal
            teacher_grade, created = TeacherGrade.objects.update_or_create(
                student=dashboard_grade.student.student_id,
                course=dashboard_grade.subject.subject_id,
                quarter=dashboard_grade.quarter,
                school_year=dashboard_grade.school_year,
                defaults={
                    'grade': dashboard_grade.grade,
                    'teacher': dashboard_grade.teacher.teacher_id,
                    'status': dashboard_grade.status,
                    'remarks': dashboard_grade.remarks,
                    'date_submitted': dashboard_grade.date_submitted,
                    'date_approved': dashboard_grade.date_approved,
                    'uploaded_at': dashboard_grade.uploaded_at,
                }
            )
            
            if created:
                print(f"Created new grade record in TeacherPortal for {dashboard_grade.student} - {dashboard_grade.subject}")
            else:
                print(f"Updated existing grade record in TeacherPortal for {dashboard_grade.student} - {dashboard_grade.subject}")
                
        except Exception as e:
            print(f"Error syncing grade: {e}")
            continue

def convert_grades(apps, schema_editor):
    Grades = apps.get_model('dashboard', 'Grades')
    for grade in Grades.objects.all():
        # Create new grade records for each quarter
        for q in ['1', '2', '3', '4']:
            q_field = f'q{q}_grade'
            if hasattr(grade, q_field) and getattr(grade, q_field):
                Grades.objects.create(
                    student=grade.student,
                    subject=grade.subject,
                    teacher=grade.teacher,
                    grade=getattr(grade, q_field),
                    quarter=q,
                    school_year=grade.school_year,
                    status='approved'
                ) 