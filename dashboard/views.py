from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from .models import (
    Student, Teachers, Subject, Schedules, Sections, 
    Enrollment, Grade8Enrollment, Grade9Enrollment, 
    Grade10Enrollment, Grade11Enrollment, Grade12Enrollment,
    StudentAccount, Guardian, Grades, DroppedStudent, 
    TransferredStudent, CompletedStudent, AdminProfile, 
    AdminActivity, SchoolYear,
    Event, Archive, Announcement,
    
)

from .forms_models import SchoolForm, TeacherForm, FormSubmission
import pandas as pd
from django.core.exceptions import ValidationError

from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Avg
from django.conf import settings
from django.http import JsonResponse
from datetime import datetime, timedelta, date, time
from django.utils import timezone
from django.db import transaction
from django.db import models
from django.views.decorators.http import require_POST
import json
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models.functions import ExtractMonth
from django.db.models import Q
from collections import defaultdict
from django.urls import reverse
from django.db.models import Prefetch
from decimal import Decimal
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
import random
from django.views.decorators.csrf import csrf_exempt
from django.db import connection
import os
from django.core.files.storage import FileSystemStorage
import logging
import traceback
import string
from django.core.mail import send_mail
from django.contrib.auth import update_session_auth_hash

logger = logging.getLogger(__name__)

# Create your views here.
@login_required
def dashboard_view(request):
    try:
        # Get active school year and all school years for filtering
        active_school_year = SchoolYear.get_active()
        print(f"Active school year: {active_school_year}")
        school_years = SchoolYear.objects.all().order_by('-year_start')
        selected_year = request.GET.get('school_year', active_school_year.display_name if active_school_year else None)
        print(f"Selected year: {selected_year}")

        # Initialize context with school year data
        context = {
            'active_school_year': active_school_year,
            'school_years': school_years,
            'selected_year': selected_year
        }

        # Get enrollment statistics
        enrollment_stats = {
            'total': 0,
            'by_grade': {},
            'by_gender': {'Male': 0, 'Female': 0},
            'by_status': {'Active': 0, 'Dropped': 0, 'Transferred': 0, 'Completed': 0}
        }

        # Define enrollment models for each grade
        enrollment_models = {
            7: Enrollment,
            8: Grade8Enrollment,
            9: Grade9Enrollment,
            10: Grade10Enrollment,
            11: Grade11Enrollment,
            12: Grade12Enrollment
        }

        # Calculate enrollment statistics
        for grade, model in enrollment_models.items():
            grade_enrollments = model.objects.filter(
                school_year=selected_year
            ).select_related('student')
            print(f"Grade {grade} enrollments: {grade_enrollments.count()}")

            grade_count = grade_enrollments.count()
            enrollment_stats['total'] += grade_count
            enrollment_stats['by_grade'][f'Grade {grade}'] = grade_count

            # Update gender statistics
            for enrollment in grade_enrollments:
                enrollment_stats['by_gender'][enrollment.student.gender] += 1
                enrollment_stats['by_status'][enrollment.status] += 1

        print(f"Total enrollments: {enrollment_stats['total']}")

        # Calculate student growth (comparing to last month)
        last_month = datetime.now() - timedelta(days=30)
        students_last_month = sum(
            model.objects.filter(
                school_year=selected_year,
                enrollment_date__lt=last_month
            ).count()
            for model in enrollment_models.values()
        )

        current_total = enrollment_stats['total']
        if students_last_month > 0:
            student_growth = ((current_total - students_last_month) / students_last_month) * 100
        else:
            student_growth = 0

        # Get teacher statistics
        teacher_stats = {
            'total': Teachers.objects.count(),
            'by_gender': {
                'Male': Teachers.objects.filter(gender='Male').count(),
                'Female': Teachers.objects.filter(gender='Female').count()
            }
        }
        print(f"Total teachers: {teacher_stats['total']}")

        # Get section statistics
        section_stats = {
            'total': Sections.objects.count(),
            'by_grade': {
                grade: Sections.objects.filter(grade_level=grade).count()
                for grade in range(7, 13)
            }
        }
        print(f"Total sections: {section_stats['total']}")

        # Prepare chart data
        gender_data = {
            'labels': ['Male', 'Female'],
            'data': [
                enrollment_stats['by_gender']['Male'],
                enrollment_stats['by_gender']['Female']
            ]
        }

        grade_level_data = {
            'labels': list(enrollment_stats['by_grade'].keys()),
            'data': list(enrollment_stats['by_grade'].values())
        }

        # Get monthly enrollment trends
        monthly_data = defaultdict(lambda: [0] * 12)
        for model in enrollment_models.values():
            enrollments = (
                model.objects
                .filter(school_year=selected_year)
                .annotate(month=ExtractMonth('enrollment_date'))
                .values('month')
                .annotate(count=Count('id'))
            )
            for item in enrollments:
                monthly_data['enrollments'][item['month'] - 1] = item['count']

        enrollment_trends = {
            'labels': ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
            'datasets': [{
                'label': 'Monthly Enrollments',
                'data': monthly_data['enrollments']
            }]
        }

        # Get latest announcements (last 5)
        recent_announcements = Announcement.objects.all().order_by('-created_at')[:5]

        # Get upcoming events (next 7 days)
        today = timezone.now().date()
        upcoming_events = Event.objects.filter(
            start_date__gte=today
        ).order_by('start_date', 'start_time')[:5]

        # Update context with all statistics
        context.update({
            'enrollment_stats': enrollment_stats,
            'teacher_stats': teacher_stats,
            'section_stats': section_stats,
            'student_growth': round(student_growth, 1),
            'gender_data': json.dumps(gender_data),
            'grade_level_data': json.dumps(grade_level_data),
            'enrollment_trends': json.dumps(enrollment_trends),
            'recent_announcements': recent_announcements,
            'upcoming_events': upcoming_events,
            'total_students': enrollment_stats['total'],
            'total_teachers': teacher_stats['total'],
            'total_sections': section_stats['total'],
        })

        print(f"Context data: {context}")
        return render(request, 'main.html', context)
    except Exception as e:
        print(f"Error in dashboard_view: {str(e)}")
        messages.error(request, f"Error loading dashboard: {str(e)}")
        return render(request, 'main.html', {'error_message': str(e)})

@login_required
def teachers_view(request):
    try:
        teachers = Teachers.objects.all()
        context = {
            'teachers': teachers
        }
        return render(request, 'teachers.html', context)
    except Exception as e:
        messages.error(request, f"Error loading teachers: {str(e)}")
        return render(request, 'teachers.html', {
            'teachers': [],
            'error': str(e)
        })

@login_required
def students_view(request):
    try:
        school_years = SchoolYear.objects.all().order_by('-year_start')
        active_school_year = SchoolYear.get_active()
        selected_year = request.GET.get('school_year', active_school_year.display_name if active_school_year else None)
        status_filter = request.GET.get('status', None)
        
        students = Student.objects.all()
        # Exclude students who have completed Grade 12
        graduated_ids = set(
            Grade12Enrollment.objects.filter(status='Completed').values_list('student_id', flat=True)
        )
        students = students.exclude(id__in=graduated_ids)

        # Build a status dictionary for each student for the selected year
        enrollment_models = {
            7: Enrollment,
            8: Grade8Enrollment,
            9: Grade9Enrollment,
            10: Grade10Enrollment,
            11: Grade11Enrollment,
            12: Grade12Enrollment
        }
        student_statuses = {}
        for student in students:
            found = False
            # Check for enrollment in the selected year, from highest to lowest grade
            for grade in range(12, 6, -1):
                model = enrollment_models[grade]
                if selected_year:
                    enrollment = model.objects.filter(student=student, school_year=selected_year).first()
                else:
                    enrollment = model.objects.filter(student=student).order_by('-school_year').first()
                if enrollment:
                    student_statuses[student.id] = enrollment.status
                    found = True
                    break
            if not found:
                student_statuses[student.id] = 'Not Enrolled'

        # Optionally filter by status if requested
        if status_filter == 'not_enrolled':
            students = [s for s in students if student_statuses.get(s.id) == 'Not Enrolled']

        grade7_sections = Sections.objects.filter(grade_level=7)

        sections = Sections.objects.all().order_by('grade_level', 'section_id')
        sections_by_grade = defaultdict(list)
        for section in sections:
            sections_by_grade[section.grade_level].append(section)

        context = {
            'students': students,
            'school_years': school_years,
            'active_school_year': active_school_year,
            'selected_year': selected_year,
            'status_filter': status_filter,
            'student_statuses': student_statuses,
            'grade7_sections': grade7_sections,
            'sections_by_grade': dict(sections_by_grade),
        }
        return render(request, 'students.html', context)
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        messages.error(request, f'Error loading students: {str(e)}')
        return render(request, 'students.html', {
            'students': [],
            'school_years': [],
            'active_school_year': None,
            'selected_year': None,
            'status_filter': None,
            'student_statuses': {},
        })

@login_required
def add_student(request):
    if request.method == 'POST':
        try:
            # Get active school year
            active_school_year = SchoolYear.get_active()
            if not active_school_year:
                messages.error(request, 'No active school year found. Please set an active school year first.')
                return redirect('dashboard:students')

            # Log the POST data for debugging
            logger.info(f"POST data: {request.POST}")
            logger.info(f"FILES data: {request.FILES}")

            # Validate required fields
            required_fields = ['student_id', 'first_name', 'last_name', 'gender', 'religion', 
                             'date_of_birth', 'email', 'mobile_number', 'address', 'student_status']
            
            missing_fields = [field for field in required_fields if not request.POST.get(field)]
            if missing_fields:
                raise ValidationError(f"Missing required fields: {', '.join(missing_fields)}")

            # Check if student ID already exists
            if Student.objects.filter(student_id=request.POST['student_id']).exists():
                raise ValidationError(f"Student ID {request.POST['student_id']} already exists")

            # Check if email already exists
            if Student.objects.filter(email=request.POST['email']).exists():
                raise ValidationError(f"Email {request.POST['email']} already exists")

            # Generate unique username
            student_id = request.POST['student_id']
            base_username = f"student_{student_id}"
            username = base_username
            counter = 1
            
            # Keep trying until we find a unique username
            while User.objects.filter(username=username).exists():
                username = f"{base_username}_{counter}"
                counter += 1

            # Generate default password
            default_password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
            
            # Create User instance first
            user = User.objects.create_user(
                username=username,
                password=default_password,
                email=request.POST['email'],
                first_name=request.POST['first_name'],
                last_name=request.POST['last_name']
            )
            
            # Handle photo upload
            student_photo = request.FILES.get('student_photo')

            # Handle suffix
            suffix = request.POST.get('suffix')
            if suffix == 'Other':
                suffix = request.POST.get('custom_suffix')

            # Create Student instance
            student = Student.objects.create(
                user=user,
                student_id=student_id,
                username=username,  # Use the same unique username
                password=default_password,
                first_name=request.POST['first_name'],
                middle_name=request.POST.get('middle_name'),
                last_name=request.POST['last_name'],
                suffix=suffix,
                gender=request.POST['gender'],
                religion=request.POST['religion'],
                date_of_birth=request.POST['date_of_birth'],
                email=request.POST['email'],
                mobile_number=request.POST['mobile_number'],
                address=request.POST['address'],
                student_photo=student_photo,
                school_year=active_school_year.display_name,
                student_status=request.POST.get('student_status', 'New Student'),
                force_password_change=True
            )

            # ENROLLMENT LOGIC STARTS HERE
            section_id = request.POST.get('enrollment_section')
            if section_id:
                try:
                    section = Sections.objects.get(id=section_id)
                    grade_level = section.grade_level

                    EnrollmentModel = get_enrollment_model(grade_level)

                    if grade_level in [11, 12]:
                        track = request.POST.get('track')
                        if not track:
                            raise ValidationError("Track is required for Grades 11 and 12")
                        
                        enrollment = EnrollmentModel.objects.create(
                            student=student,
                            section=section,
                            school_year=active_school_year.display_name,
                            track=track
                        )
                    else:
                        enrollment = EnrollmentModel.objects.create(
                            student=student,
                            section=section,
                            school_year=active_school_year.display_name
                        )
                except Sections.DoesNotExist:
                    raise ValidationError(f"Section with ID {section_id} does not exist")
                except Exception as e:
                    raise ValidationError(f"Error creating enrollment: {str(e)}")

            # Send email with credentials
            subject = 'Your Student Portal Login Credentials'
            message = f"""
            Hello {student.first_name} {student.last_name},

            Your student portal account has been created. Here are your login credentials:

            Username: {username}
            Password: {default_password}

            For security reasons, you will be required to change your password upon first login.

            Best regards,
            School Administration
            """
            
            try:
                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [student.email],
                    fail_silently=False,
                )
            except Exception as e:
                logger.error(f"Failed to send email to {student.email}: {str(e)}")
                messages.warning(request, f"Student created but failed to send email: {str(e)}")

            messages.success(request, f'Student {student.first_name} {student.last_name} added successfully!')
            return redirect('dashboard:students')

        except ValidationError as e:
            messages.error(request, str(e))
            return redirect('dashboard:students')
        except Exception as e:
            logger.error(f"Error in add_student: {str(e)}")
            messages.error(request, f'Error adding student: {str(e)}')
            return redirect('dashboard:students')
    return redirect('dashboard:students')

