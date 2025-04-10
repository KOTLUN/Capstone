from django.db import migrations, transaction
from django.utils import timezone

def sync_teacher_portal_grades(apps, schema_editor):
    Grade = apps.get_model('TeacherPortal', 'Grade')
    Grades = apps.get_model('dashboard', 'Grades')
    Student = apps.get_model('dashboard', 'Student')
    Subject = apps.get_model('dashboard', 'Subject')
    Teachers = apps.get_model('dashboard', 'Teachers')
    
    # Get the database connection
    connection = schema_editor.connection
    
    print("Starting grade synchronization...")
    success_count = 0
    error_count = 0
    
    with transaction.atomic():
        # Clear existing grades using raw SQL
        with connection.cursor() as cursor:
            cursor.execute("TRUNCATE TABLE dashboard_grades")
        
        # Sync grades from TeacherPortal
        for grade in Grade.objects.all():
            try:
                # Get corresponding student, subject, and teacher from dashboard
                student = Student.objects.filter(student_id=grade.student).first()
                subject = Subject.objects.filter(subject_id=grade.course).first()
                teacher = Teachers.objects.filter(teacher_id=grade.teacher).first()
                
                if not all([student, subject, teacher]):
                    print(f"Missing reference for grade {grade.id}:")
                    if not student:
                        print(f"- Student {grade.student} not found")
                    if not subject:
                        print(f"- Subject {grade.course} not found")
                    if not teacher:
                        print(f"- Teacher {grade.teacher} not found")
                    error_count += 1
                    continue
                
                # Insert grade using raw SQL
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO dashboard_grades 
                        (student_id, subject_id, teacher_id, grade, quarter, school_year, 
                        status, remarks, date_created, date_submitted, date_approved, uploaded_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        [
                            student.id, subject.id, teacher.id, grade.grade, grade.quarter,
                            grade.school_year, grade.status or 'draft', grade.remarks,
                            grade.date_created or timezone.now(),
                            grade.date_submitted, grade.date_approved,
                            grade.uploaded_at or timezone.now()
                        ]
                    )
                success_count += 1
                print(f"Synced grade {grade.id} for student {student.student_id} in {subject.name}")
                
            except Exception as e:
                print(f"Error syncing grade {grade.id}: {str(e)}")
                error_count += 1
    
    print(f"\nSync complete:")
    print(f"- Successfully synced: {success_count} grades")
    print(f"- Errors: {error_count} grades")

def reverse_sync(apps, schema_editor):
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        cursor.execute("TRUNCATE TABLE dashboard_grades")

class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('TeacherPortal', '0001_initial'),
        ('dashboard', '0003_remove_old_grade_fields'),
    ]

    operations = [
        migrations.RunPython(sync_teacher_portal_grades, reverse_sync),
    ] 