from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import (
    Student, Teachers, Subject, Schedules, Sections, 
    Enrollment, Grade8Enrollment, Grade9Enrollment, 
    Grade10Enrollment, Grade11Enrollment, Grade12Enrollment,
    StudentAccount, Guardian, Grades, DroppedStudent, 
    TransferredStudent, CompletedStudent, AdminProfile, 
    AdminActivity, SchoolYear
)
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Avg
from django.conf import settings
from django.http import JsonResponse
from datetime import datetime, timedelta
from django.db import transaction
from django.db import models
from django.views.decorators.http import require_POST
import json
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models.functions import ExtractMonth
from django.db.models import Q
from collections import defaultdict
from django.urls import reverse


# Create your views here.
def dashboard_view(request):
    # Get active school year
    active_school_year = SchoolYear.get_active()
    
    # Get total number of enrolled students for active school year
    total_students = Enrollment.objects.filter(
        school_year=active_school_year.display_name if active_school_year else None,
        status='Active'
    ).count()
    
    # Calculate student growth (comparing to last month for the selected school year)
    last_month = datetime.now() - timedelta(days=30)
    students_last_month = Enrollment.objects.filter(
        school_year=active_school_year.display_name if active_school_year else None,
        status='Active',
        enrollment_date__lt=last_month
    ).count()
    
    if students_last_month > 0:
        student_growth = ((total_students - students_last_month) / students_last_month) * 100
    else:
        student_growth = 0

    # Initialize school years data structure
    school_years_data = {}
    
    if active_school_year:
        year_data = {
            'monthly': {
                'labels': ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
                'data': [0] * 12  # Initialize with zeros
            }
        }

        # Get monthly enrollment data
        monthly_data = (
            Enrollment.objects
            .filter(
                school_year=active_school_year.display_name,
                status='Active'
            )
            .annotate(month=ExtractMonth('enrollment_date'))
            .values('month')
            .annotate(count=Count('id'))
        )

        # Fill in the actual monthly counts
        for item in monthly_data:
            month_index = item['month'] - 1
            year_data['monthly']['data'][month_index] = item['count']

        school_years_data[active_school_year.display_name] = year_data

    context = {
        'total_students': total_students,
        'student_growth': round(student_growth, 1),
        'active_school_year': active_school_year,
        'school_years_data': json.dumps(school_years_data, cls=DjangoJSONEncoder),
    }
    
    return render(request, 'main.html', context)

def students_view(request):
    # Get school years from SchoolYear model
    school_years = SchoolYear.objects.all().order_by('-year_start')
    active_school_year = SchoolYear.get_active()
    previous_school_year = SchoolYear.objects.filter(is_previous=True).first()
    
    # Filter by school year if provided
    selected_year = request.GET.get('school_year')
    
    if selected_year:
        # Get only students who were enrolled in the selected school year
        students = Student.objects.filter(
            enrollments__school_year=selected_year
        ).distinct()
        
        # Set display status based on the selected year
        if previous_school_year and selected_year == previous_school_year.display_name:
            # If viewing previous year, show all filtered students as completed
            for student in students:
                student.display_status = 'Completed'
        elif active_school_year and selected_year == active_school_year.display_name:
            # If viewing active year, show actual enrollment status
            for student in students:
                enrollment = student.enrollments.filter(
                    school_year=active_school_year.display_name
                ).first()
                student.display_status = enrollment.status if enrollment else student.status
    else:
        # If no year selected, show all students with current status
        students = Student.objects.all()
        for student in students:
            if active_school_year:
                enrollment = student.enrollments.filter(
                    school_year=active_school_year.display_name
                ).first()
                student.display_status = enrollment.status if enrollment else student.status
            else:
                student.display_status = student.status

    context = {
        'students': students,
        'school_years': school_years,
        'active_school_year': active_school_year,
        'previous_school_year': previous_school_year,
        'selected_year': selected_year
    }
    return render(request, 'students.html', context)

def teachers_view(request):
    teachers = Teachers.objects.all()
    context = {
        'teachers': teachers,
        'media_url': settings.MEDIA_URL,  # Add media URL to context
    }
    return render(request, 'teachers.html', context)

def add_teacher(request):
    if request.method == 'POST':
        try:
            # Create User instance first
            user = User.objects.create_user(
                username=request.POST['username'],
                password=request.POST['password'],
                email=request.POST['email'],
                first_name=request.POST['first_name'],
                last_name=request.POST['last_name']
            )
            
            # Handle photo upload
            teacher_photo = request.FILES.get('teacher_photo')
            
            # Create Teachers instance
            teacher = Teachers.objects.create(
                user=user,
                teacher_id=request.POST['teacher_id'],
                username=request.POST['username'],
                password=request.POST['password'],
                first_name=request.POST['first_name'],
                middle_name=request.POST.get('middle_name'),
                last_name=request.POST['last_name'],
                gender=request.POST['gender'],
                religion=request.POST['religion'],
                date_of_birth=request.POST['date_of_birth'],
                email=request.POST['email'],
                mobile_number=request.POST['mobile_number'],
                address=request.POST['address'],
                class_sched="",  # Set a default empty value
                teacher_photo=teacher_photo
            )
            messages.success(request, 'Teacher added successfully!')
            log_admin_activity(
                request.user,
                f"Added new teacher: {teacher.first_name} {teacher.last_name}",
                "teacher"
            )
            return redirect('teachers')
        except Exception as e:
            if 'user' in locals():
                user.delete()
            messages.error(request, f'Error adding teacher: {str(e)}')
            return redirect('teachers')
    
    return redirect('teachers')



def add_student(request):
    if request.method == 'POST':
        try:
            student_id = request.POST.get('student_id')
            first_name = request.POST.get('first_name')
            middle_name = request.POST.get('middle_name', '')
            last_name = request.POST.get('last_name')
            gender = request.POST.get('gender')
            religion = request.POST.get('religion')
            date_of_birth = request.POST.get('date_of_birth')
            email = request.POST.get('email')
            mobile_number = request.POST.get('mobile_number')
            address = request.POST.get('address')

            # Validate that the date of birth is provided
            if not date_of_birth:
                messages.error(request, "Date of Birth is required.")
                return redirect('students')

            # Create the student record
            student = Student.objects.create(
                student_id=student_id,
                first_name=first_name,
                middle_name=middle_name,
                last_name=last_name,
                gender=gender,
                religion=religion,
                date_of_birth=date_of_birth,
                email=email,
                mobile_number=mobile_number,
                address=address
            )

            # Log the activity after successful creation
            log_admin_activity(
                request.user,
                f"Added new student: {student.first_name} {student.last_name} ({student.student_id})",
                "student"
            )
            
            messages.success(request, "Student added successfully!")
            return redirect('students')

        except Exception as e:
            messages.error(request, f"Error adding student: {str(e)}")
            return redirect('students')

    return render(request, 'students.html')


def teacher_portal_view(request):
    # Fetch teacher data from the database as needed.
    # For example, if Teachers is your model:
    from dashboard.models import Teachers
    teacher_data = Teachers.objects.all()  # or filter as necessary
    return render(request, 'grades.html', {'teacher_data': teacher_data})