@login_required
def upload_students_excel(request):
    """Handle bulk student upload via Excel file"""
    if request.method == 'POST':
        try:
            # Get active school year
            active_school_year = SchoolYear.get_active()
            if not active_school_year:
                messages.error(request, 'No active school year found. Please set an active school year first.')
                return redirect('dashboard:students')

            # Check if file was uploaded
            if 'excel_file' not in request.FILES:
                messages.error(request, 'No file uploaded')
                return redirect('dashboard:students')

            excel_file = request.FILES['excel_file']
            
            # Validate file extension
            if not excel_file.name.endswith(('.xls', '.xlsx')):
                messages.error(request, 'Invalid file format. Please upload an Excel file (.xls or .xlsx)')
                return redirect('dashboard:students')

            # Read Excel file
            df = pd.read_excel(excel_file)
            
            # Required columns
            required_columns = [
                'student_id', 'first_name', 'last_name', 'gender', 
                'email', 'date_of_birth', 'mobile_number', 'address'
            ]
            
            # Validate columns
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                messages.error(request, f'Missing required columns: {", ".join(missing_columns)}')
                return redirect('dashboard:students')

            # Track success and failures
            success_count = 0
            error_count = 0
            errors = []

            # Process each row
            for index, row in df.iterrows():
                try:
                    # Check if student ID already exists
                    if Student.objects.filter(student_id=row['student_id']).exists():
                        errors.append(f"Row {index + 2}: Student ID {row['student_id']} already exists")
                        error_count += 1
                        continue

                    # Generate default username and password
                    default_username = f"student_{row['student_id']}"
                    default_password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))

                    # Create User instance
                    user = User.objects.create_user(
                        username=default_username,
                        password=default_password,
                        email=row['email'],
                        first_name=row['first_name'],
                        last_name=row['last_name']
                    )

                    # Create Student instance
                    student = Student.objects.create(
                        user=user,
                        student_id=row['student_id'],
                        username=default_username,
                        password=default_password,
                        first_name=row['first_name'],
                        middle_name=row.get('middle_name', ''),
                        last_name=row['last_name'],
                        gender=row['gender'],
                        religion=row.get('religion', ''),
                        date_of_birth=row['date_of_birth'],
                        email=row['email'],
                        mobile_number=row['mobile_number'],
                        address=row['address'],
                        school_year=active_school_year.display_name,
                        force_password_change=True
                    )

                    # Handle enrollment if section is provided
                    if 'section_id' in row and pd.notna(row['section_id']):
                        try:
                            section = Sections.objects.get(id=row['section_id'])
                            grade_level = section.grade_level
                            EnrollmentModel = get_enrollment_model(grade_level)

                            if grade_level in [11, 12]:
                                track = row.get('track')
                                if not track:
                                    raise ValidationError("Track is required for Grades 11 and 12")
                                
                                enrollment = EnrollmentModel.objects.create(
                                    student=student,
                                    section=section,
                                    school_year=active_school_year.display_name,
                                    track=track
                                )
                            else:
                                enrollment = EnrollmentModel.objects.create(
                                    student=student,
                                    section=section,
                                    school_year=active_school_year.display_name
                                )
                        except Sections.DoesNotExist:
                            errors.append(f"Row {index + 2}: Section ID {row['section_id']} not found")
                            error_count += 1
                            continue

                    # Send email with credentials
                    try:
                        subject = 'Your Student Portal Login Credentials'
                        message = f"""
                        Hello {student.first_name} {student.last_name},

                        Your student portal account has been created. Here are your login credentials:

                        Username: {default_username}
                        Password: {default_password}

                        For security reasons, you will be required to change your password upon first login.

                        Best regards,
                        School Administration
                        """
                        
                        send_mail(
                            subject,
                            message,
                            settings.DEFAULT_FROM_EMAIL,
                            [student.email],
                            fail_silently=False,
                        )
                    except Exception as e:
                        logger.error(f"Failed to send email to {student.email}: {str(e)}")
                        errors.append(f"Row {index + 2}: Failed to send email to {student.email}")

                    success_count += 1

                except Exception as e:
                    errors.append(f"Row {index + 2}: {str(e)}")
                    error_count += 1
                    if 'user' in locals():
                        user.delete()

            # Log the activity
            log_admin_activity(
                request.user,
                f"Uploaded {success_count} students via Excel",
                "student"
            )

            # Prepare success/error messages
            if success_count > 0:
                messages.success(request, f'Successfully added {success_count} students')
            if error_count > 0:
                messages.error(request, f'Failed to add {error_count} students. See details below.')
                for error in errors:
                    messages.error(request, error)

            return redirect('dashboard:students')

        except Exception as e:
            messages.error(request, f'Error processing Excel file: {str(e)}')
            return redirect('dashboard:students')

    return redirect('dashboard:students')

@login_required
def add_teacher(request):
    if request.method == 'POST':
        try:
            # Get form data
            teacher_id = request.POST.get('teacher_id')
            first_name = request.POST.get('first_name')
            middle_name = request.POST.get('middle_name')
            last_name = request.POST.get('last_name')
            email = request.POST.get('email')
            mobile_number = request.POST.get('mobile_number')
            address = request.POST.get('address')
            date_of_birth = request.POST.get('date_of_birth')
            gender = request.POST.get('gender')
            religion = request.POST.get('religion')
            
            # Create unique username
            base_username = f"{first_name.lower()}.{last_name.lower()}"
            username = base_username
            counter = 1
            
            # Keep trying until we find a unique username
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1
            
            # Generate random password
            password = User.objects.make_random_password()
            
            # Create user account
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )
            
            # Create teacher profile
            teacher = Teachers.objects.create(
                user=user,
                teacher_id=teacher_id,
                username=username,
                password=user.password,
                first_name=first_name,
                middle_name=middle_name,
                last_name=last_name,
                gender=gender,
                religion=religion,
                date_of_birth=date_of_birth,
                email=email,
                mobile_number=mobile_number,
                address=address,
                class_sched=''  # Default empty string
            )
            
            # Handle photo upload if provided
            if 'teacher_photo' in request.FILES:
                teacher.teacher_photo = request.FILES['teacher_photo']
                teacher.save()
            
            messages.success(request, f'Successfully added teacher: {first_name} {last_name}')
            return redirect('dashboard:teachers')
            
        except Exception as e:
            messages.error(request, f'Error adding teacher: {str(e)}')
            return redirect('dashboard:teachers')
            
    return redirect('dashboard:teachers')

@login_required
def edit_teacher(request):
    if request.method == 'POST':
        try:
            teacher_id = request.POST.get('teacher_id')
            name_parts = request.POST.get('name', '').split()
            gender = request.POST.get('gender')
            email = request.POST.get('email')
            mobile_number = request.POST.get('mobile_number')
            
            # Get the teacher object
            teacher = Teachers.objects.get(teacher_id=teacher_id)
            
            # Update teacher information
            if len(name_parts) >= 2:
                teacher.first_name = name_parts[0]
                teacher.last_name = name_parts[-1]
                # If there are middle names
                if len(name_parts) > 2:
                    teacher.middle_name = ' '.join(name_parts[1:-1])
                else:
                    teacher.middle_name = ''
            
            teacher.gender = gender
            teacher.email = email
            teacher.mobile_number = mobile_number
            teacher.save()
            
            log_admin_activity(
                request.user,
                f"Updated teacher information: {teacher.first_name} {teacher.last_name} ({teacher.teacher_id})",
                "teacher"
            )
            messages.success(request, 'Teacher updated successfully!')
            
        except Teachers.DoesNotExist:
            messages.error(request, 'Teacher not found!')
        except Exception as e:
            messages.error(request, f'Error updating teacher: {str(e)}')
    
    return redirect('dashboard:teachers')

@login_required
def add_subject(request):
    if request.method == 'POST':
        subject_id = request.POST.get('subject_id')
        subject_name = request.POST.get('subject_name')
        try:
            if Subject.objects.filter(subject_id=subject_id).exists():
                msg = 'Subject ID already exists!'
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'message': msg})
                messages.error(request, msg)
            elif Subject.objects.filter(name=subject_name).exists():
                msg = 'Subject name already exists!'
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'message': msg})
                messages.error(request, msg)
            else:
                Subject.objects.create(subject_id=subject_id, name=subject_name)
                msg = 'Subject added successfully!'
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({'success': True, 'message': msg})
                messages.success(request, msg)
        except Exception as e:
            msg = f'Error adding subject: {str(e)}'
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': msg})
            messages.error(request, msg)
        return redirect('dashboard:subjects')
    else:
        return redirect('dashboard:subjects')

@login_required
def sections_view(request):
    try:
        # Get all sections with their advisers
        sections = Sections.objects.select_related('adviser').all().order_by('grade_level', 'section_id')
        
        # Get all teachers for adviser selection
        teachers = Teachers.objects.all().order_by('last_name', 'first_name')
        
        # Get enrollment counts for each section
        section_stats = {}
        for section in sections:
            enrollment_model = get_enrollment_model(section.grade_level)
            if enrollment_model:
                count = enrollment_model.objects.filter(section=section, status='Active').count()
                section_stats[section.id] = count

        # Adviser assignments mapping for frontend JS restriction
        adviser_assignments = {str(section.adviser.id): section.section_id for section in sections if section.adviser}

        context = {
            'sections': sections,
            'teachers': teachers,
            'available_teachers': teachers,
            'section_stats': section_stats,
            'grade_levels': range(7, 13),  # Grades 7-12
            'adviser_assignments': adviser_assignments
        }
        
        return render(request, 'Sections.html', context)
    except Exception as e:
        messages.error(request, f'Error loading sections: {str(e)}')
        # Instead of redirecting, render the template with minimal context
        return render(request, 'Sections.html', {
            'sections': [],
            'teachers': [],
            'available_teachers': [],
            'section_stats': {},
            'grade_levels': range(7, 13)
        })

def add_section(request):
    if request.method == 'POST':
        section_id = request.POST.get('section_id')
        grade_level = request.POST.get('grade_level')
        adviser_id = request.POST.get('adviser')

        # Convert grade_level to int right away
        try:
            grade_level = int(grade_level)
        except (TypeError, ValueError):
            from django.contrib import messages
            messages.error(request, 'Invalid grade level.')
            return redirect('dashboard:sections')

        # Check for adviser duplication (across all grade levels)
        adviser_sections = Sections.objects.filter(adviser_id=adviser_id)
        if adviser_sections.exists():
            from django.shortcuts import render
            context = {
                'adviser_duplication_error': 'This teacher is already an adviser for another section!'
            }
            return render(request, 'Sections.html', context)

        # Validate required fields
        if not section_id or not grade_level or not adviser_id:
            from django.contrib import messages
            messages.error(request, 'All fields are required.')
            return redirect('dashboard:sections')

        try:
            adviser = Teachers.objects.get(id=adviser_id)
        except Teachers.DoesNotExist:
            from django.contrib import messages
            messages.error(request, 'Adviser not found!')
            return redirect('dashboard:sections')

        # Check for duplicate section_id
        if Sections.objects.filter(section_id=section_id).exists():
            from django.contrib import messages
            messages.error(request, f'Section ID {section_id} already exists.')
            return redirect('dashboard:sections')

        section = Sections.objects.create(
            section_id=section_id,
            grade_level=grade_level,
            adviser=adviser
        )  
        from django.contrib import messages
        messages.success(request, f'Section {section_id} created successfully!')
        log_admin_activity(
            request.user,
            f"Created section: {section.section_id} (Grade {section.grade_level})",
            "section"
        )
        return redirect('dashboard:sections')
    return redirect('dashboard:sections')

@login_required
def edit_subject(request):
    if request.method == 'POST':
        try:
            subject_id = request.POST.get('subject_id')
            new_subject_id = request.POST.get('new_subject_id')
            new_name = request.POST.get('new_name')
            
            # Get the subject
            subject = Subject.objects.get(subject_id=subject_id)
            
            # Check if new subject ID already exists (if it's different from current)
            if new_subject_id != subject_id and Subject.objects.filter(subject_id=new_subject_id).exists():
                return JsonResponse({'success': False, 'message': 'Subject ID already exists!'})
            
            # Check if new name already exists (if it's different from current)
            if new_name != subject.name and Subject.objects.filter(name=new_name).exists():
                return JsonResponse({'success': False, 'message': 'Subject name already exists!'})
            
            # Update the subject
            subject.subject_id = new_subject_id
            subject.name = new_name
            subject.save()
            
            return JsonResponse({
                'success': True, 
                'message': 'Subject updated successfully!',
                'subject': {
                    'subject_id': subject.subject_id,
                    'name': subject.name
                }
            })
            
        except Subject.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Subject not found!'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})

