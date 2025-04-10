from django.core.management.base import BaseCommand
from TeacherPortal.sync_utils import sync_grades_to_dashboard
from django.apps import apps

class Command(BaseCommand):
    help = 'Synchronize grades from TeacherPortal to Dashboard'

    def handle(self, *args, **options):
        self.stdout.write('Starting grade synchronization...')
        try:
            # Get models
            TeacherGrade = apps.get_model('TeacherPortal', 'Grade')
            DashboardGrade = apps.get_model('dashboard', 'Grades')
            
            # Get all grades from TeacherPortal
            teacher_grades = TeacherGrade.objects.all()
            self.stdout.write(f'Found {teacher_grades.count()} grades in TeacherPortal')
            
            # Sync grades
            sync_grades_to_dashboard()
            
            self.stdout.write(self.style.SUCCESS('Successfully synchronized grades'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error synchronizing grades: {str(e)}')) 