def edit_teacher(request):
    if request.method == 'POST':
        try:
            teacher = Teachers.objects.get(teacher_id=request.POST['teacher_id'])
            
            # Update teacher information
            teacher.first_name = request.POST['first_name']
            teacher.middle_name = request.POST.get('middle_name')
            teacher.last_name = request.POST['last_name']
            teacher.gender = request.POST['gender']
            teacher.religion = request.POST['religion']
            teacher.date_of_birth = request.POST['date_of_birth']
            teacher.email = request.POST['email']
            teacher.mobile_number = request.POST['mobile_number']
            teacher.address = request.POST['address']

            # Handle photo upload if provided
            if 'teacher_photo' in request.FILES:
                teacher.teacher_photo = request.FILES['teacher_photo']
            
            # Update associated user
            teacher.user.first_name = request.POST['first_name']
            teacher.user.last_name = request.POST['last_name']
            teacher.user.email = request.POST['email']
            teacher.user.save()
            
            teacher.save()
            messages.success(request, 'Teacher updated successfully!')
            
            log_admin_activity(
                request.user,
                f"Updated teacher information: {teacher.first_name} {teacher.last_name}",
                "teacher"
            )
            
        except Teachers.DoesNotExist:
            messages.error(request, 'Teacher not found!')
        except Exception as e:
            messages.error(request, f'Error updating teacher: {str(e)}')
    
    return redirect('teachers')




def add_subject(request):
    if request.method == 'POST':
        subject_id = request.POST.get('subject_id')
        subject_name = request.POST.get('subject_name')
        
        if subject_id and subject_name:
            # Check if subject with this ID already exists
            if Subject.objects.filter(subject_id=subject_id).exists():
                messages.error(request, f"Subject with ID {subject_id} already exists.")
                return redirect('add_subject')
            
            # Create the new subject
            Subject.objects.create(
                subject_id=subject_id,
                name=subject_name
            )
            messages.success(request, f"Subject '{subject_name}' added successfully!")
            log_admin_activity(
                request.user,
                f"Added new subject: {subject_name}",
                "subject"
            )
            return redirect('add_subject')
        else:
            messages.error(request, "Both Subject ID and Subject Name are required.")
    
    # Get all subjects for display
    subjects = Subject.objects.all().order_by('name')
    return render(request, 'subject.html', {'subjects': subjects})





def generate_time_slots():
    """Generate available time slots from 7 AM to 5 PM in 30-minute intervals"""
    time_slots = []
    for hour in range(7, 17):  # 7 AM to 5 PM
        for minute in [0, 30]:
            time = f"{hour:02d}:{minute:02d}"
            # Convert to 12-hour format for display
            display_hour = hour if hour <= 12 else hour - 12
            ampm = 'AM' if hour < 12 else 'PM'
            display_time = f"{display_hour}:{minute:02d} {ampm}"
            time_slots.append({
                'value': time,
                'label': display_time
            })
    return time_slots

def sections_view(request):
    try:
        sections = Sections.objects.all()
        
        # Get all teachers
        all_teachers = Teachers.objects.all()
        
        # Get teachers who are already advisers and their grade levels
        existing_advisers = Sections.objects.values_list('adviser_id', 'grade_level')
        
        # Create a dictionary to track which teachers are advising which grade levels
        adviser_grade_levels = {}
        for adviser_id, grade_level in existing_advisers:
            if adviser_id not in adviser_grade_levels:
                adviser_grade_levels[adviser_id] = []
            adviser_grade_levels[adviser_id].append(grade_level)
        
        # Filter out teachers who are already advisers for any section
        available_teachers = []
        for teacher in all_teachers:
            # Include teachers who aren't advising any section yet
            if teacher.id not in adviser_grade_levels:
                available_teachers.append(teacher)
        
        subjects = Subject.objects.all()
        
        # Get unique school years from enrollments
        enrollment_years = (Enrollment.objects
                          .values_list('school_year', flat=True)
                          .distinct()
                          .order_by('-school_year'))

        # Get enrollment counts for each section
        section_counts = {}
        for section in sections:
            grade_number = section.grade_level
            
            # Get enrollments based on grade level
            if grade_number == 7:
                count = Enrollment.objects.filter(
                    section=section,
                    status='Active'
                ).count()
            elif grade_number == 8:
                count = Grade8Enrollment.objects.filter(
                    section=section,
                    status='Active'
                ).count()
            elif grade_number == 9:
                count = Grade9Enrollment.objects.filter(
                    section=section,
                    status='Active'
                ).count()
            elif grade_number == 10:
                count = Grade10Enrollment.objects.filter(
                    section=section,
                    status='Active'
                ).count()
            elif grade_number == 11:
                count = Grade11Enrollment.objects.filter(
                    section=section,
                    status='Active'
                ).count()
            elif grade_number == 12:
                count = Grade12Enrollment.objects.filter(
                    section=section,
                    status='Active'
                ).count()
            else:
                count = 0
                
            section_counts[section.id] = count

        context = {
            'sections': sections,
            'teachers': all_teachers,
            'available_teachers': available_teachers,
            'subjects': subjects,
            'adviser_grade_levels': adviser_grade_levels,
            'enrollment_years': enrollment_years,
            'section_counts': section_counts
        }
        return render(request, 'Sections.html', context)
    except Exception as e:
        messages.error(request, f"Error loading sections: {str(e)}")
        return render(request, 'Sections.html', {})

def add_section(request):
    if request.method == 'POST':
        section_id = request.POST.get('section_id')
        grade_level = request.POST.get('grade_level')
        adviser_id = request.POST.get('adviser')
        
        # Check if section with this ID already exists
        if Sections.objects.filter(section_id=section_id).exists():
            messages.error(request, f"Section with ID {section_id} already exists.")
            return redirect('sections')
        
        # Check if a section with this grade level and section ID combination already exists
        if Sections.objects.filter(grade_level=grade_level, section_id=section_id).exists():
            messages.error(request, f"A section with ID {section_id} in {grade_level} already exists.")
            return redirect('sections')
        
        try:
            # Get the teacher object by ID
            adviser = Teachers.objects.get(id=adviser_id)
            
            # Check if the adviser is already assigned to a section in this grade level
            if Sections.objects.filter(adviser=adviser, grade_level=grade_level).exists():
                messages.error(request, f"Teacher {adviser.first_name} {adviser.last_name} is already an adviser for a section in {grade_level}.")
                return redirect('sections')
            
            # Create the new section with the adviser from Teachers model
            Sections.objects.create(
                section_id=section_id,
                grade_level=grade_level,
                adviser=adviser
            )  
            messages.success(request, f"Section '{section_id} - {grade_level}' added successfully!")
            log_admin_activity(
                request.user,
                f"Added new section: {section_id} (Grade {grade_level})",
                "section"
            )
        except Teachers.DoesNotExist:
            messages.error(request, "Selected adviser not found.")
        except Exception as e:
            messages.error(request, f"Error adding section: {str(e)}")
            
    return redirect('sections')

def edit_section(request, pk=None):
    if request.method == 'POST':
        section_id = request.POST.get('section_id')
        grade_level = request.POST.get('grade_level')
        adviser_id = request.POST.get('adviser')
        
        try:
            section = Sections.objects.get(id=pk)
            adviser = Teachers.objects.get(id=adviser_id)
            
            section.grade_level = grade_level
            section.adviser = adviser
            section.save()
            
            messages.success(request, f"Section updated successfully!")
            log_admin_activity(
                request.user,
                f"Updated section: {section.section_id}",
                "section"
            )
        except Sections.DoesNotExist:
            messages.error(request, "Section not found.")
        except Teachers.DoesNotExist:
            messages.error(request, "Selected adviser not found.")
        except Exception as e:
            messages.error(request, f"Error updating section: {str(e)}")
            
    return redirect('sections')

def delete_section(request, pk=None):
    if request.method == 'POST':
        try:
            section = Sections.objects.get(id=pk)
            section_id = section.section_id
            grade_level = section.grade_level
            section.delete()
            messages.success(request, f"Section '{section_id} - {grade_level}' deleted successfully!")
        except Sections.DoesNotExist:
            messages.error(request, "Section not found.")
        except Exception as e:
            messages.error(request, f"Error deleting section: {str(e)}")
            
    return redirect('sections')