@login_required
def delete_subject(request):
    """API endpoint to delete a subject"""
    if request.method == 'POST':
        try:
            subject_id = request.POST.get('subject_id')
            
            if not subject_id:
                return JsonResponse({
                    'success': False,
                    'message': 'Subject ID is required'
                }, status=400)
            
            # Get the subject
            try:
                subject = Subject.objects.get(subject_id=subject_id)
            except Subject.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': 'Subject not found'
                }, status=404)
            
            # Check if subject is being used in any schedules
            if Schedules.objects.filter(subject=subject).exists():
                return JsonResponse({
                    'success': False,
                    'message': f'Cannot delete subject {subject.name} because it is being used in schedules'
                }, status=400)
            
            # Check if subject is being used in any grades
            if Grades.objects.filter(subject=subject).exists():
                return JsonResponse({
                    'success': False,
                    'message': f'Cannot delete subject {subject.name} because it has associated grades'
                }, status=400)
            
            # Store subject info for logging
            subject_name = subject.name
            
            # Delete the subject
            subject.delete()
            
            # Log the activity
            log_admin_activity(
                request.user,
                f"Deleted subject: {subject_name}",
                "subject"
            )
            
            return JsonResponse({
                'success': True,
                'message': f'Successfully deleted subject {subject_name}'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            }, status=500)
    
    return JsonResponse({
        'success': False,
        'message': 'Invalid request method'
    }, status=405)

    
def edit_section(request, pk=None):
    if request.method == 'POST':
        try:
            section_id = request.POST.get('section_id')
            grade_level = request.POST.get('grade_level')
            adviser_id = request.POST.get('adviser')
            
            # Get the section
            section = Sections.objects.get(id=pk)
            
            # Update section information
            section.section_id = section_id
            section.grade_level = grade_level
            section.adviser = Teachers.objects.get(id=adviser_id)
            section.save()
            
            messages.success(request, f'Section {section_id} updated successfully!')
            log_admin_activity(
                request.user,
                f"Updated section: {section.section_id} (Grade {section.grade_level})",
                "section"
            )
            return redirect('dashboard:sections')
        except Sections.DoesNotExist:
            messages.error(request, 'Section not found!')
            return redirect('dashboard:sections')
        except Teachers.DoesNotExist:
            messages.error(request, 'Adviser not found!')
            return redirect('dashboard:sections')
        except Exception as e:
            messages.error(request, f'Error editing section: {str(e)}')
            return redirect('dashboard:sections')
    return redirect('dashboard:sections')

def delete_section(request, pk=None):
    if request.method == 'POST':
        try:
            # Get the section
            section = Sections.objects.get(id=pk)
            section_id = section.section_id
            
            # Delete the section
            section.delete()
            
            messages.success(request, f'Section {section_id} deleted successfully!')
            log_admin_activity(
                request.user,
                f"Deleted section: {section_id}",
                "section"
            )
            return redirect('dashboard:sections')
        except Sections.DoesNotExist:
            messages.error(request, 'Section not found!')
            return redirect('dashboard:sections')
        except Exception as e:
            messages.error(request, f'Error deleting section: {str(e)}')
            return redirect('dashboard:sections')
    return redirect('dashboard:sections')

def get_enrollment_model(grade_level):
    """Get the appropriate enrollment model based on grade level"""
    enrollment_models = {
        7: Enrollment,
        8: Grade8Enrollment,
        9: Grade9Enrollment,
        10: Grade10Enrollment,
        11: Grade11Enrollment,
        12: Grade12Enrollment
    }
    return enrollment_models.get(grade_level)

@login_required
def enrollment_view(request):
    try:
        # Get active school year
        active_school_year = SchoolYear.get_active()
        school_years = SchoolYear.objects.all().order_by('-year_start')
        sections = Sections.objects.all().order_by('grade_level', 'section_id')
        students = Student.objects.all().order_by('student_id')

        # Get enrollments for active school year only
        enrollments = []
        enrollment_models = {
            7: Enrollment,
            8: Grade8Enrollment,
            9: Grade9Enrollment,
            10: Grade10Enrollment,
            11: Grade11Enrollment,
            12: Grade12Enrollment
        }

        if active_school_year:
            for grade, model in enrollment_models.items():
                grade_enrollments = model.objects.filter(
                    school_year=active_school_year.display_name
                ).select_related('student', 'section')
                enrollments.extend(grade_enrollments)
        
        # Calculate enrollment statistics for active school year
        enrollment_stats = {
            'total': len(enrollments),
            'by_grade': {},
            'by_status': {'Active': 0, 'Dropped': 0, 'Transferred': 0, 'Completed': 0}
        }
        
        if active_school_year:
            for grade, model in enrollment_models.items():
                grade_count = model.objects.filter(
                    school_year=active_school_year.display_name
                ).count()
                enrollment_stats['by_grade'][f'Grade {grade}'] = grade_count
                for status in ['Active', 'Dropped', 'Transferred', 'Completed']:
                    status_count = model.objects.filter(
                        status=status,
                        school_year=active_school_year.display_name
                    ).count()
                    enrollment_stats['by_status'][status] += status_count
        
        # Build sections_by_grade for grade cards
        sections_by_grade = {}
        for section in sections:
            grade = section.grade_level
            if grade not in sections_by_grade:
                sections_by_grade[grade] = []

            # Get the correct enrollment model for this section's grade
            enrollment_model = get_enrollment_model(grade)
            if enrollment_model and active_school_year:
                enrolled_students = enrollment_model.objects.filter(
                    section=section,
                    school_year=active_school_year.display_name
                ).select_related('student')
                count = enrolled_students.count()
                students_list = [
                    {
                        'student_id': e.student.student_id,
                        'name': f"{e.student.first_name} {e.student.last_name}",
                        'section': section.section_id,
                        'grade_level': f"Grade {grade}",
                        'school_year': e.school_year,
                        'status': e.status,
                        'enrollment_id': e.id
                    }
                    for e in enrolled_students
                ]
            else:
                count = 0
                students_list = []

            sections_by_grade[grade].append({
                'section': section,
                'count': count,
                'students': students_list
            })
        
        # Get available students (not enrolled in active school year)
        if active_school_year:
            enrolled_student_ids = [e.student.id for e in enrollments]
            available_students = students.exclude(id__in=enrolled_student_ids)
        else:
            available_students = students

        context = {
            'active_school_year': active_school_year,
            'school_years': school_years,
            'sections': sections,
            'students': students,
            'enrollments': enrollments,
            'enrollment_stats': enrollment_stats,
            'available_students': available_students,
            'all_students': students,
            'sections_by_grade': sections_by_grade,
        }
        return render(request, 'enrollment.html', context)
    except Exception as e:
        messages.error(request, f'Error loading enrollment view: {str(e)}')
        # Instead of redirecting, render the template with minimal context
        return render(request, 'enrollment.html', {
            'active_school_year': None,
            'school_years': [],
            'sections': [],
            'students': [],
            'enrollments': [],
            'enrollment_stats': {
                'total': 0,
                'by_grade': {},
                'by_status': {'Active': 0, 'Dropped': 0, 'Transferred': 0, 'Completed': 0}
            },
            'available_students': [],
            'all_students': [],
            'sections_by_grade': {}
        })

def add_enrollment(request):
    if request.method == 'POST':
        try:
            student_id = request.POST.get('student')
            section_id = request.POST.get('section')
            school_year = request.POST.get('school_year')
            track = request.POST.get('track', None)  # Optional for senior high

            # Get the student and section
            student = Student.objects.get(id=student_id)
            section = Sections.objects.get(id=section_id)

            # Check if student is already enrolled in this grade level for this school year
            existing_enrollment = Enrollment.objects.filter(
                student=student,
                section__grade_level=section.grade_level,
                school_year=school_year
            ).first()

            if existing_enrollment:
                messages.error(request, f'⚠️ {student.first_name} {student.last_name} is already enrolled in Grade {section.grade_level} for {school_year}')
                return redirect('dashboard:enrollment')

            # Check if student is already enrolled in a different grade level for this school year
            other_grade_enrollment = Enrollment.objects.filter(
                student=student,
                school_year=school_year
            ).exclude(section__grade_level=section.grade_level).first()

            if other_grade_enrollment:
                messages.error(request, f'⚠️ {student.first_name} {student.last_name} is already enrolled in Grade {other_grade_enrollment.section.grade_level} for {school_year}')
                return redirect('dashboard:enrollment')

            # Check if student has already completed or been enrolled in this grade level in any previous school year
            previous_enrollments = Enrollment.objects.filter(
                student=student,
                section__grade_level=section.grade_level
            ).exclude(school_year=school_year).order_by('-school_year')

            if previous_enrollments.exists():
                last_enrollment = previous_enrollments.first()
                if last_enrollment.status in ['Completed', 'Active']:
                    messages.error(request, f'⚠️ {student.first_name} {student.last_name} has already completed Grade {section.grade_level} in {last_enrollment.school_year}')
                    return redirect('dashboard:enrollment')

            # Create the enrollment
            enrollment = Enrollment.objects.create(
                student=student,
                section=section,
                school_year=school_year,
                status='Active'
            )

            # If senior high, add track
            if section.grade_level in [11, 12] and track:
                enrollment.track = track
                enrollment.save()

            messages.success(request, f'✅ {student.first_name} {student.last_name} has been successfully enrolled in {section.section_id} for {school_year}!')
            log_admin_activity(
                request.user,
                f"Enrolled student: {student.first_name} {student.last_name} in {section.section_id}",
                "enrollment"
            )
            return redirect('dashboard:enrollment')
        except Student.DoesNotExist:
            messages.error(request, '⚠️ Student not found!')
            return redirect('dashboard:enrollment')
        except Sections.DoesNotExist:
            messages.error(request, '⚠️ Section not found!')
            return redirect('dashboard:enrollment')
        except Exception as e:
            messages.error(request, f'⚠️ Error enrolling student: {str(e)}')
            return redirect('dashboard:enrollment')
    
    return redirect('dashboard:enrollment')

def edit_enrollment(request):
    if request.method == 'POST':
        try:
            enrollment_id = request.POST.get('enrollment_id')
            new_status = request.POST.get('status')
            
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
    
    return redirect('dashboard:enrollment')

def delete_enrollment(request):
    if request.method == 'POST':
        try:
            school_year = request.POST.get('school_year')
            archive_type = request.POST.get('archive_type')
            
            if not school_year or not archive_type:
                messages.error(request, 'School year and archive type are required')
                return redirect('administrator:archive_view')
            
            # Check if archive already exists for this type and year
            existing_archive = Archive.objects.filter(
                archive_type=archive_type,
                school_year=school_year
            ).first()
            
            if existing_archive:
                messages.warning(request, f'An archive for {archive_type} data in {school_year} already exists')
                return redirect('administrator:archive_view')
            
            # Get data based on archive type
            data = []
            try:
                if archive_type == 'student':
                    data = list(Student.objects.filter(school_year=school_year).values())
                elif archive_type == 'teacher':
                    data = list(Teachers.objects.all().values())
                elif archive_type == 'enrollment':
                    data = list(Enrollment.objects.filter(school_year=school_year).values())
                elif archive_type == 'grade':
                    data = list(Grades.objects.filter(school_year=school_year).values())
                elif archive_type == 'section':
                    data = list(Sections.objects.all().values())
                elif archive_type == 'schedule':
                    data = list(Schedules.objects.all().values())
                elif archive_type == 'event':
                    data = list(Event.objects.all().values())
                else:
                    messages.error(request, 'Invalid archive type')
                    return redirect('administrator:archive_view')
            except Exception as e:
                messages.error(request, f'Error fetching data: {str(e)}')
                return redirect('administrator:archive_view')
            
            if not data:
                messages.warning(request, f'No {archive_type} data found for {school_year}')
                return redirect('administrator:archive_view')
            
            # Create archive record with transaction to ensure data integrity
            try:
                with transaction.atomic():
                    archive = Archive.objects.create(
                        archive_type=archive_type,
                        school_year=school_year,
                        data=data,
                        created_by=request.user
                    )
                    
                    # Log the archive creation
                    log_admin_activity(
                        user=request.user,
                        action=f'Created {archive_type} archive for {school_year}',
                        action_type='archive'
                    )
                
                messages.success(request, f'Successfully archived {len(data)} {archive_type} records for {school_year}')
                return redirect('administrator:archive_view')
                
            except Exception as e:
                messages.error(request, f'Error creating archive: {str(e)}')
                return redirect('administrator:archive_view')
            
        except Exception as e:
            messages.error(request, f'Error archiving data: {str(e)}')
            return redirect('administrator:archive_view')
    
    return redirect('administrator:archive_view')

@login_required
def archive_view(request):
    try:
        archives = Archive.objects.all()
        context = {
            'archives': archives
        }
        return render(request, 'archive.html', context)
    except Exception as e:
        messages.error(request, f"Error loading archives: {str(e)}")
        return redirect('dashboard:archive_view')

@login_required
def view_archive_detail(request, archive_id):
    """View detailed data of a specific archive"""
    try:
        archive = Archive.objects.get(id=archive_id)
        
        # Format the data for display
        formatted_data = []
        for item in archive.data:
            formatted_item = {}
            for key, value in item.items():
                # Format datetime fields
                if isinstance(value, str) and value.endswith('Z'):
                    try:
                        value = datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ')
                        value = value.strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        pass
                formatted_item[key] = value
            formatted_data.append(formatted_item)
        
        context = {
            'archive': archive,
            'data': formatted_data
        }
        
        return render(request, 'archive_detail.html', context)
        
    except Archive.DoesNotExist:
        messages.error(request, 'Archive not found')
        return redirect('dashboard:archive_view')
    except Exception as e:
        messages.error(request, f'Error viewing archive details: {str(e)}')
        return redirect('dashboard:archive_view')

