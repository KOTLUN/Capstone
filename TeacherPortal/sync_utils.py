from django.utils import timezone
from django.apps import apps

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
    
    for teacher_grade in teacher_grades:
        try:
            # Get corresponding student, subject, and teacher from dashboard
            student = Student.objects.get(student_id=teacher_grade.student)
            subject = Subject.objects.get(subject_id=teacher_grade.course)
            teacher = Teachers.objects.get(teacher_id=teacher_grade.teacher)
            
            # Create or update the grade in dashboard
            dashboard_grade, created = DashboardGrade.objects.update_or_create(
                student=student,
                subject=subject,
                teacher=teacher,
                quarter=teacher_grade.quarter,
                school_year=teacher_grade.school_year,
                defaults={
                    'grade': teacher_grade.grade,
                    'status': teacher_grade.status,
                    'remarks': teacher_grade.remarks,
                    'date_submitted': teacher_grade.date_submitted,
                    'date_approved': teacher_grade.date_approved,
                    'uploaded_at': teacher_grade.uploaded_at,
                }
            )
            
            if created:
                print(f"Created new grade record in dashboard for {student} - {subject}")
            else:
                print(f"Updated existing grade record in dashboard for {student} - {subject}")
                
        except (Student.DoesNotExist, Subject.DoesNotExist, Teachers.DoesNotExist) as e:
            print(f"Error syncing grade: {e}")
            continue

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