@login_required
def enrollment_view(request):
    active_school_year = SchoolYear.get_active()
    previous_school_year = SchoolYear.objects.filter(is_previous=True).first()
    
    selected_year = request.GET.get('school_year', 
                                  active_school_year.display_name if active_school_year else None)
    
    # Get all enrollments for the selected school year
    if selected_year:
        enrollments = []
        # Get enrollments from each grade level
        enrollments.extend(list(Enrollment.objects.filter(
            school_year=selected_year
        ).select_related('student', 'section')))
        
        enrollments.extend(list(Grade8Enrollment.objects.filter(
            school_year=selected_year
        ).select_related('student', 'section')))
        
        enrollments.extend(list(Grade9Enrollment.objects.filter(
            school_year=selected_year
        ).select_related('student', 'section')))
        
        enrollments.extend(list(Grade10Enrollment.objects.filter(
            school_year=selected_year
        ).select_related('student', 'section')))
        
        enrollments.extend(list(Grade11Enrollment.objects.filter(
            school_year=selected_year
        ).select_related('student', 'section')))
        
        enrollments.extend(list(Grade12Enrollment.objects.filter(
            school_year=selected_year
        ).select_related('student', 'section')))
    else:
        enrollments = []

    # Get students who are not enrolled in any grade for the active school year
    if active_school_year:
        enrolled_students = set()
        
        # Get all enrolled students from each grade level
        enrolled_students.update(
            Enrollment.objects.filter(school_year=active_school_year.display_name).values_list('student_id', flat=True),
            Grade8Enrollment.objects.filter(school_year=active_school_year.display_name).values_list('student_id', flat=True),
            Grade9Enrollment.objects.filter(school_year=active_school_year.display_name).values_list('student_id', flat=True),
            Grade10Enrollment.objects.filter(school_year=active_school_year.display_name).values_list('student_id', flat=True),
            Grade11Enrollment.objects.filter(school_year=active_school_year.display_name).values_list('student_id', flat=True),
            Grade12Enrollment.objects.filter(school_year=active_school_year.display_name).values_list('student_id', flat=True)
        )

        # Get completed grade levels for each student
        completed_grade_levels = {}
        for student in Student.objects.filter(status__in=['Not Enrolled', 'Transferred', 'Dropped']):
            completed_levels = []  # Changed from set() to list
            
            # Check each grade level model for completed enrollments
            if Enrollment.objects.filter(student=student, status='Completed').exists():
                completed_levels.append(7)
            if Grade8Enrollment.objects.filter(student=student, status='Completed').exists():
                completed_levels.append(8)
            if Grade9Enrollment.objects.filter(student=student, status='Completed').exists():
                completed_levels.append(9)
            if Grade10Enrollment.objects.filter(student=student, status='Completed').exists():
                completed_levels.append(10)
            if Grade11Enrollment.objects.filter(student=student, status='Completed').exists():
                completed_levels.append(11)
            if Grade12Enrollment.objects.filter(student=student, status='Completed').exists():
                completed_levels.append(12)
                
            if completed_levels:  # Only add if student has completed levels
                completed_grade_levels[str(student.id)] = completed_levels  # Convert ID to string for JSON
        
        available_students = Student.objects.filter(
            status__in=['Not Enrolled', 'Transferred', 'Dropped']
        ).exclude(id__in=enrolled_students)
    else:
        available_students = Student.objects.none()
        completed_grade_levels = {}

    # Initialize sections_by_grade with empty lists for each grade level
    sections_by_grade = {7: [], 8: [], 9: [], 10: [], 11: [], 12: []}
    
    # Get all sections and their enrollments
    all_sections = Sections.objects.all().order_by('grade_level', 'section_id')
    
    if selected_year:
        for section in all_sections:
            grade = int(section.grade_level)
            
            # Get enrollments based on grade level
            if grade == 10:
                enrollments = Grade10Enrollment.objects.filter(
                    section=section,
                    school_year=selected_year,
                    status='Active'  # Only get active enrollments
                ).select_related('student')
            elif grade == 7:
                enrollments = Enrollment.objects.filter(section=section, school_year=selected_year).select_related('student')
            elif grade == 8:
                enrollments = Grade8Enrollment.objects.filter(section=section, school_year=selected_year).select_related('student')
            elif grade == 9:
                enrollments = Grade9Enrollment.objects.filter(section=section, school_year=selected_year).select_related('student')
            elif grade == 11:
                enrollments = Grade11Enrollment.objects.filter(section=section, school_year=selected_year).select_related('student')
            elif grade == 12:
                enrollments = Grade12Enrollment.objects.filter(section=section, school_year=selected_year).select_related('student')
            else:
                enrollments = []

            # Add section data to appropriate grade level
            if grade in sections_by_grade:
                sections_by_grade[grade].append({
                    'section': section,
                    'enrollments': enrollments,
                    'count': len(enrollments)
                })

    context = {
        'sections_by_grade': sections_by_grade,
        'sections': all_sections,
        'available_students': available_students,
        'completed_grade_levels': json.dumps(completed_grade_levels),
        'school_years': SchoolYear.objects.all().order_by('-year_start'),
        'active_school_year': active_school_year,
        'previous_school_year': previous_school_year,
        'selected_year': selected_year,
        'enrollments': enrollments  # Add enrollments to context
    }
    
    return render(request, 'enrollment.html', context)

def add_enrollment(request):
    if request.method == 'POST':
        try:
            student = Student.objects.get(id=request.POST['student'])
            section = Sections.objects.get(id=request.POST['section'])
            school_year = request.POST['school_year']
            grade_level = int(section.grade_level)
            track = request.POST.get('track', '')  # For senior high

            # Check if student has already completed or is currently enrolled in this grade level in ANY school year
            completed_or_active = False
            
            if grade_level == 7:
                completed_or_active = Enrollment.objects.filter(
                    student=student,
                    section__grade_level=grade_level,
                    status__in=['Completed', 'Active']
                ).exists()
            elif grade_level == 8:
                completed_or_active = Grade8Enrollment.objects.filter(
                    student=student,
                    section__grade_level=grade_level,
                    status__in=['Completed', 'Active']
                ).exists()
            elif grade_level == 9:
                completed_or_active = Grade9Enrollment.objects.filter(
                    student=student,
                    section__grade_level=grade_level,
                    status__in=['Completed', 'Active']
                ).exists()
            elif grade_level == 10:
                completed_or_active = Grade10Enrollment.objects.filter(
                    student=student,
                    section__grade_level=grade_level,
                    status__in=['Completed', 'Active']
                ).exists()
            elif grade_level == 11:
                completed_or_active = Grade11Enrollment.objects.filter(
                    student=student,
                    section__grade_level=grade_level,
                    status__in=['Completed', 'Active']
                ).exists()
            elif grade_level == 12:
                completed_or_active = Grade12Enrollment.objects.filter(
                    student=student,
                    section__grade_level=grade_level,
                    status__in=['Completed', 'Active']
                ).exists()

            if completed_or_active:
                messages.error(
                    request, 
                    f"Cannot enroll student in Grade {grade_level}. Student has already completed or is currently enrolled in this grade level."
                )
                return redirect('enrollment')

            # Check if previous grade level is completed (except for Grade 7)
            if grade_level > 7:
                previous_grade_completed = False
                if grade_level == 8:
                    previous_grade_completed = Enrollment.objects.filter(
                        student=student,
                        section__grade_level=7,
                        status='Completed'
                    ).exists()
                elif grade_level == 9:
                    previous_grade_completed = Grade8Enrollment.objects.filter(
                        student=student,
                        section__grade_level=8,
                        status='Completed'
                    ).exists()
                elif grade_level == 10:
                    previous_grade_completed = Grade9Enrollment.objects.filter(
                        student=student,
                        section__grade_level=9,
                        status='Completed'
                    ).exists()
                elif grade_level == 11:
                    previous_grade_completed = Grade10Enrollment.objects.filter(
                        student=student,
                        section__grade_level=10,
                        status='Completed'
                    ).exists()
                elif grade_level == 12:
                    previous_grade_completed = Grade11Enrollment.objects.filter(
                        student=student,
                        section__grade_level=11,
                        status='Completed'
                    ).exists()

                if not previous_grade_completed:
                    messages.error(
                        request, 
                        f"Cannot enroll in Grade {grade_level}. Student must complete Grade {grade_level-1} first."
                    )
                    return redirect('enrollment')

            # Create enrollment based on grade level
            enrollment_data = {
                'student': student,
                'section': section,
                'school_year': school_year,
                'status': 'Active'
            }

            if grade_level == 7:
                Enrollment.objects.create(**enrollment_data)
                messages.success(request, f"Student enrolled in Grade 7 successfully!")
            elif grade_level == 8:
                Grade8Enrollment.objects.create(**enrollment_data)
                messages.success(request, f"Student enrolled in Grade 8 successfully!")
            elif grade_level == 9:
                Grade9Enrollment.objects.create(**enrollment_data)
                messages.success(request, f"Student enrolled in Grade 9 successfully!")
            elif grade_level == 10:
                Grade10Enrollment.objects.create(**enrollment_data)
                messages.success(request, f"Student enrolled in Grade 10 successfully!")
            elif grade_level == 11:
                if not track:
                    messages.error(request, "Academic track is required for Grade 11")
                    return redirect('enrollment')
                enrollment_data['track'] = track
                Grade11Enrollment.objects.create(**enrollment_data)
                messages.success(request, f"Student enrolled in Grade 11 successfully!")
            elif grade_level == 12:
                if not track:
                    messages.error(request, "Academic track is required for Grade 12")
                    return redirect('enrollment')
                enrollment_data['track'] = track
                Grade12Enrollment.objects.create(**enrollment_data)
                messages.success(request, f"Student enrolled in Grade 12 successfully!")

            # Update student status
            student.status = 'Active'
            student.save()

            log_admin_activity(
                request.user,
                f"Enrolled student {student.first_name} {student.last_name} in Grade {grade_level}",
                "enrollment"
            )

        except Exception as e:
            messages.error(request, f"Error enrolling student: {str(e)}")

    return redirect('enrollment')