@login_required
def save_archive(request):
    """Save archive data to the database"""
    if request.method == 'POST':
        try:
            # Get form data
            school_year = request.POST.get('school_year')
            archive_type = request.POST.get('archive_type')
            
            # Validate required fields
            if not school_year or not archive_type:
                messages.error(request, 'School year and archive type are required')
                return JsonResponse({'status': 'error', 'message': 'School year and archive type are required'})
            
            # Check if archive already exists
            existing_archive = Archive.objects.filter(
                archive_type=archive_type,
                school_year=school_year
            ).first()
            
            if existing_archive:
                messages.warning(request, f'An archive for {archive_type} data in {school_year} already exists')
                return JsonResponse({'status': 'warning', 'message': f'An archive for {archive_type} data in {school_year} already exists'})
            
            # Get data based on archive type
            data = []
            try:
                if archive_type == 'student':
                    data = list(Student.objects.filter(school_year=school_year).values())
                elif archive_type == 'teacher':
                    data = list(Teachers.objects.all().values())
                elif archive_type == 'enrollment':
                    data = list(Enrollment.objects.filter(school_year=school_year).values())
                elif archive_type == 'grade':
                    # Handle grade data differently
                    grades = Grades.objects.select_related('student', 'subject', 'section').all()
                    data = []
                    for grade in grades:
                        # Only include grades for the specified school year
                        if grade.school_year == school_year:
                            grade_data = {
                                'id': grade.id,
                                'student_id': grade.student.id if grade.student else None,
                                'student_name': f"{grade.student.first_name} {grade.student.last_name}" if grade.student else None,
                                'subject_id': grade.subject.id if grade.subject else None,
                                'subject_name': grade.subject.name if grade.subject else None,
                                'section_id': grade.section.id if grade.section else None,
                                'section_name': grade.section.section_id if grade.section else None,
                                'quarter': grade.quarter,
                                'grade': float(grade.grade) if grade.grade else None,
                                'status': grade.status,
                                'remarks': grade.remarks,
                                'school_year': grade.school_year,
                                'created_at': grade.created_at.isoformat() if grade.created_at else None,
                                'updated_at': grade.updated_at.isoformat() if grade.updated_at else None
                            }
                            data.append(grade_data)
                elif archive_type == 'section':
                    data = list(Sections.objects.all().values())
                elif archive_type == 'schedule':
                    # Handle schedule data differently
                    schedules = Schedules.objects.select_related('section', 'subject', 'teacher_id').all()
                    data = []
                    for schedule in schedules:
                        schedule_data = {
                            'id': schedule.id,
                            'section_id': schedule.section.id if schedule.section else None,
                            'section_name': schedule.section.section_id if schedule.section else None,
                            'subject_id': schedule.subject.id if schedule.subject else None,
                            'subject_name': schedule.subject.name if schedule.subject else None,
                            'teacher_id': schedule.teacher_id.id if schedule.teacher_id else None,
                            'teacher_name': f"{schedule.teacher_id.first_name} {schedule.teacher_id.last_name}" if schedule.teacher_id else None,
                            'day': schedule.day,
                            'start_time': schedule.start_time.strftime('%H:%M') if schedule.start_time else None,
                            'end_time': schedule.end_time.strftime('%H:%M') if schedule.end_time else None,
                            'room': schedule.room,
                            'created_at': schedule.created_at.isoformat() if schedule.created_at else None,
                            'updated_at': schedule.updated_at.isoformat() if schedule.updated_at else None
                        }
                        data.append(schedule_data)
                elif archive_type == 'event':
                    # Handle event data differently
                    events = Event.objects.all()
                    data = []
                    for event in events:
                        event_data = {
                            'id': event.id,
                            'title': event.title,
                            'description': event.description,
                            'start_date': event.start_date.isoformat() if event.start_date else None,
                            'end_date': event.end_date.isoformat() if event.end_date else None,
                            'start_time': event.start_time.strftime('%H:%M') if event.start_time else None,
                            'end_time': event.end_time.strftime('%H:%M') if event.end_time else None,
                            'created_at': event.created_at.isoformat() if event.created_at else None,
                            'updated_at': event.updated_at.isoformat() if event.updated_at else None
                        }
                        data.append(event_data)
                else:
                    messages.error(request, 'Invalid archive type')
                    return JsonResponse({'status': 'error', 'message': 'Invalid archive type'})
            except Exception as e:
                messages.error(request, f'Error fetching data: {str(e)}')
                return JsonResponse({'status': 'error', 'message': f'Error fetching data: {str(e)}'})
            
            if not data:
                messages.warning(request, f'No {archive_type} data found for {school_year}')
                return JsonResponse({'status': 'warning', 'message': f'No {archive_type} data found for {school_year}'})
            
            # Process data to handle date serialization
            processed_data = []
            for item in data:
                processed_item = {}
                for key, value in item.items():
                    if isinstance(value, (date, datetime)):
                        processed_item[key] = value.isoformat()
                    elif isinstance(value, Decimal):
                        processed_item[key] = float(value)
                    else:
                        processed_item[key] = value
                processed_data.append(processed_item)
            
            # Create archive record with transaction
            try:
                with transaction.atomic():
                    # Create archive with the currently logged-in admin user
                    archive = Archive.objects.create(
                        archive_type=archive_type,
                        school_year=school_year,
                        data=processed_data,
                        created_by=request.user  # Automatically set to the logged-in user
                    )
                    
                    # Log the archive creation
                    log_admin_activity(
                        user=request.user,
                        action=f'Created {archive_type} archive for {school_year}',
                        action_type='archive'
                    )
                
                messages.success(request, f'Successfully archived {len(processed_data)} {archive_type} records for {school_year}')
                return JsonResponse({
                    'status': 'success',
                    'message': f'Successfully archived {len(processed_data)} {archive_type} records for {school_year}',
                    'archive_id': archive.id
                })
                
            except Exception as e:
                messages.error(request, f'Error creating archive: {str(e)}')
                return JsonResponse({'status': 'error', 'message': f'Error creating archive: {str(e)}'})
            
        except Exception as e:
            messages.error(request, f'Error archiving data: {str(e)}')
            return JsonResponse({'status': 'error', 'message': f'Error archiving data: {str(e)}'})
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})

@login_required
def announcement_view(request):
    try:
        # Get all announcements ordered by creation date (newest first)
        announcements = Announcement.objects.all().order_by('-created_at')
        
        context = {
            'announcements': announcements
        }
        
        return render(request, 'announcement.html', context)
    except Exception as e:
        messages.error(request, f'Error viewing announcements: {str(e)}')
        return redirect('dashboard:dashboard')

@login_required
@require_POST
def add_announcement(request):
    """Add a new announcement"""
    try:
        title = request.POST.get('title')
        content = request.POST.get('content')
        
        if not title or not content:
            messages.error(request, 'Title and content are required')
            return redirect('dashboard:announcement')
        
        Announcement.objects.create(
            title=title,
            content=content,
            created_by=request.user
        )
        
        messages.success(request, 'Announcement added successfully')
        log_admin_activity(
            request.user,
            'Added a new announcement',
            'announcement'
        )
        
    except Exception as e:
        messages.error(request, f'Error adding announcement: {str(e)}')
    
    return redirect('dashboard:announcement')

@login_required
@require_POST
def delete_announcement(request, announcement_id):
    """Delete an announcement"""
    try:
        announcement = get_object_or_404(Announcement, id=announcement_id)
        announcement.delete()
        
        messages.success(request, 'Announcement deleted successfully')
        log_admin_activity(
            request.user,
            'Deleted an announcement',
            'announcement'
        )
        
    except Exception as e:
        messages.error(request, f'Error deleting announcement: {str(e)}')
    
    return redirect('dashboard:announcement')

def student_profile_view(request, student_id):
    try:
        student = Student.objects.get(id=student_id)
        context = {
            'student': student
        }
        return render(request, 'student_profile.html', context)
    except Student.DoesNotExist:
        messages.error(request, 'Student not found.')
        return redirect('dashboard:students')
    except Exception as e:
        messages.error(request, f'Error loading student profile: {str(e)}')
        return redirect('dashboard:students')

def validate_grade_level_enrollment(student_id, grade_level, school_year):
    """
    Validate if a student can be enrolled in a specific grade level for a given school year.
    Returns True if valid, False otherwise.
    """
    try:
        # Get the student
        student = Student.objects.get(student_id=student_id)
        
        # Check if student is already enrolled in this grade level for this school year
        enrollment_models = {
            7: Enrollment,
            8: Grade8Enrollment,
            9: Grade9Enrollment,
            10: Grade10Enrollment,
            11: Grade11Enrollment,
            12: Grade12Enrollment
        }
        
        enrollment_model = enrollment_models.get(grade_level)
        if not enrollment_model:
            return False
            
        existing_enrollment = enrollment_model.objects.filter(
            student=student,
            school_year=school_year
        ).first()
        
        if existing_enrollment:
            return False
            
        # Check if student has completed the previous grade level
        if grade_level > 7:
            previous_grade = grade_level - 1
            previous_model = enrollment_models.get(previous_grade)
            if previous_model:
                previous_enrollment = previous_model.objects.filter(
                    student=student,
                    school_year=school_year
                ).first()
                if not previous_enrollment or previous_enrollment.status != 'Completed':
                    return False
        
        return True
        
    except Student.DoesNotExist:
        return False
    except Exception as e:
        print(f"Error validating grade level enrollment: {str(e)}")
        return False

def subject_view(request):
    try:
        subjects = Subject.objects.all().order_by('subject_id')  # Ensure ascending order by subject_id
        paginator = Paginator(subjects, 10)
        page = request.GET.get('page')
        try:
            subjects = paginator.page(page)
        except PageNotAnInteger:
            subjects = paginator.page(1)
        except EmptyPage:
            subjects = paginator.page(paginator.num_pages)
        context = {
            'subjects': subjects,
            'grade_levels': range(7, 13)  # Grades 7 to 12
        }
        return render(request, 'subject.html', context)
    except Exception as e:
        messages.error(request, f"Error loading subjects: {str(e)}")
        return redirect('dashboard:subjects')

def delete_teacher(request):
    if request.method == 'POST':
        try:
            teacher_id = request.POST.get('teacher_id')
            teacher = Teachers.objects.get(teacher_id=teacher_id)
            teacher_name = f"{teacher.first_name} {teacher.last_name}"
            
            # Check for associated records
            if teacher.schedules_set.exists():
                messages.error(request, f'Cannot delete teacher {teacher_name} because they have assigned schedules. Please remove their schedules first.')
                return redirect('dashboard:teachers')
            
            if teacher.sections_set.exists():
                messages.error(request, f'Cannot delete teacher {teacher_name} because they are assigned as an adviser. Please reassign their advisory sections first.')
                return redirect('dashboard:teachers')
            
            # Delete the teacher
            teacher.delete()
            
            messages.success(request, f'Teacher {teacher_name} deleted successfully!')
            log_admin_activity(
                request.user,
                f"Deleted teacher: {teacher_name}",
                "teacher"
            )
            return redirect('dashboard:teachers')
        except Teachers.DoesNotExist:
            messages.error(request, 'Teacher not found!')
            return redirect('dashboard:teachers')
        except Exception as e:
            messages.error(request, f'Error deleting teacher: {str(e)}')
            return redirect('dashboard:teachers')
    return redirect('dashboard:teachers')

@login_required
def teacher_portal_view(request):
    """View for redirecting teachers to their portal"""
    try:
        # Check if user is a teacher
        teacher = Teachers.objects.get(user=request.user)
        return redirect('TeacherPortal:profile')  # Redirect to teacher profile page
    except Teachers.DoesNotExist:
        messages.error(request, "You don't have permission to access the teacher portal.")
        return redirect('dashboard:dashboard')

@login_required
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
    
    return redirect('dashboard:students')

@login_required
def student_grades_view(request):
    try:
        # Get active school year
        active_school_year = SchoolYear.get_active()
        school_years = SchoolYear.objects.all().order_by('-year_start')
        selected_year = request.GET.get('school_year', active_school_year.display_name if active_school_year else None)
        
        # Get all students
        students = Student.objects.all()
        
        # Get grades for the selected school year
        grades = Grades.objects.filter(
            school_year=selected_year
        ).select_related('student', 'subject', 'teacher', 'section')
        
        # Organize grades by student
        student_grades = {}
        for grade in grades:
            student_id = grade.student.id
            if student_id not in student_grades:
                student_grades[student_id] = {
                    'student': grade.student,
                    'subjects': {},
                    'total_average': 0,
                    'subjects_count': 0
                }
            
            subject_name = grade.subject.name
            if subject_name not in student_grades[student_id]['subjects']:
                student_grades[student_id]['subjects'][subject_name] = {
                    'quarters': {},
                    'average': 0,
                    'status': 'No Grades'
                }
            
            # Add quarter grade
            student_grades[student_id]['subjects'][subject_name]['quarters'][grade.quarter] = {
                'grade': float(grade.grade),
                'status': grade.status,
                'remarks': grade.remarks,
                'uploaded_at': grade.uploaded_at
            }
        
        # Calculate averages and status for each subject
        for student_data in student_grades.values():
            total_grade = 0
            total_subjects = 0
            
            for subject_data in student_data['subjects'].values():
                valid_grades = [q['grade'] for q in subject_data['quarters'].values()]
                if valid_grades:
                    subject_data['average'] = sum(valid_grades) / len(valid_grades)
                    subject_data['status'] = 'Passing' if subject_data['average'] >= 75 else 'Failing'
                    total_grade += subject_data['average']
                    total_subjects += 1
            
            if total_subjects > 0:
                student_data['total_average'] = total_grade / total_subjects
                student_data['subjects_count'] = total_subjects
        
        context = {
            'active_school_year': active_school_year,
            'school_years': school_years,
            'selected_year': selected_year,
            'student_grades': student_grades,
            'quarters': ['First Quarter', 'Second Quarter', 'Third Quarter', 'Fourth Quarter']
        }
        
        return render(request, 'student_grades.html', context)
        
    except Exception as e:
        messages.error(request, f'Error loading student grades: {str(e)}')
        return render(request, 'student_grades.html', {
            'active_school_year': None,
            'school_years': [],
            'selected_year': None,
            'student_grades': {},
            'quarters': ['First Quarter', 'Second Quarter', 'Third Quarter', 'Fourth Quarter']
        })

