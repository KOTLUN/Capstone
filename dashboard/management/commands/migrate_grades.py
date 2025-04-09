from django.core.management.base import BaseCommand
from TeacherPortal.models import Grade as TeacherGrade
from dashboard.models import Grades as DashboardGrade, Student, Subject, Teachers
from django.db import transaction

class Command(BaseCommand):
    help = 'Migrate grades from TeacherPortal to Dashboard'

    def handle(self, *args, **kwargs):
        self.stdout.write('Starting grade migration...')
        
        try:
            with transaction.atomic():
                # Get all grades from TeacherPortal
                teacher_grades = TeacherGrade.objects.all()
                
                migrated_count = 0
                skipped_count = 0
                
                for old_grade in teacher_grades:
                    try:
                        # Get related objects from dashboard
                        student = Student.objects.get(student_id=old_grade.student)
                        subject = Subject.objects.get(subject_id=old_grade.course)
                        teacher = Teachers.objects.get(username=old_grade.teacher)
                        
                        # Create new grade in dashboard
                        new_grade, created = DashboardGrade.objects.get_or_create(
                            student=student,
                            subject=subject,
                            teacher=teacher,
                            quarter=old_grade.quarter,
                            school_year=old_grade.school_year,
                            defaults={
                                'grade': old_grade.grade,
                                'status': old_grade.status,
                                'remarks': old_grade.remarks,
                                'date_created': old_grade.date_created,
                                'date_modified': old_grade.date_modified,
                                'date_submitted': old_grade.date_submitted,
                                'date_approved': old_grade.date_approved,
                                'uploaded_at': old_grade.uploaded_at
                            }
                        )
                        
                        if not created:
                            # Update existing grade
                            new_grade.grade = old_grade.grade
                            new_grade.status = old_grade.status
                            new_grade.remarks = old_grade.remarks
                            new_grade.date_submitted = old_grade.date_submitted
                            new_grade.date_approved = old_grade.date_approved
                            new_grade.uploaded_at = old_grade.uploaded_at
                            new_grade.save()
                        
                        migrated_count += 1
                        self.stdout.write(f'Migrated grade for student {student.student_id} in {subject.name}')
                        
                    except (Student.DoesNotExist, Subject.DoesNotExist, Teachers.DoesNotExist) as e:
                        self.stdout.write(
                            self.style.WARNING(
                                f'Skipped grade ID {old_grade.id}: {str(e)}'
                            )
                        )
                        skipped_count += 1
                        continue
                    
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Successfully migrated {migrated_count} grades. Skipped {skipped_count} grades.'
                    )
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(
                    f'Error during migration: {str(e)}'
                )
            ) 