def edit_enrollment(request):
    if request.method == 'POST':
        enrollment_id = request.POST.get('enrollment_id')
        new_status = request.POST.get('status')
        
        try:
            enrollment = Enrollment.objects.get(id=enrollment_id)
            student = enrollment.student  # Get the student reference
            old_status = enrollment.status  # Store the old status
            
            # Update student status based on enrollment status
            if new_status == 'Active':
                student.status = 'Enrolled'
            elif new_status == 'Withdrawn':
                student.status = 'Not Enrolled'
            elif new_status == 'Completed':
                student.status = 'Completed'
                CompletedStudent.objects.create(
                    enrollment=enrollment,
                    completion_date=request.POST.get('completion_date'),
                    final_grade=request.POST.get('final_grade'),
                    remarks=request.POST.get('completion_remarks', '')
                )
                enrollment.status = new_status
                enrollment.save()
                log_admin_activity(
                    request.user,
                    f"Marked {student.first_name} {student.last_name}'s enrollment as Completed",
                    "enrollment"
                )
            elif new_status == 'Dropped':
                student.status = 'Dropped'
                DroppedStudent.objects.create(
                    enrollment=enrollment,
                    drop_date=request.POST.get('drop_date'),
                    reason=request.POST.get('drop_reason', 'Status changed to Dropped'),
                    remarks=request.POST.get('drop_remarks', '')
                )
                enrollment.delete()
                log_admin_activity(
                    request.user,
                    f"Marked {student.first_name} {student.last_name} as Dropped",
                    "enrollment"
                )
            elif new_status == 'Transferred':
                student.status = 'Transferred'
                transfer_school = request.POST.get('transfer_school', 'Not specified')
                TransferredStudent.objects.create(
                    enrollment=enrollment,
                    transfer_date=request.POST.get('transfer_date'),
                    transfer_school=transfer_school,
                    reason=request.POST.get('transfer_reason', 'Status changed to Transferred'),
                    remarks=request.POST.get('transfer_remarks', '')
                )
                enrollment.delete()
                log_admin_activity(
                    request.user,
                    f"Marked {student.first_name} {student.last_name} as Transferred to {transfer_school}",
                    "enrollment"
                )
            
            # Save student status changes
            student.save()
            
            if new_status in ['Dropped', 'Transferred']:
                messages.success(request, f'Student {student.first_name} {student.last_name} has been marked as {new_status}')
            elif new_status == 'Completed':
                messages.success(request, f'Student {student.first_name} {student.last_name} has completed the enrollment')
            else:
                # For Active and Withdrawn statuses
                enrollment.status = new_status
                enrollment.save()
                messages.success(request, 'Enrollment status updated successfully')
            
        except Enrollment.DoesNotExist:
            messages.error(request, 'Enrollment not found!')
        except Exception as e:
            messages.error(request, f'Error updating enrollment: {str(e)}')
        
    return redirect('enrollment')

def delete_enrollment(request):
    if request.method == 'POST':
        try:
            enrollment_id = request.POST.get('enrollment_id')
            enrollment = Enrollment.objects.get(id=enrollment_id)
            student = enrollment.student
            student_name = f"{student.first_name} {student.last_name}"
            section_id = enrollment.section.section_id
            
            # Delete the enrollment
            enrollment.delete()
            
            # Check if student has any other active enrollments
            active_enrollments = Enrollment.objects.filter(
                student=student, 
                status='Active'
            ).exists()
            
            # If no active enrollments, update student status to "Not Enrolled"
            if not active_enrollments:
                student.status = 'Not Enrolled'
                student.save()
            
            messages.success(request, f"Enrollment of {student_name} in {section_id} has been deleted.")
            
        except Enrollment.DoesNotExist:
            messages.error(request, 'Enrollment not found!')
        except Exception as e:
            messages.error(request, f'Error deleting enrollment: {str(e)}')
    
    return redirect('enrollment')

def edit_student(request):
    if request.method == 'POST':
        try:
            student_id = request.POST.get('student_id')
            name_parts = request.POST.get('name', '').split()
            gender = request.POST.get('gender')
            email = request.POST.get('email')
            mobile_number = request.POST.get('mobile_number')
            status = request.POST.get('status')
            
            # Get the student object
            student = Student.objects.get(student_id=student_id)
            
            # Update student information
            if len(name_parts) >= 2:
                student.first_name = name_parts[0]
                student.last_name = name_parts[-1]
                # If there are middle names
                if len(name_parts) > 2:
                    student.middle_name = ' '.join(name_parts[1:-1])
                else:
                    student.middle_name = ''
            
            student.gender = gender
            student.email = email
            student.mobile_number = mobile_number
            student.status = status
            student.save()
            
            log_admin_activity(
                request.user,
                f"Updated student information: {student.first_name} {student.last_name} ({student.student_id})",
                "student"
            )
            messages.success(request, 'Student updated successfully!')
            
        except Student.DoesNotExist:
            messages.error(request, 'Student not found!')
        except Exception as e:
            messages.error(request, f'Error updating student: {str(e)}')
    
    return redirect('students')

def delete_student(request):
    if request.method == 'POST':
        try:
            student_id = request.POST.get('student_id')
            student = Student.objects.get(student_id=student_id)
            name = f"{student.first_name} {student.last_name}"
            student_id = student.student_id
            student.delete()
            
            log_admin_activity(
                request.user,
                f"Deleted student: {name} ({student_id})",
                "student"
            )
            messages.success(request, 'Student deleted successfully!')
        except Exception as e:
            messages.error(request, f'Error deleting student: {str(e)}')
    return redirect('students')