@login_required
def get_sections(request):
    """API endpoint to get sections for a grade level"""
    try:
        grade_level = request.GET.get('grade_level')
        if not grade_level:
            return JsonResponse({
                'success': False,
                'error': 'Grade level is required'
            }, status=400)
            
        # Get sections for the specified grade level
        sections = Sections.objects.filter(
            grade_level=grade_level
        ).select_related('adviser').order_by('section_id')
        
        # Get enrollment counts for each section
        section_stats = {}
        for section in sections:
            enrollment_model = get_enrollment_model(section.grade_level)
            if enrollment_model:
                count = enrollment_model.objects.filter(
                    section=section,
                    status='Active'
                ).count()
                section_stats[section.id] = count
        
        # Prepare section data
        sections_data = [{
            'id': section.id,
            'section_id': section.section_id,
            'grade_level': section.grade_level,
            'adviser': {
                'id': section.adviser.id if section.adviser else None,
                'name': f"{section.adviser.first_name} {section.adviser.last_name}" if section.adviser else 'No Adviser'
            },
            'student_count': section_stats.get(section.id, 0)
        } for section in sections]
        
        return JsonResponse({
            'success': True,
            'sections': sections_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required
def schedule_view(request):
    """View for managing class schedules"""
    try:
        # Get active school year
        active_school_year = SchoolYear.get_active()
        
        # Get all sections with their advisers
        sections = Sections.objects.select_related('adviser').all().order_by('grade_level', 'section_id')
        
        # Get all teachers for schedule assignment
        teachers = Teachers.objects.all().order_by('last_name', 'first_name')
        
        # Get all subjects
        subjects = Subject.objects.all().order_by('name')
        
        # Get all schedules
        schedules = Schedules.objects.select_related(
            'subject', 'teacher_id', 'section'
        ).order_by('day', 'start_time')
        
        # Define time slots for schedule grid
        time_slots = [
            '07:00', '08:00', '09:00', '10:00', '11:00',
            '12:00', '13:00', '14:00', '15:00', '16:00', '17:00'
        ]
        
        # Organize schedules by section
        section_schedules = {}
        for section in sections:
            section_schedules[section.id] = {
                'section': section,
                'schedules': schedules.filter(section=section)
            }
        
        context = {
            'active_school_year': active_school_year,
            'sections': sections,
            'teachers': teachers,
            'subjects': subjects,
            'schedules': schedules,
            'time_slots': time_slots,
            'section_schedules': section_schedules,
            'days': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        }
        
        return render(request, 'schedules.html', context)
        
    except Exception as e:
        messages.error(request, f'Error loading schedules: {str(e)}')
        return render(request, 'schedules.html', {
            'active_school_year': None,
            'sections': [],
            'teachers': [],
            'subjects': [],
            'schedules': [],
            'time_slots': [],
            'section_schedules': {},
            'days': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        })

@login_required
def add_schedule(request):
    """Add a new schedule"""
    if request.method == 'POST':
        try:
            # Get form data
            teacher_id = request.POST.get('teacher')
            subject_id = request.POST.get('subject')
            grade_level = request.POST.get('grade_level')
            section_id = request.POST.get('section')
            day = request.POST.get('day')
            start_time = request.POST.get('start_time')
            end_time = request.POST.get('end_time')
            room = request.POST.get('room')
            
            # Validate required fields
            if not all([teacher_id, subject_id, grade_level, section_id, day, start_time, end_time, room]):
                return JsonResponse({
                    'success': False,
                    'message': 'All fields are required'
                })
            
            # Get related objects
            teacher = Teachers.objects.get(id=teacher_id)
            subject = Subject.objects.get(id=subject_id)
            section = Sections.objects.get(id=section_id)
            
            # Convert time strings to time objects
            start_time = datetime.strptime(start_time, '%H:%M').time()
            end_time = datetime.strptime(end_time, '%H:%M').time()
            
            # Check for time conflicts
            # 1. Check teacher's schedule
            teacher_conflicts = Schedules.objects.filter(
                teacher_id=teacher,
                day=day
            )
            if Schedules.exists_time_conflict(teacher_conflicts, start_time, end_time):
                return JsonResponse({
                    'success': False,
                    'message': f'Time conflict: Teacher {teacher.first_name} {teacher.last_name} has another class at this time'
                })
            
            # 2. Check section's schedule
            section_conflicts = Schedules.objects.filter(
                section=section,
                day=day
            )
            if Schedules.exists_time_conflict(section_conflicts, start_time, end_time):
                return JsonResponse({
                    'success': False,
                    'message': f'Time conflict: Section {section.section_id} has another class at this time'
                })
            
            # 3. Check room availability
            room_conflicts = Schedules.objects.filter(
                room=room,
                day=day
            )
            if Schedules.exists_time_conflict(room_conflicts, start_time, end_time):
                return JsonResponse({
                    'success': False,
                    'message': f'Time conflict: Room {room} is occupied at this time'
                })
            
            # Create the schedule
            schedule = Schedules.objects.create(
                subject=subject,
                teacher_id=teacher,
                grade_level=grade_level,
                section=section,
                day=day,
                start_time=start_time,
                end_time=end_time,
                room=room
            )
            
            # Log the activity
            log_admin_activity(
                request.user,
                f"Added schedule: {subject.name} for {section.section_id} ({day})",
                "schedule"
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Schedule added successfully',
                'schedule': {
                    'id': schedule.id,
                    'subject': subject.name,
                    'teacher': f"{teacher.first_name} {teacher.last_name}",
                    'section': section.section_id,
                    'day': day,
                    'time': f"{start_time.strftime('%I:%M %p')} - {end_time.strftime('%I:%M %p')}",
                    'room': room
                }
            })
            
        except Teachers.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Teacher not found'
            })
        except Subject.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Subject not found'
            })
        except Sections.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Section not found'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error adding schedule: {str(e)}'
            })
    
    return JsonResponse({
        'success': False,
        'message': 'Invalid request method'
    })

