from django.core.management.base import BaseCommand
from dashboard.models import Grades, Student, Subject, Teacher, SchoolYear, Sections
from django.db import transaction

class Command(BaseCommand):
    help = 'Migrate grades from old format to new format'

    def handle(self, *args, **options):
        try:
            with transaction.atomic():
                # Get active school year
                active_school_year = SchoolYear.objects.get(is_active=True)
                current_school_year = f"{active_school_year.year_start}-{active_school_year.year_end}"
                
                # Get all existing grades for the current school year
                old_grades = Grades.objects.filter(school_year=current_school_year)
                
                migrated_count = 0
                error_count = 0
                
                for old_grade in old_grades:
                    try:
                        # Create new grade record with proper associations
                        new_grade = Grades.objects.create(
                            student=old_grade.student,
                            subject=old_grade.subject,
                            teacher=old_grade.teacher,
                            school_year=current_school_year,
                            section=old_grade.section,
                            grade=old_grade.grade,
                            quarter=old_grade.quarter,
                            status='approved'
                        )
                        
                        migrated_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'Successfully migrated grade for student {old_grade.student.student_id} '
                                f'in subject {old_grade.subject.name}'
                            )
                        )
                    except Exception as e:
                        error_count += 1
                        self.stdout.write(
                            self.style.ERROR(
                                f'Failed to migrate grade: {str(e)}'
                            )
                        )
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Migration completed: {migrated_count} grades migrated successfully, '
                        f'{error_count} errors encountered.'
                    )
                )
                
        except SchoolYear.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(
                    'No active school year found. Please set an active school year first.'
                )
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(
                    f'Migration failed: {str(e)}'
                )
            ) 