@transaction.atomic
def create_student_account(request):
    if request.method == 'POST':
        try:
            # Get form data
            student_id = request.POST.get('student_id')
            username = request.POST.get('username')
            email = request.POST.get('email')
            password = request.POST.get('password')
            confirm_password = request.POST.get('confirm_password')
            contact_number = request.POST.get('contact_number')
            
            # Validate passwords match
            if password != confirm_password:
                messages.error(request, "Passwords do not match!")
                return redirect('students')
            
            # Check if username already exists
            if User.objects.filter(username=username).exists():
                messages.error(request, f"Username '{username}' is already taken.")
                return redirect('students')
            
            # Get the student
            student = get_object_or_404(Student, id=student_id)
            
            # Check if student already has an account
            if student.has_account:
                messages.error(request, f"{student.first_name} {student.last_name} already has an account.")
                return redirect('students')
            
            # Update student contact number if provided
            if contact_number:
                student.mobile_number = contact_number
                student.save(update_fields=['mobile_number'])
            
            # Get student photo if uploaded
            student_photo = request.FILES.get('student_photo')
            
            # Prepare guardian data
            guardian_data = {
                'first_name': request.POST.get('guardian_first_name'),
                'middle_name': request.POST.get('guardian_middle_name'),
                'last_name': request.POST.get('guardian_last_name'),
                'contact_number': request.POST.get('guardian_contact'),
                'relationship': request.POST.get('guardian_relationship')
            }
            
            # Create user account
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=student.first_name,
                last_name=student.last_name
            )
            
            # Update student model
            student.has_account = True
            student.user = user
            
            # Handle student photo if provided
            if student_photo:
                student.student_photo = student_photo
            
            student.save()
            
            # Create student account
            account = StudentAccount.objects.create(
                student=student,
                user=user,
                is_active=True
            )
            
            # Create guardian record
            Guardian.objects.create(
                student=student,
                first_name=guardian_data.get('first_name', ''),
                middle_name=guardian_data.get('middle_name', ''),
                last_name=guardian_data.get('last_name', ''),
                contact_number=guardian_data.get('contact_number', ''),
                relationship=guardian_data.get('relationship', 'Guardian')
            )
            
            messages.success(request, f"Account created successfully for {student.first_name} {student.last_name}.")
            log_admin_activity(
                request.user,
                f"Created account for student: {student.first_name} {student.last_name}",
                "student"
            )
            
        except Exception as e:
            # Print the error to the console for debugging
            import traceback
            traceback.print_exc()
            
            messages.error(request, f"Error creating account: {str(e)}")
    
    return redirect('students')

@login_required
def student_profile_view(request, student_id):
    # Get the student or return 404
    student = get_object_or_404(Student, id=student_id)
    
    # Security check - only allow viewing if the logged-in user matches the student's user
    # or if the user is an admin/staff
    if request.user != student.user and not request.user.is_staff:
        messages.error(request, "You don't have permission to view this profile.")
        return redirect('login')
    
    # Get the student's current enrollment
    current_enrollment = Enrollment.objects.filter(
        student=student,
        status='Active'
    ).first()
    
    # If enrolled, get the section information
    if current_enrollment:
        student.section = current_enrollment.section.section_id
        student.grade_level = current_enrollment.section.grade_level
        student.school_year = current_enrollment.school_year
    
    context = {
        'student': student,
        'is_enrolled': current_enrollment is not None
    }
    
    return render(request, 'StudentProfiles/templates/student_profile.html', context)