@login_required
def get_sections_by_grade(request):
    """API endpoint to get sections for a specific grade level"""
    try:
        grade_level = request.GET.get('grade_level')
        if not grade_level:
            return JsonResponse({
                'success': False,
                'message': 'Grade level is required'
            }, status=400)
        
        # Get sections for the specified grade level
        sections = Sections.objects.filter(
            grade_level=grade_level
        ).select_related('adviser').order_by('section_id')
        
        # Get enrollment counts for each section
        section_stats = {}
        for section in sections:
            enrollment_model = get_enrollment_model(section.grade_level)
            if enrollment_model:
                count = enrollment_model.objects.filter(
                    section=section,
                    status='Active'
                ).count()
                section_stats[section.id] = count
        
        # Prepare section data
        sections_data = [{
            'id': section.id,
            'section_id': section.section_id,
            'grade_level': section.grade_level,
            'adviser': {
                'id': section.adviser.id if section.adviser else None,
                'name': f"{section.adviser.first_name} {section.adviser.last_name}" if section.adviser else 'No Adviser'
            },
            'student_count': section_stats.get(section.id, 0)
        } for section in sections]
        
        return JsonResponse({
            'success': True,
            'sections': sections_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)

@login_required
def get_available_time_slots(request):
    """API endpoint to get available time slots for scheduling"""
    try:
        # Get parameters
        day = request.GET.get('day')
        teacher_id = request.GET.get('teacher_id')
        section_id = request.GET.get('section_id')
        room = request.GET.get('room')
        
        if not all([day, teacher_id, section_id]):
            return JsonResponse({
                'success': False,
                'message': 'Day, teacher, and section are required'
            }, status=400)
        
        # Get existing schedules for the day
        teacher_schedules = Schedules.objects.filter(
            teacher_id=teacher_id,
            day=day
        ).order_by('start_time')
        
        section_schedules = Schedules.objects.filter(
            section_id=section_id,
            day=day
        ).order_by('start_time')
        
        # Only check room conflicts if room is provided
        room_schedules = []
        if room:
            room_schedules = Schedules.objects.filter(
                room=room,
                day=day
            ).order_by('start_time')
        
        # Define all possible time slots (7 AM to 5 PM)
        all_slots = []
        current_time = datetime.strptime('07:00', '%H:%M').time()
        end_time = datetime.strptime('17:00', '%H:%M').time()
        
        while current_time < end_time:
            slot_end = (datetime.combine(date.today(), current_time) + timedelta(hours=1)).time()
            all_slots.append({
                'start': current_time.strftime('%H:%M'),
                'end': slot_end.strftime('%H:%M'),
                'display': f"{current_time.strftime('%I:%M %p')} - {slot_end.strftime('%I:%M %p')}"
            })
            current_time = slot_end
        
        # Find occupied slots
        occupied_slots = set()
        
        # Helper function to mark slots as occupied
        def mark_occupied_slots(schedules):
            for schedule in schedules:
                start = schedule.start_time
                end = schedule.end_time
                for slot in all_slots:
                    slot_start = datetime.strptime(slot['start'], '%H:%M').time()
                    slot_end = datetime.strptime(slot['end'], '%H:%M').time()
                    if (start <= slot_start < end) or (start < slot_end <= end):
                        occupied_slots.add(f"{slot['start']}-{slot['end']}")
        
        # Mark slots as occupied based on all conflicts
        mark_occupied_slots(teacher_schedules)
        mark_occupied_slots(section_schedules)
        if room:
            mark_occupied_slots(room_schedules)
        
        # Filter out occupied slots
        available_slots = [
            slot for slot in all_slots 
            if f"{slot['start']}-{slot['end']}" not in occupied_slots
        ]
        
        return JsonResponse({
            'success': True,
            'available_slots': available_slots,
            'occupied_slots': list(occupied_slots)
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)

@login_required
def get_section_schedule(request):
    """API endpoint to get the complete schedule for a specific section"""
    try:
        section_id = request.GET.get('section_id')
        if not section_id:
            return JsonResponse({
                'success': False,
                'message': 'Section ID is required'
            }, status=400)
        
        # Get the section
        try:
            section = Sections.objects.get(id=section_id)
        except Sections.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Section not found'
            }, status=404)
        
        # Get all schedules for the section
        schedules = Schedules.objects.filter(
            section=section
        ).select_related(
            'subject',
            'teacher_id'
        ).order_by('day', 'start_time')
        
        # Format schedules for the frontend
        formatted_schedules = []
        for schedule in schedules:
            formatted_schedules.append({
                'subject_name': schedule.subject.name,
                'teacher_name': f"{schedule.teacher_id.first_name} {schedule.teacher_id.last_name}",
                'start_time': schedule.start_time.strftime('%H:%M'),
                'end_time': schedule.end_time.strftime('%H:%M'),
                'day': schedule.day,
                'room': schedule.room
            })
        
        return JsonResponse({
            'success': True,
            'schedules': formatted_schedules
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)

@login_required
def get_enrolled_students(request):
    """API endpoint to get all enrolled students for a specific section"""
    try:
        section_id = request.GET.get('section_id')
        school_year = request.GET.get('school_year')
        
        if not section_id:
            return JsonResponse({
                'success': False,
                'message': 'Section ID is required'
            }, status=400)
        
        # Get the section
        try:
            section = Sections.objects.get(id=section_id)
        except Sections.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Section not found'
            }, status=404)
        
        # Get the appropriate enrollment model based on grade level
        enrollment_model = get_enrollment_model(section.grade_level)
        if not enrollment_model:
            return JsonResponse({
                'success': False,
                'message': f'Invalid grade level: {section.grade_level}'
            }, status=400)
        
        # Get enrollments for the section
        enrollments = enrollment_model.objects.filter(
            section=section,
            status='Active'
        ).select_related('student')
        
        # If school year is provided, filter by it
        if school_year:
            enrollments = enrollments.filter(school_year=school_year)
        
        # Prepare student data
        students_data = []
        for enrollment in enrollments:
            student = enrollment.student
            students_data.append({
                'id': student.id,
                'student_id': student.student_id,
                'name': f"{student.first_name} {student.last_name}",
                'gender': student.gender,
                'email': student.email,
                'mobile_number': student.mobile_number,
                'status': enrollment.status,
                'enrollment_date': enrollment.enrollment_date.strftime('%Y-%m-%d') if enrollment.enrollment_date else None,
                'track': enrollment.track if hasattr(enrollment, 'track') else None
            })
        
        return JsonResponse({
            'success': True,
            'section': {
                'id': section.id,
                'section_id': section.section_id,
                'grade_level': section.grade_level,
                'adviser': {
                    'id': section.adviser.id if section.adviser else None,
                    'name': f"{section.adviser.first_name} {section.adviser.last_name}" if section.adviser else 'No Adviser'
                }
            },
            'students': students_data,
            'total_students': len(students_data)
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)

@login_required
def get_eligible_students(request):
    """API endpoint to get students eligible for enrollment in a specific section"""
    try:
        section_id = request.GET.get('section_id')
        school_year = request.GET.get('school_year')
        
        if not section_id or not school_year:
            return JsonResponse({
                'success': False,
                'message': 'Section ID and school year are required'
            }, status=400)
        
        # Get the section
        try:
            section = Sections.objects.get(id=section_id)
        except Sections.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Section not found'
            }, status=404)
        
        # Get all students
        students = Student.objects.all()
        
        # Get currently enrolled students in this grade level for this school year
        enrollment_model = get_enrollment_model(section.grade_level)
        if not enrollment_model:
            return JsonResponse({
                'success': False,
                'message': f'Invalid grade level: {section.grade_level}'
            }, status=400)
        
        enrolled_student_ids = enrollment_model.objects.filter(
            school_year=school_year,
            status='Active'
        ).values_list('student_id', flat=True)
        
        # Get students who completed the previous grade level
        eligible_students = []
        for student in students:
            # Skip if already enrolled in this grade level
            if student.id in enrolled_student_ids:
                continue
            
            # For Grade 7, all students are eligible
            if section.grade_level == 7:
                eligible_students.append(student)
                continue
            
            # For other grades, check if they completed the previous grade
            previous_grade = section.grade_level - 1
            previous_enrollment_model = get_enrollment_model(previous_grade)
            
            if previous_enrollment_model:
                previous_enrollment = previous_enrollment_model.objects.filter(
                    student=student,
                    status='Completed'
                ).order_by('-school_year').first()
                
                if previous_enrollment:
                    eligible_students.append(student)
        
        # Prepare student data
        students_data = []
        for student in eligible_students:
            students_data.append({
                'id': student.id,
                'student_id': student.student_id,
                'name': f"{student.first_name} {student.last_name}",
                'gender': student.gender,
                'email': student.email,
                'mobile_number': student.mobile_number,
                'status': student.status,
                'last_grade_level': previous_grade if section.grade_level > 7 else None,
                'last_school_year': previous_enrollment.school_year if section.grade_level > 7 and previous_enrollment else None
            })
        
        return JsonResponse({
            'success': True,
            'section': {
                'id': section.id,
                'section_id': section.section_id,
                'grade_level': section.grade_level
            },
            'school_year': school_year,
            'eligible_students': students_data,
            'total_eligible': len(students_data)
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)

@login_required
def admin_profile(request):
    """View and manage admin profile"""
    try:
        # Get or create admin profile
        admin_profile, created = AdminProfile.objects.get_or_create(
            user=request.user,
            defaults={
                'first_name': request.user.first_name,
                'last_name': request.user.last_name,
                'email': request.user.email
            }
        )
        
        if request.method == 'POST':
            try:
                # Update profile information
                admin_profile.first_name = request.POST.get('first_name', admin_profile.first_name)
                admin_profile.last_name = request.POST.get('last_name', admin_profile.last_name)
                admin_profile.email = request.POST.get('email', admin_profile.email)
                admin_profile.phone = request.POST.get('phone', admin_profile.phone)
                admin_profile.address = request.POST.get('address', admin_profile.address)
                
                # Handle profile photo upload
                if 'profile_photo' in request.FILES:
                    admin_profile.profile_photo = request.FILES['profile_photo']
                
                # Update user information
                user = request.user
                user.first_name = admin_profile.first_name
                user.last_name = admin_profile.last_name
                user.email = admin_profile.email
                user.save()
                
                # Save profile changes
                admin_profile.save()
                
                messages.success(request, 'Profile updated successfully!')
                log_admin_activity(
                    request.user,
                    "Updated admin profile information",
                    "profile"
                )
                
            except Exception as e:
                messages.error(request, f'Error updating profile: {str(e)}')
        
        # Get recent activities
        recent_activities = AdminActivity.objects.filter(
            user=request.user
        ).order_by('-timestamp')[:10]
        
        context = {
            'admin_profile': admin_profile,
            'recent_activities': recent_activities,
            'profile_updated': request.method == 'POST'
        }
        
        return render(request, 'admin_profile.html', context)
        
    except Exception as e:
        messages.error(request, f'Error loading profile: {str(e)}')
        return redirect('dashboard:dashboard')

@login_required
def admin_profile_update(request):
    """API endpoint to update admin profile information"""
    if request.method == 'POST':
        try:
            # Get the admin profile
            try:
                admin_profile = AdminProfile.objects.get(user=request.user)
            except AdminProfile.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': 'Admin profile not found'
                }, status=404)
            
            # Get update type and data
            update_type = request.POST.get('update_type')
            if not update_type:
                return JsonResponse({
                    'success': False,
                    'message': 'Update type is required'
                }, status=400)
            
            # Handle different types of updates
            if update_type == 'basic_info':
                # Update basic information
                admin_profile.first_name = request.POST.get('first_name', admin_profile.first_name)
                admin_profile.last_name = request.POST.get('last_name', admin_profile.last_name)
                admin_profile.email = request.POST.get('email', admin_profile.email)
                admin_profile.phone = request.POST.get('phone', admin_profile.phone)
                admin_profile.address = request.POST.get('address', admin_profile.address)
                
                # Update user information
                user = request.user
                user.first_name = admin_profile.first_name
                user.last_name = admin_profile.last_name
                user.email = admin_profile.email
                user.save()
                
            elif update_type == 'profile_photo':
                # Handle profile photo upload
                if 'profile_photo' not in request.FILES:
                    return JsonResponse({
                        'success': False,
                        'message': 'No profile photo provided'
                    }, status=400)
                
                # Delete old photo if exists
                if admin_profile.profile_photo:
                    try:
                        os.remove(admin_profile.profile_photo.path)
                    except:
                        pass
                
                admin_profile.profile_photo = request.FILES['profile_photo']
                
            elif update_type == 'password':
                # Handle password change
                current_password = request.POST.get('current_password')
                new_password = request.POST.get('new_password')
                confirm_password = request.POST.get('confirm_password')
                
                if not all([current_password, new_password, confirm_password]):
                    return JsonResponse({
                        'success': False,
                        'message': 'All password fields are required'
                    }, status=400)
                
                # Verify current password
                if not request.user.check_password(current_password):
                    return JsonResponse({
                        'success': False,
                        'message': 'Current password is incorrect'
                    }, status=400)
                
                # Verify new passwords match
                if new_password != confirm_password:
                    return JsonResponse({
                        'success': False,
                        'message': 'New passwords do not match'
                    }, status=400)
                
                # Update password
                request.user.set_password(new_password)
                request.user.save()
                
                # Update session to prevent logout
                update_session_auth_hash(request, request.user)
                
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'Invalid update type'
                }, status=400)
            
            # Save profile changes
            admin_profile.save()
            
            # Log the activity
            log_admin_activity(
                request.user,
                f"Updated {update_type.replace('_', ' ')}",
                "profile"
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Profile updated successfully',
                'profile': {
                    'first_name': admin_profile.first_name,
                    'last_name': admin_profile.last_name,
                    'email': admin_profile.email,
                    'phone': admin_profile.phone,
                    'address': admin_profile.address,
                    'profile_photo_url': admin_profile.profile_photo.url if admin_profile.profile_photo else None
                }
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            }, status=500)
    
    return JsonResponse({
        'success': False,
        'message': 'Invalid request method'
    }, status=405)

@login_required
def get_section_grade(request):
    """API endpoint to get grade information for all students in a section"""
    try:
        section_id = request.GET.get('section_id')
        school_year = request.GET.get('school_year')
        quarter = request.GET.get('quarter')
        
        if not all([section_id, school_year, quarter]):
            return JsonResponse({
                'success': False,
                'message': 'Section ID, school year, and quarter are required'
            }, status=400)
        
        # Get the section
        try:
            section = Sections.objects.get(id=section_id)
        except Sections.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Section not found'
            }, status=404)
        
        # Get all subjects
        subjects = Subject.objects.all().order_by('name')
        
        # Get all enrolled students
        enrollment_model = get_enrollment_model(section.grade_level)
        if not enrollment_model:
            return JsonResponse({
                'success': False,
                'message': f'Invalid grade level: {section.grade_level}'
            }, status=400)
        
        enrollments = enrollment_model.objects.filter(
            section=section,
            school_year=school_year,
            status='Active'
        ).select_related('student')
        
        # Get grades for all students in this section
        grades = Grades.objects.filter(
            section=section,
            school_year=school_year,
            quarter=quarter
        ).select_related('student', 'subject', 'teacher')
        
        # Organize grades by student and subject
        student_grades = {}
        for enrollment in enrollments:
            student = enrollment.student
            student_grades[student.id] = {
                'student': {
                    'id': student.id,
                    'student_id': student.student_id,
                    'name': f"{student.first_name} {student.last_name}",
                    'gender': student.gender
                },
                'subjects': {},
                'total_average': 0,
                'subjects_count': 0
            }
        
        # Fill in grades for each student
        for grade in grades:
            student_id = grade.student.id
            if student_id in student_grades:
                subject_name = grade.subject.name
                student_grades[student_id]['subjects'][subject_name] = {
                    'grade': float(grade.grade),
                    'status': grade.status,
                    'remarks': grade.remarks,
                    'teacher': f"{grade.teacher.first_name} {grade.teacher.last_name}" if grade.teacher else 'No Teacher'
                }
        
        # Calculate averages and status for each student
        for student_data in student_grades.values():
            total_grade = 0
            total_subjects = 0
            
            for subject_name in subjects:
                if subject_name.name in student_data['subjects']:
                    grade_data = student_data['subjects'][subject_name.name]
                    total_grade += grade_data['grade']
                    total_subjects += 1
                else:
                    student_data['subjects'][subject_name.name] = {
                        'grade': None,
                        'status': 'No Grade',
                        'remarks': '',
                        'teacher': 'No Teacher'
                    }
            
            if total_subjects > 0:
                student_data['total_average'] = round(total_grade / total_subjects, 2)
                student_data['subjects_count'] = total_subjects
                student_data['status'] = 'Passing' if student_data['total_average'] >= 75 else 'Failing'
            else:
                student_data['status'] = 'No Grades'
        
        return JsonResponse({
            'success': True,
            'section': {
                'id': section.id,
                'section_id': section.section_id,
                'grade_level': section.grade_level,
                'adviser': {
                    'id': section.adviser.id if section.adviser else None,
                    'name': f"{section.adviser.first_name} {section.adviser.last_name}" if section.adviser else 'No Adviser'
                }
            },
            'school_year': school_year,
            'quarter': quarter,
            'subjects': [subject.name for subject in subjects],
            'students': list(student_grades.values()),
            'total_students': len(student_grades)
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)

@login_required
def school_year_management(request):
    """View for managing school years"""
    try:
        # Get all school years ordered by start date
        school_years = SchoolYear.objects.all().order_by('-year_start')
        
        if request.method == 'POST':
            action = request.POST.get('action')
            
            if action == 'create':
                # Create new school year
                year_start = request.POST.get('year_start')
                year_end = request.POST.get('year_end')
                is_active = request.POST.get('is_active') == 'true'
                
                # Validate dates
                try:
                    start_date = datetime.strptime(year_start, '%Y-%m-%d').date()
                    end_date = datetime.strptime(year_end, '%Y-%m-%d').date()
                    
                    if start_date >= end_date:
                        messages.error(request, 'End date must be after start date')
                        return redirect('dashboard:school_year_management')
                    
                    # Check for overlapping school years
                    overlapping = SchoolYear.objects.filter(
                        (Q(year_start__lte=start_date) & Q(year_end__gte=start_date)) |
                        (Q(year_start__lte=end_date) & Q(year_end__gte=end_date))
                    ).exists()
                    
                    if overlapping:
                        messages.error(request, 'School year dates overlap with existing school year')
                        return redirect('dashboard:school_year_management')
                    
                    # Create new school year
                    school_year = SchoolYear.objects.create(
                        year_start=start_date,
                        year_end=end_date,
                        is_active=is_active
                    )
                    
                    # If this is set as active, deactivate other school years
                    if is_active:
                        SchoolYear.objects.exclude(id=school_year.id).update(is_active=False)
                    
                    messages.success(request, f'Successfully created school year {school_year.display_name}')
                    log_admin_activity(
                        request.user,
                        f"Created new school year: {school_year.display_name}",
                        "school_year"
                    )
                    
                except ValueError:
                    messages.error(request, 'Invalid date format')
                    return redirect('dashboard:school_year_management')
                
            elif action == 'update':
                # Update existing school year
                school_year_id = request.POST.get('school_year_id')
                year_start = request.POST.get('year_start')
                year_end = request.POST.get('year_end')
                is_active = request.POST.get('is_active') == 'true'
                
                try:
                    school_year = SchoolYear.objects.get(id=school_year_id)
                    start_date = datetime.strptime(year_start, '%Y-%m-%d').date()
                    end_date = datetime.strptime(year_end, '%Y-%m-%d').date()
                    
                    if start_date >= end_date:
                        messages.error(request, 'End date must be after start date')
                        return redirect('dashboard:school_year_management')
                    
                    # Check for overlapping school years (excluding current school year)
                    overlapping = SchoolYear.objects.exclude(id=school_year_id).filter(
                        (Q(year_start__lte=start_date) & Q(year_end__gte=start_date)) |
                        (Q(year_start__lte=end_date) & Q(year_end__gte=end_date))
                    ).exists()
                    
                    if overlapping:
                        messages.error(request, 'School year dates overlap with existing school year')
                        return redirect('dashboard:school_year_management')
                    
                    # Update school year
                    school_year.year_start = start_date
                    school_year.year_end = end_date
                    school_year.is_active = is_active
                    school_year.save()
                    
                    # If this is set as active, deactivate other school years
                    if is_active:
                        SchoolYear.objects.exclude(id=school_year.id).update(is_active=False)
                    
                    messages.success(request, f'Successfully updated school year {school_year.display_name}')
                    log_admin_activity(
                        request.user,
                        f"Updated school year: {school_year.display_name}",
                        "school_year"
                    )
                    
                except SchoolYear.DoesNotExist:
                    messages.error(request, 'School year not found')
                    return redirect('dashboard:school_year_management')
                except ValueError:
                    messages.error(request, 'Invalid date format')
                    return redirect('dashboard:school_year_management')
                
            elif action == 'delete':
                # Delete school year
                school_year_id = request.POST.get('school_year_id')
                
                try:
                    school_year = SchoolYear.objects.get(id=school_year_id)
                    
                    # Check if school year is active
                    if school_year.is_active:
                        messages.error(request, 'Cannot delete active school year')
                        return redirect('dashboard:school_year_management')
                    
                    # Check if school year has associated data
                    if (Enrollment.objects.filter(school_year=school_year.display_name).exists() or
                        Grade8Enrollment.objects.filter(school_year=school_year.display_name).exists() or
                        Grade9Enrollment.objects.filter(school_year=school_year.display_name).exists() or
                        Grade10Enrollment.objects.filter(school_year=school_year.display_name).exists() or
                        Grade11Enrollment.objects.filter(school_year=school_year.display_name).exists() or
                        Grade12Enrollment.objects.filter(school_year=school_year.display_name).exists()):
                        messages.error(request, 'Cannot delete school year with associated enrollment data')
                        return redirect('dashboard:school_year_management')
                    
                    school_year.delete()
                    messages.success(request, f'Successfully deleted school year {school_year.display_name}')
                    log_admin_activity(
                        request.user,
                        f"Deleted school year: {school_year.display_name}",
                        "school_year"
                    )
                    
                except SchoolYear.DoesNotExist:
                    messages.error(request, 'School year not found')
                    return redirect('dashboard:school_year_management')
            
            elif action == 'set_active':
                # Set school year as active
                school_year_id = request.POST.get('school_year_id')
                
                try:
                    school_year = SchoolYear.objects.get(id=school_year_id)
                    
                    # Deactivate all other school years
                    SchoolYear.objects.exclude(id=school_year_id).update(is_active=False)
                    
                    # Set this school year as active
                    school_year.is_active = True
                    school_year.save()
                    
                    messages.success(request, f'Successfully set {school_year.display_name} as active school year')
                    log_admin_activity(
                        request.user,
                        f"Set {school_year.display_name} as active school year",
                        "school_year"
                    )
                    
                except SchoolYear.DoesNotExist:
                    messages.error(request, 'School year not found')
                    return redirect('dashboard:school_year_management')
        
        # Get active school year
        active_school_year = SchoolYear.get_active()
        
        context = {
            'school_years': school_years,
            'active_school_year': active_school_year
        }
        
        return render(request, 'school_year_management_table.html', context)
        
    except Exception as e:
        messages.error(request, f'Error managing school years: {str(e)}')
        return redirect('dashboard:dashboard')

def log_admin_activity(user, action, activity_type):
    """Log admin activities for audit trail"""
    from .models import AdminActivity
    AdminActivity.objects.create(
        admin=user,  # Changed from user to admin to match model field
        action=action,
        action_type=activity_type  # Changed from activity_type to action_type to match model field
    )

@login_required
def set_active_school_year(request):
    """API endpoint to set a school year as active"""
    if request.method == 'POST':
        try:
            school_year_id = request.POST.get('school_year_id')
            
            if not school_year_id:
                return JsonResponse({
                    'success': False,
                    'message': 'School year ID is required'
                }, status=400)
            
            # Get the school year
            try:
                school_year = SchoolYear.objects.get(id=school_year_id)
            except SchoolYear.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': 'School year not found'
                }, status=404)
            
            # Check if school year is already active
            if school_year.is_active:
                return JsonResponse({
                    'success': False,
                    'message': f'School year {school_year.display_name} is already active'
                }, status=400)
            
            # Deactivate all other school years
            SchoolYear.objects.exclude(id=school_year_id).update(is_active=False)
            
            # Set this school year as active
            school_year.is_active = True
            school_year.save()
            
            # Log the activity
            log_admin_activity(
                request.user,
                f"Set {school_year.display_name} as active school year",
                "school_year"
            )
            
            return JsonResponse({
                'success': True,
                'message': f'Successfully set {school_year.display_name} as active school year'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            }, status=500)
    
    return JsonResponse({
        'success': False,
        'message': 'Invalid request method'
    }, status=405)