@login_required
def student_grades_view(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    
    # Get current enrollment
    current_enrollment = Enrollment.objects.filter(
        student=student,
        status='Active'
    ).first()
    
    if current_enrollment:
        student.section = current_enrollment.section.section_id
        student.grade_level = current_enrollment.section.grade_level
    
    # Get the student's schedule to know which subjects they're enrolled in
    student_schedules = Schedules.objects.filter(
        section=current_enrollment.section if current_enrollment else None
    ).select_related('subject', 'teacher')
    
    # Create a list to store subject grades
    subjects_with_grades = []
    
    for schedule in student_schedules:
        try:
            # Get the latest grades for this subject
            grades = Grades.objects.filter(
                student=student,
                subject=schedule.subject,
                teacher=schedule.teacher,
                school_year=current_enrollment.school_year if current_enrollment else None
            ).first()
            
            subject_data = {
                'name': schedule.subject.name,
                'teacher': f"{schedule.teacher.first_name} {schedule.teacher.last_name}",
                'q1_grade': grades.q1_grade if grades else None,
                'q2_grade': grades.q2_grade if grades else None,
                'q3_grade': grades.q3_grade if grades else None,
                'q4_grade': grades.q4_grade if grades else None,
                'final_grade': grades.final_grade if grades and grades.final_grade else None
            }
            
            subjects_with_grades.append(subject_data)
        except Exception as e:
            print(f"Error getting grades for subject {schedule.subject.name}: {str(e)}")
            continue
    
    context = {
        'student': student,
        'subjects': subjects_with_grades,
        'current_quarter': get_current_quarter(),
        'school_year': current_enrollment.school_year if current_enrollment else None
    }
    
    return render(request, 'grades.html', context)

def get_current_quarter():
    """Helper function to determine current quarter based on date"""
    current_month = datetime.now().month
    
    if 6 <= current_month <= 8:  # June to August
        return 1
    elif 9 <= current_month <= 11:  # September to November
        return 2
    elif current_month == 12 or current_month == 1:  # December to January
        return 3
    else:  # February to May
        return 4

@login_required
def grades_view(request):
    print("Grades view function called!")
    try:
        # Get the current school year (default to current year)
        current_year = datetime.now().year
        school_year = request.GET.get('school_year', f"{current_year}-{current_year+1}")
        
        # Get all sections with their enrollments and students
        sections = Sections.objects.all().prefetch_related(
            'enrollments__student__grades'
        )
        
        # Filter by school year if provided
        if school_year:
            sections = sections.filter(
                enrollments__school_year=school_year
            ).distinct()
        
        # Organize sections by year level
        sections_by_year = {}
        year_levels = set()
        
        for section in sections:
            year_level = section.grade_level
            if year_level not in sections_by_year:
                sections_by_year[year_level] = []
            sections_by_year[year_level].append(section)
            year_levels.add(year_level)
        
        # Get available school years for the dropdown
        available_years = Enrollment.objects.values_list(
            'school_year', flat=True
        ).distinct().order_by('-school_year')
        
        # Get current subject (you may need to adjust this based on your needs)
        current_subject = None
        if request.user.is_authenticated and hasattr(request.user, 'teacher'):
            # If the user is a teacher, get their current subject
            teacher_schedule = Schedules.objects.filter(teacher=request.user.teacher).first()
            if teacher_schedule:
                current_subject = teacher_schedule.subject
        
        context = {
            'sections_by_year': sections_by_year,
            'year_levels': sorted(year_levels),
            'school_year': school_year,
            'available_years': available_years,
            'current_subject': current_subject  # Add this to the context
        }
        
        return render(request, 'gradesSubmission.html', context)
    
    except Exception as e:
        messages.error(request, f"Error loading grades: {str(e)}")
        return redirect('dashboard')

def add_grade(request):
    """View function to add or update a grade"""
    if request.method == 'POST':
        try:
            student_id = request.POST.get('student')
            subject_id = request.POST.get('subject')
            school_year = request.POST.get('school_year')
            quarter = request.POST.get('quarter')
            grade_value = request.POST.get('grade')
            
            # Get the teacher, student and subject
            teacher = Teachers.objects.get(user=request.user)
            student = Student.objects.get(id=student_id)
            subject = Subject.objects.get(id=subject_id)
            
            # Try to get existing grade record or create a new one
            grade, created = Grades.objects.get_or_create(
                student=student,
                subject=subject,
                teacher=teacher,
                school_year=school_year,
                defaults={f'q{quarter}_grade': grade_value}
            )
            
            # If record exists, update the specific quarter
            if not created:
                setattr(grade, f'q{quarter}_grade', grade_value)
                grade.save()
            
            # Calculate and update final grade
            grade.calculate_final_grade()
            grade.save()
            
            messages.success(request, f"Grade for {student.first_name} {student.last_name} in {subject.name} has been updated.")
            log_admin_activity(
                request.user,
                f"Added grades for {student.first_name} {student.last_name} in {subject.name}",
                "grade"
            )
            
        except Exception as e:
            messages.error(request, f"Error adding grade: {str(e)}")
    
    return redirect('grades')

@login_required
def delete_teacher(request):
    if request.method == "POST":
        teacher_id = request.POST.get('teacher_id')
        try:
            teacher = Teachers.objects.get(teacher_id=teacher_id)
            # Delete associated user first
            if teacher.user:
                teacher.user.delete()
            teacher.delete()
            messages.success(request, 'Teacher deleted successfully.')
            log_admin_activity(
                request.user,
                f"Deleted teacher: {teacher.first_name} {teacher.last_name}",
                "teacher"
            )
        except Teachers.DoesNotExist:
            messages.error(request, 'Teacher not found.')
        except Exception as e:
            messages.error(request, f'Error deleting teacher: {str(e)}')
    return redirect('teachers')

@login_required
def submit_grade(request):
    """View function to submit a grade"""
    if request.method == 'POST':
        try:
            student_id = request.POST.get('student')
            subject_id = request.POST.get('subject')
            quarter = request.POST.get('quarter')
            grade_value = request.POST.get('grade')
            school_year = request.POST.get('school_year', datetime.now().year)
            
            # Get the teacher, student and subject
            teacher = Teachers.objects.get(user=request.user)
            student = Student.objects.get(id=student_id)
            subject = Subject.objects.get(id=subject_id)
            
            # Try to get existing grade record or create a new one
            grade, created = Grades.objects.get_or_create(
                student=student,
                subject=subject,
                teacher=teacher,
                school_year=school_year,
                defaults={f'q{quarter}_grade': grade_value}
            )
            
            # If record exists, update the specific quarter
            if not created:
                setattr(grade, f'q{quarter}_grade', grade_value)
                grade.save()
            
            # Calculate and update final grade if needed
            if hasattr(grade, 'calculate_final_grade'):
                grade.calculate_final_grade()
                grade.save()
            
            messages.success(request, f"Grade for {student.first_name} {student.last_name} in {subject.name} has been updated.")
            
        except Exception as e:
            messages.error(request, f"Error submitting grade: {str(e)}")
    
    return redirect('grades')

def schedule_view(request):
    """View function for displaying the schedule page."""
    schedules = Schedules.objects.all().select_related('subject', 'teacher_id', 'section')
    
    # Fetch all required data from models
    teachers = Teachers.objects.all().order_by('first_name', 'last_name')
    subjects = Subject.objects.all().order_by('name')
    sections = Sections.objects.all().order_by('grade_level', 'section_id')
    grade_levels = Sections.objects.values_list('grade_level', flat=True).distinct().order_by('grade_level')
    
    sections_json = json.dumps([{
        'id': section.id,
        'section_id': section.section_id,
        'grade_level': section.grade_level
    } for section in sections], cls=DjangoJSONEncoder)
    
    context = {
        'schedules': schedules,
        'teachers': teachers,
        'subjects': subjects,
        'sections': sections,
        'grade_levels': grade_levels,
        'sections_json': sections_json,
    }
    return render(request, 'schedules.html', context)


def get_teachers(request):
    """API endpoint to get all teachers."""
    teachers = list(Teachers.objects.values('id', 'first_name', 'last_name'))
    return JsonResponse({'teachers': teachers})

def get_subjects(request):
    """API endpoint to get all subjects."""
    subjects = list(Subject.objects.values('id', 'name'))
    return JsonResponse({'subjects': subjects})

def get_grade_levels(request):
    """API endpoint to get all grade levels."""
    grade_levels = list(Sections.objects.values_list('grade_level', flat=True).distinct().order_by('grade_level'))
    return JsonResponse({'grade_levels': grade_levels})

def get_sections_by_grade(request):
    """Get sections for a specific grade level."""
    grade_level = request.GET.get('grade_level')
    
    if grade_level:
        try:
            # Convert to integer
            grade_level = int(grade_level)
            
            # Get sections for this grade level
            sections = Sections.objects.filter(grade_level=grade_level)
            sections_data = list(sections.values('id', 'section_id'))
            
            # Return JSON response
            return JsonResponse({'sections': sections_data})
        except Exception as e:
            print(f"Error in get_sections_by_grade: {e}")
    
    # Return empty list if no grade level or error
    return JsonResponse({'sections': []})

def get_sections(request):
    """API endpoint to get all sections with their grade levels."""
    sections = list(Sections.objects.values('id', 'section_id', 'grade_level'))
    return JsonResponse({'sections': sections})

def get_schedules(request):
    """API endpoint to get all schedules."""
    schedules = Schedules.objects.select_related('teacher_id', 'subject', 'section').all()
    schedule_data = [{
        'id': schedule.id,
        'teacher_name': f"{schedule.teacher_id.first_name} {schedule.teacher_id.last_name}",
        'subject_name': schedule.subject.name,
        'grade_level': schedule.grade_level,
        'section_id': schedule.section.section_id,
        'day': schedule.day,
        'start_time': schedule.start_time.strftime('%H:%M'),
        'end_time': schedule.end_time.strftime('%H:%M'),
        'room': schedule.room
    } for schedule in schedules]
    return JsonResponse({'schedules': schedule_data})

def filter_schedules(request):
    """API endpoint to get filtered schedules."""
    teacher = request.GET.get('teacher')
    grade_level = request.GET.get('grade_level')
    section = request.GET.get('section')
    day = request.GET.get('day')

    schedules = Schedules.objects.select_related('teacher_id', 'subject', 'section').all()

    if teacher:
        schedules = schedules.filter(teacher_id=teacher)
    if grade_level:
        schedules = schedules.filter(grade_level=grade_level)
    if section:
        schedules = schedules.filter(section=section)
    if day:
        schedules = schedules.filter(day=day)

    schedule_data = [{
        'id': schedule.id,
        'teacher_name': f"{schedule.teacher_id.first_name} {schedule.teacher_id.last_name}",
        'subject_name': schedule.subject.name,
        'grade_level': schedule.grade_level,
        'section_id': schedule.section.section_id,
        'day': schedule.day,
        'start_time': schedule.start_time.strftime('%H:%M'),
        'end_time': schedule.end_time.strftime('%H:%M'),
        'room': schedule.room
    } for schedule in schedules]
    return JsonResponse({'schedules': schedule_data})

def get_all_sections(request):
    """Get all sections for client-side filtering."""
    try:
        sections = list(Sections.objects.all().values('id', 'section_id', 'grade_level'))
        return JsonResponse({'success': True, 'sections': sections})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

def add_schedule(request):
    if request.method == 'POST':
        try:
            teacher_id = request.POST.get('teacher_id')
            subject_id = request.POST.get('subject')
            grade_level = request.POST.get('grade_level')
            section_id = request.POST.get('section')
            day = request.POST.get('day')
            start_time = request.POST.get('start_time')
            end_time = request.POST.get('end_time')
            room = request.POST.get('room')
            
            # Get the teacher, subject, and section objects
            teacher = Teachers.objects.get(id=teacher_id)
            subject = Subject.objects.get(id=subject_id)
            section = Sections.objects.get(id=section_id)
            
            # Create the schedule
            schedule = Schedules.objects.create(
                teacher_id=teacher,
                subject=subject,
                grade_level=grade_level,
                section=section,
                day=day,
                start_time=start_time,
                end_time=end_time,
                room=room
            )
            
            log_admin_activity(
                request.user,
                f"Added schedule for {schedule.teacher_id.first_name} {schedule.teacher_id.last_name} - {schedule.subject.name}",
                "schedule"
            )
            
            return JsonResponse({'success': True})
            
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})

def get_available_time_slots(request):
    """API endpoint to get available time slots for a given day and teacher."""
    teacher_id = request.GET.get('teacher_id')
    day = request.GET.get('day')
    section_id = request.GET.get('section_id')
    subject_id = request.GET.get('subject')
    grade_level = request.GET.get('grade_level')
    room = request.GET.get('room')

    # Check if subject is already assigned to this section
    if section_id and subject_id:
        existing_subject = Schedules.objects.filter(
            section_id=section_id,
            subject_id=subject_id
        ).first()
        
        if existing_subject:
            return JsonResponse({
                'error': 'This subject is already assigned to this section',
                'time_slots': []
            }, status=400)

    # Define all possible time slots (8 AM to 5 PM)
    time_slots = []
    start = datetime.strptime('08:00', '%H:%M')
    end = datetime.strptime('17:00', '%H:%M')
    
    # Create 1-hour time slots
    current = start
    while current < end:
        next_slot = current + timedelta(hours=1)
        if current.hour != 12:  # Skip lunch break
            time_slots.append({
                'start': current.strftime('%H:%M'),
                'end': next_slot.strftime('%H:%M'),
                'display': f"{current.strftime('%I:%M %p')} - {next_slot.strftime('%I:%M %p')}"
            })
        current = next_slot

    available_slots = []
    for slot in time_slots:
        slot_start = datetime.strptime(slot['start'], '%H:%M').time()
        slot_end = datetime.strptime(slot['end'], '%H:%M').time()
        
        is_available = True
        
        if day:
            # Check room conflicts
            if room:
                room_schedules = Schedules.objects.filter(
                    day=day,
                    room=room
                )
                if room_schedules.filter(
                    models.Q(start_time__lt=slot_end) & 
                    models.Q(end_time__gt=slot_start)
                ).exists():
                    is_available = False
            
            # Check teacher conflicts
            if is_available and teacher_id:
                teacher_schedules = Schedules.objects.filter(
                    teacher_id=teacher_id,
                    day=day
                )
                if teacher_schedules.filter(
                    models.Q(start_time__lt=slot_end) & 
                    models.Q(end_time__gt=slot_start)
                ).exists():
                    is_available = False
            
            # Check section conflicts
            if is_available and section_id:
                section_schedules = Schedules.objects.filter(
                    section_id=section_id,
                    day=day
                )
                if section_schedules.filter(
                    models.Q(start_time__lt=slot_end) & 
                    models.Q(end_time__gt=slot_start)
                ).exists():
                    is_available = False
        
        if is_available:
            available_slots.append(slot)

    return JsonResponse({'time_slots': available_slots})

def schedules_view(request):
    # Existing code...
    schedules = Schedules.objects.select_related('teacher_id', 'subject', 'section').all()
    sections = Sections.objects.prefetch_related(
        'schedules_set',
        'schedules_set__subject',
        'schedules_set__teacher_id'
    ).all()
    teachers = Teachers.objects.all()
    subjects = Subject.objects.all()
    grade_levels = range(7, 13)  # Grades 7-12

    context = {
        'schedules': schedules,
        'sections': sections,
        'teachers': teachers,
        'subjects': subjects,
        'grade_levels': grade_levels,
    }
    return render(request, 'schedules.html', context)