@login_required
def add_school_year(request):
    """API endpoint to add a new school year"""
    if request.method == 'POST':
        try:
            # Get form data
            year_start = request.POST.get('year_start')
            year_end = request.POST.get('year_end')
            is_active = request.POST.get('is_active') == 'true'
            
            # Validate required fields
            if not all([year_start, year_end]):
                return JsonResponse({
                    'success': False,
                    'message': 'Start date and end date are required'
                }, status=400)
            
            # Validate dates
            try:
                start_date = datetime.strptime(year_start, '%Y-%m-%d').date()
                end_date = datetime.strptime(year_end, '%Y-%m-%d').date()
                
                if start_date >= end_date:
                    return JsonResponse({
                        'success': False,
                        'message': 'End date must be after start date'
                    }, status=400)
                
                # Check for overlapping school years
                overlapping = SchoolYear.objects.filter(
                    (Q(year_start__lte=start_date) & Q(year_end__gte=start_date)) |
                    (Q(year_start__lte=end_date) & Q(year_end__gte=end_date))
                ).exists()
                
                if overlapping:
                    return JsonResponse({
                        'success': False,
                        'message': 'School year dates overlap with existing school year'
                    }, status=400)
                
                # Create new school year
                school_year = SchoolYear.objects.create(
                    year_start=start_date,
                    year_end=end_date,
                    is_active=is_active
                )
                
                # If this is set as active, deactivate other school years
                if is_active:
                    SchoolYear.objects.exclude(id=school_year.id).update(is_active=False)
                
                # Log the activity
                log_admin_activity(
                    request.user,
                    f"Created new school year: {school_year.display_name}",
                    "school_year"
                )
                
                return JsonResponse({
                    'success': True,
                    'message': f'Successfully created school year {school_year.display_name}',
                    'school_year': {
                        'id': school_year.id,
                        'display_name': school_year.display_name,
                        'year_start': school_year.year_start.strftime('%Y-%m-%d'),
                        'year_end': school_year.year_end.strftime('%Y-%m-%d'),
                        'is_active': school_year.is_active
                    }
                })
                
            except ValueError:
                return JsonResponse({
                    'success': False,
                    'message': 'Invalid date format'
                }, status=400)
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            }, status=500)
    
    return JsonResponse({
        'success': False,
        'message': 'Invalid request method'
    }, status=405)

@login_required
def get_teacher_schedule(request):
    """API endpoint to get the complete schedule for a specific teacher"""
    try:
        teacher_id = request.GET.get('teacher_id')
        school_year = request.GET.get('school_year')
        
        if not teacher_id:
            return JsonResponse({
                'success': False,
                'message': 'Teacher ID is required'
            }, status=400)
        
        # Get the teacher
        try:
            teacher = Teachers.objects.get(id=teacher_id)
        except Teachers.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Teacher not found'
            }, status=404)
        
        # Get all schedules for the teacher
        schedules = Schedules.objects.filter(
            teacher_id=teacher
        ).select_related(
            'subject',
            'section'
        ).order_by('day', 'start_time')
        
        # If school year is provided, filter by it
        if school_year:
            schedules = schedules.filter(school_year=school_year)
        
        # Format schedules for the frontend
        formatted_schedules = []
        for schedule in schedules:
            formatted_schedules.append({
                'subject_name': schedule.subject.name,
                'section_name': f"Grade {schedule.grade_level} - {schedule.section.section_id}",
                'start_time': schedule.start_time.strftime('%H:%M'),
                'end_time': schedule.end_time.strftime('%H:%M'),
                'day': schedule.day,
                'room': schedule.room
            })
        
        return JsonResponse({
            'success': True,
            'schedules': formatted_schedules
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)

@login_required
def get_dashboard_data(request):
    """API endpoint to get comprehensive dashboard data"""
    try:
        # Get active school year
        active_school_year = SchoolYear.get_active()
        if not active_school_year:
            return JsonResponse({
                'success': False,
                'message': 'No active school year found'
            }, status=400)

        # Get enrollment statistics
        enrollment_stats = {
            'total': 0,
            'by_grade': {},
            'by_gender': {'Male': 0, 'Female': 0},
            'by_status': {'Active': 0, 'Dropped': 0, 'Transferred': 0, 'Completed': 0}
        }

        # Define enrollment models for each grade
        enrollment_models = {
            7: Enrollment,
            8: Grade8Enrollment,
            9: Grade9Enrollment,
            10: Grade10Enrollment,
            11: Grade11Enrollment,
            12: Grade12Enrollment
        }

        # Calculate enrollment statistics
        for grade, model in enrollment_models.items():
            grade_enrollments = model.objects.filter(
                school_year=active_school_year.display_name
            ).select_related('student')

            grade_count = grade_enrollments.count()
            enrollment_stats['total'] += grade_count
            enrollment_stats['by_grade'][f'Grade {grade}'] = grade_count

            # Update gender and status statistics
            for enrollment in grade_enrollments:
                enrollment_stats['by_gender'][enrollment.student.gender] += 1
                enrollment_stats['by_status'][enrollment.status] += 1

        # Get teacher statistics
        teacher_stats = {
            'total': Teachers.objects.count(),
            'by_gender': {
                'Male': Teachers.objects.filter(gender='Male').count(),
                'Female': Teachers.objects.filter(gender='Female').count()
            },
            'by_department': {}
        }

        # Calculate department statistics
        departments = Teachers.objects.values_list('department', flat=True).distinct()
        for dept in departments:
            if dept:  # Skip empty department names
                teacher_stats['by_department'][dept] = Teachers.objects.filter(department=dept).count()

        # Get section statistics
        section_stats = {
            'total': Sections.objects.count(),
            'by_grade': {
                grade: Sections.objects.filter(grade_level=grade).count()
                for grade in range(7, 13)
            }
        }

        # Get recent activities (last 10)
        recent_activities = AdminActivity.objects.all().order_by('-timestamp')[:10]
        activities_data = [{
            'id': activity.id,
            'action': activity.action,
            'action_type': activity.action_type,
            'timestamp': activity.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'user': f"{activity.user.first_name} {activity.user.last_name}"
        } for activity in recent_activities]

        # Get upcoming events (next 7 days)
        today = timezone.now().date()
        upcoming_events = Event.objects.filter(
            start_date__gte=today
        ).order_by('start_date', 'start_time')[:5]
        events_data = [{
            'id': event.id,
            'title': event.title,
            'description': event.description,
            'start_date': event.start_date.strftime('%Y-%m-%d'),
            'end_date': event.end_date.strftime('%Y-%m-%d') if event.end_date else None,
            'start_time': event.start_time.strftime('%H:%M') if event.start_time else None,
            'end_time': event.end_time.strftime('%H:%M') if event.end_time else None
        } for event in upcoming_events]

        # Get recent announcements (last 5)
        recent_announcements = Announcement.objects.all().order_by('-created_at')[:5]
        announcements_data = [{
            'id': announcement.id,
            'title': announcement.title,
            'content': announcement.content,
            'created_at': announcement.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'created_by': f"{announcement.created_by.first_name} {announcement.created_by.last_name}"
        } for announcement in recent_announcements]

        # Calculate student growth (comparing to last month)
        last_month = datetime.now() - timedelta(days=30)
        students_last_month = sum(
            model.objects.filter(
                school_year=active_school_year.display_name,
                enrollment_date__lt=last_month
            ).count()
            for model in enrollment_models.values()
        )

        current_total = enrollment_stats['total']
        if students_last_month > 0:
            student_growth = ((current_total - students_last_month) / students_last_month) * 100
        else:
            student_growth = 0

        # Prepare chart data
        gender_data = {
            'labels': ['Male', 'Female'],
            'data': [
                enrollment_stats['by_gender']['Male'],
                enrollment_stats['by_gender']['Female']
            ]
        }

        grade_level_data = {
            'labels': list(enrollment_stats['by_grade'].keys()),
            'data': list(enrollment_stats['by_grade'].values())
        }

        # Get monthly enrollment trends
        monthly_data = defaultdict(lambda: [0] * 12)
        for model in enrollment_models.values():
            enrollments = (
                model.objects
                .filter(school_year=active_school_year.display_name)
                .annotate(month=ExtractMonth('enrollment_date'))
                .values('month')
                .annotate(count=Count('id'))
            )
            for item in enrollments:
                monthly_data['enrollments'][item['month'] - 1] = item['count']

        enrollment_trends = {
            'labels': ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
            'datasets': [{
                'label': 'Monthly Enrollments',
                'data': monthly_data['enrollments']
            }]
        }

        return JsonResponse({
            'success': True,
            'data': {
                'active_school_year': {
                    'id': active_school_year.id,
                    'display_name': active_school_year.display_name,
                    'year_start': active_school_year.year_start.strftime('%Y-%m-%d'),
                    'year_end': active_school_year.year_end.strftime('%Y-%m-%d')
                },
                'enrollment_stats': enrollment_stats,
                'teacher_stats': teacher_stats,
                'section_stats': section_stats,
                'student_growth': round(student_growth, 1),
                'recent_activities': activities_data,
                'upcoming_events': events_data,
                'recent_announcements': announcements_data,
                'chart_data': {
                    'gender': gender_data,
                    'grade_level': grade_level_data,
                    'enrollment_trends': enrollment_trends
                }
            }
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)

@login_required
def event_calendar(request):
    """View for displaying and managing events in a calendar format"""
    try:
        # Get all events
        events = Event.objects.all().order_by('start_date', 'start_time')
        
        # Get active school year
        active_school_year = SchoolYear.get_active()
        
        # Format events for calendar display
        calendar_events = []
        for event in events:
            # Create calendar event object
            calendar_event = {
                'id': event.id,
                'title': event.title,
                'description': event.description,
                'start': event.start_date.strftime('%Y-%m-%d'),
                'end': event.end_date.strftime('%Y-%m-%d') if event.end_date else event.start_date.strftime('%Y-%m-%d'),
                'allDay': not event.start_time,  # If no start time, treat as all-day event
                'color': self.get_event_color(event),  # You can implement this method to assign colors based on event type
                'textColor': '#ffffff',  # White text for better contrast
                'borderColor': '#000000',  # Black border
                'url': reverse('dashboard:event_detail', args=[event.id])  # URL for event details
            }
            
            # Add time information if available
            if event.start_time:
                calendar_event['start'] += f"T{event.start_time.strftime('%H:%M:%S')}"
            if event.end_time:
                calendar_event['end'] += f"T{event.end_time.strftime('%H:%M:%S')}"
            
            calendar_events.append(calendar_event)
        
        context = {
            'events': events,
            'calendar_events': json.dumps(calendar_events),
            'active_school_year': active_school_year
        }
        
        return render(request, 'event_calendar.html', context)
        
    except Exception as e:
        messages.error(request, f'Error loading event calendar: {str(e)}')
        return render(request, 'event_calendar.html', {
            'events': [],
            'calendar_events': '[]',
            'active_school_year': None
        })

@login_required
def get_event_color(self, event):
    """Helper method to determine event color based on type or other criteria"""
    # You can customize this method to assign different colors based on event properties
    # For example, you could use event type, category, or other attributes
    return '#3788d8'  # Default blue color

@login_required
def event_detail(request, event_id):
    """View for displaying detailed information about a specific event"""
    try:
        event = Event.objects.get(id=event_id)
        
        context = {
            'event': event
        }
        
        return render(request, 'event_detail.html', context)
        
    except Event.DoesNotExist:
        messages.error(request, 'Event not found')
        return redirect('dashboard:event_calendar')
    except Exception as e:
        messages.error(request, f'Error loading event details: {str(e)}')
        return redirect('dashboard:event_calendar')

@login_required
def add_event(request):
    """API endpoint to add a new event"""
    if request.method == 'POST':
        try:
            # Get form data
            title = request.POST.get('title')
            description = request.POST.get('description')
            start_date = request.POST.get('start_date')
            end_date = request.POST.get('end_date')
            start_time = request.POST.get('start_time')
            end_time = request.POST.get('end_time')
            
            # Validate required fields
            if not all([title, start_date]):
                return JsonResponse({
                    'success': False,
                    'message': 'Title and start date are required'
                }, status=400)
            
            # Create new event
            event = Event.objects.create(
                title=title,
                description=description,
                start_date=datetime.strptime(start_date, '%Y-%m-%d').date(),
                end_date=datetime.strptime(end_date, '%Y-%m-%d').date() if end_date else None,
                start_time=datetime.strptime(start_time, '%H:%M').time() if start_time else None,
                end_time=datetime.strptime(end_time, '%H:%M').time() if end_time else None,
                created_by=request.user
            )
            
            # Log the activity
            log_admin_activity(
                request.user,
                f"Created new event: {event.title}",
                "event"
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Event created successfully',
                'event': {
                    'id': event.id,
                    'title': event.title,
                    'description': event.description,
                    'start_date': event.start_date.strftime('%Y-%m-%d'),
                    'end_date': event.end_date.strftime('%Y-%m-%d') if event.end_date else None,
                    'start_time': event.start_time.strftime('%H:%M') if event.start_time else None,
                    'end_time': event.end_time.strftime('%H:%M') if event.end_time else None
                }
            })
            
        except ValueError as e:
            return JsonResponse({
                'success': False,
                'message': f'Invalid date/time format: {str(e)}'
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            }, status=500)
    
    return JsonResponse({
        'success': False,
        'message': 'Invalid request method'
    }, status=405)

@login_required
def update_event(request, event_id):
    """API endpoint to update an existing event"""
    if request.method == 'POST':
        try:
            # Get the event
            try:
                event = Event.objects.get(id=event_id)
            except Event.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': 'Event not found'
                }, status=404)
            
            # Get form data
            title = request.POST.get('title')
            description = request.POST.get('description')
            start_date = request.POST.get('start_date')
            end_date = request.POST.get('end_date')
            start_time = request.POST.get('start_time')
            end_time = request.POST.get('end_time')
            
            # Update event
            if title:
                event.title = title
            if description is not None:
                event.description = description
            if start_date:
                event.start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            if end_date:
                event.end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            if start_time:
                event.start_time = datetime.strptime(start_time, '%H:%M').time()
            if end_time:
                event.end_time = datetime.strptime(end_time, '%H:%M').time()
            
            event.save()
            
            # Log the activity
            log_admin_activity(
                request.user,
                f"Updated event: {event.title}",
                "event"
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Event updated successfully',
                'event': {
                    'id': event.id,
                    'title': event.title,
                    'description': event.description,
                    'start_date': event.start_date.strftime('%Y-%m-%d'),
                    'end_date': event.end_date.strftime('%Y-%m-%d') if event.end_date else None,
                    'start_time': event.start_time.strftime('%H:%M') if event.start_time else None,
                    'end_time': event.end_time.strftime('%H:%M') if event.end_time else None
                }
            })
            
        except ValueError as e:
            return JsonResponse({
                'success': False,
                'message': f'Invalid date/time format: {str(e)}'
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            }, status=500)
    
    return JsonResponse({
        'success': False,
        'message': 'Invalid request method'
    }, status=405)

@login_required
def delete_event(request, event_id):
    """API endpoint to delete an event"""
    if request.method == 'POST':
        try:
            # Get the event
            try:
                event = Event.objects.get(id=event_id)
            except Event.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': 'Event not found'
                }, status=404)
            
            # Delete the event
            event_title = event.title
            event.delete()
            
            # Log the activity
            log_admin_activity(
                request.user,
                f"Deleted event: {event_title}",
                "event"
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Event deleted successfully'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            }, status=500)
    
    return JsonResponse({
        'success': False,
        'message': 'Invalid request method'
    }, status=405)

@login_required
def archive_data(request):
    """API endpoint to archive data for a specific school year and data type"""
    if request.method == 'POST':
        try:
            # Get form data
            school_year = request.POST.get('school_year')
            archive_type = request.POST.get('archive_type')
            
            if not school_year or not archive_type:
                return JsonResponse({
                    'success': False,
                    'message': 'School year and archive type are required'
                }, status=400)
            
            # Check if archive already exists
            existing_archive = Archive.objects.filter(
                archive_type=archive_type,
                school_year=school_year
            ).first()
            
            if existing_archive:
                return JsonResponse({
                    'success': False,
                    'message': f'An archive for {archive_type} data in {school_year} already exists'
                }, status=400)
            
            # Get data based on archive type
            data = []
            try:
                if archive_type == 'student':
                    data = list(Student.objects.filter(school_year=school_year).values())
                elif archive_type == 'teacher':
                    data = list(Teachers.objects.all().values())
                elif archive_type == 'enrollment':
                    # Handle enrollment data for all grade levels
                    enrollment_models = {
                        7: Enrollment,
                        8: Grade8Enrollment,
                        9: Grade9Enrollment,
                        10: Grade10Enrollment,
                        11: Grade11Enrollment,
                        12: Grade12Enrollment
                    }
                    for model in enrollment_models.values():
                        enrollments = model.objects.filter(school_year=school_year).select_related('student', 'section')
                        for enrollment in enrollments:
                            enrollment_data = {
                                'id': enrollment.id,
                                'student_id': enrollment.student.student_id,
                                'student_name': f"{enrollment.student.first_name} {enrollment.student.last_name}",
                                'section_id': enrollment.section.section_id,
                                'grade_level': enrollment.section.grade_level,
                                'status': enrollment.status,
                                'enrollment_date': enrollment.enrollment_date.strftime('%Y-%m-%d') if enrollment.enrollment_date else None,
                                'track': enrollment.track if hasattr(enrollment, 'track') else None
                            }
                            data.append(enrollment_data)
                elif archive_type == 'grade':
                    grades = Grades.objects.filter(school_year=school_year).select_related('student', 'subject', 'section', 'teacher')
                    for grade in grades:
                        grade_data = {
                            'id': grade.id,
                            'student_id': grade.student.student_id,
                            'student_name': f"{grade.student.first_name} {grade.student.last_name}",
                            'subject': grade.subject.name,
                            'section': grade.section.section_id,
                            'quarter': grade.quarter,
                            'grade': float(grade.grade) if grade.grade else None,
                            'status': grade.status,
                            'remarks': grade.remarks,
                            'teacher': f"{grade.teacher.first_name} {grade.teacher.last_name}" if grade.teacher else None
                        }
                        data.append(grade_data)
                elif archive_type == 'section':
                    sections = Sections.objects.select_related('adviser').all()
                    for section in sections:
                        section_data = {
                            'id': section.id,
                            'section_id': section.section_id,
                            'grade_level': section.grade_level,
                            'adviser': f"{section.adviser.first_name} {section.adviser.last_name}" if section.adviser else None
                        }
                        data.append(section_data)
                elif archive_type == 'schedule':
                    schedules = Schedules.objects.select_related('section', 'subject', 'teacher_id').all()
                    for schedule in schedules:
                        schedule_data = {
                            'id': schedule.id,
                            'section': schedule.section.section_id,
                            'subject': schedule.subject.name,
                            'teacher': f"{schedule.teacher_id.first_name} {schedule.teacher_id.last_name}",
                            'day': schedule.day,
                            'start_time': schedule.start_time.strftime('%H:%M') if schedule.start_time else None,
                            'end_time': schedule.end_time.strftime('%H:%M') if schedule.end_time else None,
                            'room': schedule.room
                        }
                        data.append(schedule_data)
                elif archive_type == 'event':
                    events = Event.objects.all()
                    for event in events:
                        event_data = {
                            'id': event.id,
                            'title': event.title,
                            'description': event.description,
                            'start_date': event.start_date.strftime('%Y-%m-%d'),
                            'end_date': event.end_date.strftime('%Y-%m-%d') if event.end_date else None,
                            'start_time': event.start_time.strftime('%H:%M') if event.start_time else None,
                            'end_time': event.end_time.strftime('%H:%M') if event.end_time else None,
                            'created_by': f"{event.created_by.first_name} {event.created_by.last_name}" if event.created_by else None
                        }
                        data.append(event_data)
                else:
                    return JsonResponse({
                        'success': False,
                        'message': 'Invalid archive type'
                    }, status=400)
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'message': f'Error fetching data: {str(e)}'
                }, status=500)
            
            if not data:
                return JsonResponse({
                    'success': False,
                    'message': f'No {archive_type} data found for {school_year}'
                }, status=400)
            
            # Process data to handle date serialization
            processed_data = []
            for item in data:
                processed_item = {}
                for key, value in item.items():
                    if isinstance(value, (date, datetime)):
                        processed_item[key] = value.isoformat()
                    elif isinstance(value, Decimal):
                        processed_item[key] = float(value)
                    else:
                        processed_item[key] = value
                processed_data.append(processed_item)
            
            # Create archive record
            try:
                with transaction.atomic():
                    archive = Archive.objects.create(
                        archive_type=archive_type,
                        school_year=school_year,
                        data=processed_data,
                        created_by=request.user
                    )
                    
                    # Log the activity
                    log_admin_activity(
                        request.user,
                        f"Created {archive_type} archive for {school_year}",
                        "archive"
                    )
                
                return JsonResponse({
                    'success': True,
                    'message': f'Successfully archived {len(processed_data)} {archive_type} records for {school_year}',
                    'archive_id': archive.id
                })
                
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'message': f'Error creating archive: {str(e)}'
                }, status=500)
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            }, status=500)
    
    return JsonResponse({
        'success': False,
        'message': 'Invalid request method'
    }, status=405)