def get_section_schedule(request):
    """API endpoint to get a section's weekly schedule"""
    section_id = request.GET.get('section_id')
    if not section_id:
        return JsonResponse({'error': 'Section ID is required'}, status=400)
    
    try:
        section = Sections.objects.get(id=section_id)
        schedules = section.schedules_set.all().select_related('subject', 'teacher_id')
        
        # Generate time slots from 7 AM to 5 PM with exact hour ranges
        time_slots = []
        start_time = datetime.strptime('07:00', '%H:%M')
        end_time = datetime.strptime('17:00', '%H:%M')
        
        while start_time < end_time:
            next_time = start_time + timedelta(hours=1)
            time_slots.append({
                'start': start_time.time(),
                'end': next_time.time(),
                'display': f"{start_time.strftime('%I:%M %p')} - {next_time.strftime('%I:%M %p')}"
            })
            start_time = next_time

        # Generate HTML for the schedule table
        html = """
        <div class="table-responsive">
            <table class="table table-bordered">
                <thead>
                    <tr class="bg-light">
                        <th style="width: 150px;">Time</th>
                        <th>Monday</th>
                        <th>Tuesday</th>
                        <th>Wednesday</th>
                        <th>Thursday</th>
                        <th>Friday</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        
        for time_slot in time_slots:
            html += f"<tr><td class='font-weight-bold'>{time_slot['display']}</td>"
            
            for day in days:
                html += "<td style='height: 100px; padding: 0.5rem;'>"
                for schedule in schedules:
                    if (schedule.day == day and 
                        schedule.start_time <= time_slot['start'] and 
                        schedule.end_time > time_slot['start']):
                        html += f"""
                            <div class="schedule-item bg-primary text-white p-2 rounded">
                                <strong>{schedule.subject.name}</strong><br>
                                <small>{schedule.teacher_id.first_name} {schedule.teacher_id.last_name}</small><br>
                                <small>Room: {schedule.room}</small>
                            </div>
                        """
                html += "</td>"
            
            html += "</tr>"
        
        html += "</tbody></table></div>"
        
        return JsonResponse({
            'html': html,
            'section_name': f"Grade {section.grade_level} - Section {section.section_id}"
        })
        
    except Sections.DoesNotExist:
        return JsonResponse({'error': 'Section not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def get_enrolled_students(request):
    grade_level = request.GET.get('grade_level')
    section_id = request.GET.get('section_id')
    selected_school_year = request.GET.get('school_year', '')  # Make school_year optional for section view
    
    try:
        grade_number = int(grade_level)
        section = Sections.objects.get(id=section_id)
        
        # Get enrollments based on grade level and section
        if grade_number == 7:
            enrollments = Enrollment.objects.filter(
                section=section,
                status='Active'
            ).select_related('student', 'section')
        elif grade_number == 8:
            enrollments = Grade8Enrollment.objects.filter(
                section=section,
                status='Active'
            ).select_related('student', 'section')
        elif grade_number == 9:
            enrollments = Grade9Enrollment.objects.filter(
                section=section,
                status='Active'
            ).select_related('student', 'section')
        elif grade_number == 10:
            enrollments = Grade10Enrollment.objects.filter(
                section=section,
                status='Active'
            ).select_related('student', 'section')
        elif grade_number == 11:
            enrollments = Grade11Enrollment.objects.filter(
                section=section,
                status='Active'
            ).select_related('student', 'section')
        elif grade_number == 12:
            enrollments = Grade12Enrollment.objects.filter(
                section=section,
                status='Active'
            ).select_related('student', 'section')
        else:
            return JsonResponse({'error': f'Invalid grade level: {grade_number}'}, status=400)

        # Add school year filter if provided
        if selected_school_year:
            enrollments = enrollments.filter(school_year=selected_school_year)

        students = []
        for enrollment in enrollments:
            students.append({
                'student_id': enrollment.student.student_id,
                'first_name': enrollment.student.first_name,
                'last_name': enrollment.student.last_name,
                'section_id': enrollment.section.section_id,
                'status': enrollment.status
            })
        
        # Sort students by ID
        students.sort(key=lambda x: x['student_id'])
        
        return JsonResponse({
            'students': students,
            'grade_level': f"Grade {grade_number}",
            'section_id': section.section_id,
            'total_students': len(students)
        })
        
    except Exception as e:
        print(f"Error in get_enrolled_students: {str(e)}")  # Debug line
        return JsonResponse({'error': str(e)}, status=500)

def get_eligible_students(request):
    """API endpoint to get students eligible for promotion"""
    school_year = request.GET.get('school_year')
    current_grade = request.GET.get('grade_level')
    
    # Base query for enrollments
    enrollment_query = Enrollment.objects.filter(
        section__grade_level=current_grade,
        status='Active'
    ).select_related('student')
    
    # Apply school year filter if not "all"
    if school_year and school_year != 'all':
        enrollment_query = enrollment_query.filter(school_year=school_year)
    
    students = []
    seen_students = set()  # To prevent duplicates
    
    for enrollment in enrollment_query:
        student_id = enrollment.student.id
        
        # Skip if we've already processed this student
        if student_id in seen_students:
            continue
        seen_students.add(student_id)
        
        # Calculate overall grade for the student
        grades_query = Grades.objects.filter(
            student=enrollment.student
        )
        
        # Filter grades by school year if specific year selected
        if school_year and school_year != 'all':
            grades_query = grades_query.filter(school_year=school_year)
        
        overall_grade = grades_query.aggregate(
            avg_grade=Avg('final_grade')
        )['avg_grade'] or 0
        
        # Student is eligible if overall grade is >= 75
        is_eligible = overall_grade >= 75
        
        students.append({
            'id': student_id,
            'student_id': enrollment.student.student_id,
            'name': f"{enrollment.student.first_name} {enrollment.student.last_name}",
            'grade_level': current_grade,
            'overall_grade': round(overall_grade, 2),
            'is_eligible': is_eligible,
            'school_year': enrollment.school_year
        })
    
    # Sort students by ID
    students.sort(key=lambda x: x['student_id'])
    
    return JsonResponse({'students': students})

@transaction.atomic
def promote_students(request):
    """View to handle student promotion"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=400)
    
    try:
        from_year = request.POST.get('from_school_year')
        to_year = request.POST.get('to_school_year')
        current_grade = request.POST.get('current_grade')
        student_ids = request.POST.getlist('student_ids[]')
        
        # Get the next grade level
        grade_levels = {
            'Grade 7': 'Grade 8',
            'Grade 8': 'Grade 9',
            'Grade 9': 'Grade 10',
            'Grade 10': 'Grade 11',
            'Grade 11': 'Grade 12'
        }
        next_grade = grade_levels.get(current_grade)
        
        if not next_grade:
            return JsonResponse({'error': 'Invalid grade level'}, status=400)
        
        # Get the section for the next grade
        next_section = Sections.objects.filter(grade_level=next_grade).first()
        if not next_section:
            return JsonResponse({'error': f'No section found for {next_grade}'}, status=400)
        
        # Process each student
        for student_id in student_ids:
            student = Student.objects.get(id=student_id)
            
            # Create new enrollment for next year
            Enrollment.objects.create(
                student=student,
                section=next_section,
                school_year=to_year,
                status='Active'
            )
            
            # Update current enrollment status to 'Completed'
            current_enrollment = Enrollment.objects.get(
                student=student,
                school_year=from_year,
                status='Active'
            )
            current_enrollment.status = 'Completed'
            current_enrollment.save()
            
            log_admin_activity(
                request.user,
                f"Promoted {student.first_name} {student.last_name} to {next_grade}",
                "student"
            )
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def log_admin_activity(user, action, action_type):
    """
    action_type can be:
    - student
    - teacher
    - subject
    - section
    - schedule
    - enrollment
    - grade
    - profile
    """
    AdminActivity.objects.create(
        admin=user,
        action=action,
        action_type=action_type
    )
@login_required
def admin_profile(request):
    try:
        admin_profile = AdminProfile.objects.get(user=request.user)
    except AdminProfile.DoesNotExist:
        admin_profile = AdminProfile.objects.create(user=request.user)
    
    # Get recent activities
    recent_activities = AdminActivity.objects.filter(admin=request.user)[:5]
    
    context = {
        'admin_profile': admin_profile,
        'recent_activities': recent_activities
    }
    return render(request, 'admin_profile.html', context)

@login_required
def admin_profile_update(request):
    if request.method == 'POST':
        try:
            user = request.user
            user.first_name = request.POST.get('first_name', '')
            user.last_name = request.POST.get('last_name', '')
            user.email = request.POST.get('email', '')
            
            # Update password if provided
            new_password = request.POST.get('new_password')
            if new_password:
                user.set_password(new_password)
            
            user.save()
            
            # Handle profile photo
            if request.FILES.get('profile_photo'):
                profile = AdminProfile.objects.get_or_create(user=user)[0]
                profile.profile_photo = request.FILES['profile_photo']
                profile.save()
            
            messages.success(request, 'Profile updated successfully!')
            
            # If password was changed, redirect to login
            if new_password:
                return redirect('login')
                
        except Exception as e:
            messages.error(request, f'Error updating profile: {str(e)}')
            
    return redirect('admin_profile')

def get_section_grade(request):
    section_id = request.GET.get('section_id')
    try:
        section = Sections.objects.get(id=section_id)
        return JsonResponse({
            'grade_level': section.grade_level
        })
    except Sections.DoesNotExist:
        return JsonResponse({'error': 'Section not found'}, status=404)

@login_required
def school_year_management(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'add':
            try:
                year_start = int(request.POST.get('year_start'))
                year_end = int(request.POST.get('year_end'))
                is_active = request.POST.get('is_active') == 'true'
                
                school_year = SchoolYear.objects.create(
                    year_start=year_start,
                    year_end=year_end,
                    is_active=is_active
                )
                
                log_admin_activity(
                    request.user,
                    f"Added new school year {school_year.display_name}",
                    'school_year'
                )
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'status': 'success',
                        'message': f'School year {school_year.display_name} added successfully!',
                        'redirect': reverse('enrollment')
                    })
                
                messages.success(request, f'School year {school_year.display_name} added successfully!')
                return redirect('enrollment')
                
            except Exception as e:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'status': 'error',
                        'message': str(e)
                    })
                messages.error(request, str(e))

        elif action == 'activate':
            try:
                school_year_id = request.POST.get('school_year_id')
                school_year = SchoolYear.objects.get(id=school_year_id)
                
                # This will trigger the save method which handles status updates
                school_year.is_active = True
                school_year.save()
                
                log_admin_activity(
                    request.user,
                    f"Set {school_year.display_name} as active school year",
                    'school_year'
                )
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'status': 'success',
                        'message': f'{school_year.display_name} has been set as the active school year.',
                        'redirect': reverse('enrollment')
                    })
                
                messages.success(request, 
                    f'{school_year.display_name} has been set as the active school year. '
                    'Student statuses have been updated for the new school year.'
                )
                return redirect('enrollment')
                
            except SchoolYear.DoesNotExist:
                messages.error(request, 'School year not found.')
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'status': 'error',
                        'message': 'School year not found.'
                    })

    school_years = SchoolYear.get_all_years()
    active_school_year = SchoolYear.get_active()
    previous_school_year = SchoolYear.objects.filter(is_previous=True).first()
    
    context = {
        'school_years': school_years,
        'active_school_year': active_school_year,
        'previous_school_year': previous_school_year,
        'current_year': datetime.now().year
    }
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'school_year_management_table.html', context)
    
    return render(request, 'school_year_management.html', context)



    