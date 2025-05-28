from django.shortcuts import render, redirect, get_object_or_404
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse, HttpResponseNotAllowed
import csv
import pandas as pd
from dashboard.models import (
    Student, Teachers, Subject, Sections, Schedules, 
    Enrollment, Grade8Enrollment, Grade9Enrollment,
    Grade10Enrollment, Grade11Enrollment, Grade12Enrollment,
    SchoolYear, Grades, GradeChangeLog
)
from dashboard.views import validate_grade_level_enrollment
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.contrib import messages
from datetime import datetime, timedelta
from django.db.models import Q, Count, F
from django.utils import timezone
from django.views.decorators.http import require_POST, require_http_methods
import json
import os
from django.http import HttpResponse
import pandas as pd
from io import BytesIO
import xlsxwriter
from decimal import Decimal
import io
from dashboard.models import Grades
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from dashboard.models import Event
from django.core.mail import send_mail
from django.conf import settings
import zipfile
import re

@login_required
def profile_view(request):
    """View for teacher's profile page"""
    try:
        teacher = Teachers.objects.get(user=request.user)
        school_years = SchoolYear.objects.all().order_by('-year_start')
        active_school_year = SchoolYear.get_active()
        
        selected_year = request.GET.get('school_year', 
            active_school_year.display_name if active_school_year else None)
        
        teacher_schedules = Schedules.objects.filter(
            teacher_id=teacher
        ).select_related(
            'subject',
            'section'
        )

        sections_with_students = {}
        unique_subjects = set()
        
        for schedule in teacher_schedules:
            section = schedule.section
            subject = schedule.subject
            
            if section not in sections_with_students:
                # Get enrollments based on grade level
                if section.grade_level == 7:
                    enrollments = Enrollment.objects.filter(
                        section=section,
                        school_year=selected_year,
                        status='Active'
                    ).select_related('student')
                elif section.grade_level == 8:
                    enrollments = Grade8Enrollment.objects.filter(
                        section=section,
                        school_year=selected_year,
                        status='Active'
                    ).select_related('student')
                elif section.grade_level == 9:
                    enrollments = Grade9Enrollment.objects.filter(
                        section=section,
                        school_year=selected_year,
                        status='Active'
                    ).select_related('student')
                elif section.grade_level == 10:
                    enrollments = Grade10Enrollment.objects.filter(
                        section=section,
                        school_year=selected_year,
                        status='Active'
                    ).select_related('student')
                elif section.grade_level == 11:
                    enrollments = Grade11Enrollment.objects.filter(
                        section=section,
                        school_year=selected_year,
                        status='Active'
                    ).select_related('student')
                elif section.grade_level == 12:
                    enrollments = Grade12Enrollment.objects.filter(
                        section=section,
                        school_year=selected_year,
                        status='Active'
                    ).select_related('student')
                
                sections_with_students[section] = {
                    'students': enrollments,
                    'student_count': enrollments.count(),
                    'subjects': set(),
                    'grade_level': section.grade_level
                }
            
            sections_with_students[section]['subjects'].add(subject.name)
            unique_subjects.add(subject.name)

        context = {
            'teacher': teacher,
            'unique_subjects': sorted(list(unique_subjects)),
            'sections_with_students': sections_with_students,
            'active_school_year': active_school_year,
            'school_years': school_years,
            'selected_year': selected_year
        }
        
        return render(request, 'Profile.html', context)
    except Teachers.DoesNotExist:
        messages.error(request, 'Teacher profile not found')
        return render(request, 'Profile.html', {
            'error': 'Teacher profile not found',
            'user': request.user
        })
    except Exception as e:
        print(f"Error in profile_view: {str(e)}")  # Add logging for debugging
        context = {
            'error': f'An error occurred: {str(e)}',
            'user': request.user,
            'teacher': Teachers.objects.get(user=request.user) if request.user.is_authenticated else None
        }
        return render(request, 'Profile.html', context)

@login_required
def update_profile(request):
    """Handle teacher profile updates"""
    if request.method == 'POST':
        try:
            teacher = Teachers.objects.get(user=request.user)
            
            # Update basic info
            teacher.first_name = request.POST.get('first_name')
            teacher.middle_name = request.POST.get('middle_name')
            teacher.last_name = request.POST.get('last_name')
            teacher.gender = request.POST.get('gender')
            teacher.date_of_birth = request.POST.get('date_of_birth')
            teacher.religion = request.POST.get('religion')
            
            # Update contact info
            teacher.mobile_number = request.POST.get('mobile_number')
            teacher.email = request.POST.get('email')
            teacher.address = request.POST.get('address')
            
            # Handle photo upload
            if 'teacher_photo' in request.FILES:
                teacher.teacher_photo = request.FILES['teacher_photo']
            
            teacher.save()
            messages.success(request, 'Profile updated successfully')
            
        except Teachers.DoesNotExist:
            messages.error(request, 'Teacher profile not found')
        except Exception as e:
            messages.error(request, f'Error updating profile: {str(e)}')
            
    return redirect('profile')

def logout_view(request):
    """Handle user logout"""
    logout(request)
    return redirect('login')

@login_required
def teacher_subjects_view(request):
    """View for teacher's subjects and students"""
    try:
        teacher = Teachers.objects.get(user=request.user)
        active_school_year = SchoolYear.get_active()
        
        # Get unique subjects with their sections from schedules
        schedules = Schedules.objects.filter(
            teacher_id=teacher
        ).select_related('subject', 'section').distinct()

        # Organize schedules by subject
        subjects_data = {}
        
        for schedule in schedules:
            subject_key = f"{schedule.subject.name}_{schedule.section.grade_level}_{schedule.section.section_id}"
            
            if subject_key not in subjects_data:
                subjects_data[subject_key] = {
                    'name': schedule.subject.name,
                    'subject_id': schedule.subject.subject_id,
                    'grade_level': schedule.section.grade_level,
                    'section_id': schedule.section.section_id,
                    'total_students': 0
                }

                # Get enrollment model based on grade level
                enrollment_model = {
                    7: Enrollment,
                    8: Grade8Enrollment,
                    9: Grade9Enrollment,
                    10: Grade10Enrollment,
                    11: Grade11Enrollment,
                    12: Grade12Enrollment
                }.get(schedule.section.grade_level)

                if enrollment_model:
                    total_students = enrollment_model.objects.filter(
                        section=schedule.section,
                        school_year=active_school_year.display_name
                    ).count()
                    
                    subjects_data[subject_key]['total_students'] = total_students

        # Convert dictionary to sorted list
        subjects_list = sorted(
            subjects_data.values(), 
            key=lambda x: (x['name'], x['grade_level'], x['section_id'])
        )

        # Get advisory sections
        advisory_sections = Sections.objects.filter(adviser=teacher)
        advisory_data = []

        for section in advisory_sections:
            enrollment_model = {
                7: Enrollment,
                8: Grade8Enrollment,
                9: Grade9Enrollment,
                10: Grade10Enrollment,
                11: Grade11Enrollment,
                12: Grade12Enrollment
            }.get(section.grade_level)

            if enrollment_model:
                enrollments = enrollment_model.objects.filter(
                    section=section,
                    school_year=active_school_year.display_name
                )
                
                active_count = enrollments.filter(status='Active').count()
                total_count = enrollments.count()
                
                advisory_data.append({
                    'grade_level': section.grade_level,
                    'section_id': section.section_id,
                    'active_count': active_count,
                    'pending_count': total_count - active_count,
                    'total_students': total_count
                })
        
        context = {
            'teacher': teacher,
            'active_school_year': active_school_year,
            'subjects': subjects_list,
            'advisory_sections': sorted(advisory_data, key=lambda x: (x['grade_level'], x['section_id']))
        }
        
        return render(request, 'teacher_subjects.html', context)
        
    except Exception as e:
        print(f"Error in teacher_subjects_view: {str(e)}")
        return render(request, 'teacher_subjects.html', {
            'error': f'Error: {str(e)}',
            'user': request.user
        })

@login_required
def teacher_schedule_view(request):
    """View for teacher's schedule"""
    try:
        teacher = Teachers.objects.get(user=request.user)
        active_school_year = SchoolYear.get_active()
        
        # Define time slots (remove last slot for correct pairing)
        time_slots = [
            '07:00', '08:00', '09:00', '10:00', '11:00',
            '12:00', '13:00', '14:00', '15:00', '16:00'
        ]
        
        # Get all schedules for the teacher
        schedules = Schedules.objects.filter(
            teacher_id=teacher
        ).select_related('subject', 'section').order_by('day', 'start_time')
        
        # Organize schedules by day
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        schedule_matrix = []
        
        # Create schedule matrix with time ranges
        for time in time_slots:
            start_time = datetime.strptime(time, '%H:%M')
            end_time = start_time + timedelta(hours=1)
            time_range = f"{start_time.strftime('%I:%M %p')} - {end_time.strftime('%I:%M %p')}"
            row = {
                'time': time_range,
                'slots': []
            }
            
            for day in days:
                day_schedules = schedules.filter(day=day)
                slot_schedule = None
                
                for schedule in day_schedules:
                    if schedule.start_time.strftime('%H:%M') == time:
                        slot_schedule = {
                            'subject': schedule.subject.name,
                            'grade_level': schedule.grade_level,
                            'section': schedule.section.section_id,
                            'room': schedule.room or '-'
                        }
                        break
                
                row['slots'].append(slot_schedule)
            
            schedule_matrix.append(row)
        
        context = {
            'teacher': teacher,
            'days': days,
            'schedule_matrix': schedule_matrix,
            'active_school_year': active_school_year,
            'total_subjects': schedules.values('subject').distinct().count(),
            'total_sections': schedules.values('section').distinct().count()
        }
        
        return render(request, 'teacher_schedule.html', context)
    except Exception as e:
        print(f"Error in teacher_schedule_view: {str(e)}")
        return render(request, 'teacher_schedule.html', {
            'error': f'Error: {str(e)}',
            'user': request.user
        })

@login_required
def import_grades_view(request):
    """View for grade import page"""
    try:
        teacher = Teachers.objects.get(user=request.user)
        teacher_subjects = Subject.objects.filter(
            schedules__teacher_id=teacher,
            schedules__school_year=SchoolYear.get_active().display_name
        ).distinct()
        
        context = {
            'teacher': teacher,
            'subjects': teacher_subjects
        }
        
        return render(request, 'import_grades.html', context)
    except Exception as e:
        messages.error(request, f'Error: {str(e)}')
        return redirect('profile')

@login_required
def upload_grades(request):
    """API endpoint to handle grade uploads from Excel files"""
    try:
        if request.method != 'POST':
            return JsonResponse({'error': 'Method not allowed'}, status=405)
            
        teacher = Teachers.objects.get(user=request.user)
        school_year_id = request.POST.get('school_year')
        excel_file = request.FILES.get('grades_file')
        
        if not all([school_year_id, excel_file]):
            missing = []
            if not school_year_id: missing.append('school_year')
            if not excel_file: missing.append('grades_file')
            return JsonResponse({
                'error': f'Missing required fields: {", ".join(missing)}'
            }, status=400)
            
        # Validate file type
        if not excel_file.name.endswith(('.xlsx', '.xls')):
            return JsonResponse({
                'error': 'Invalid file type. Please upload an Excel file (.xlsx or .xls)'
            }, status=400)

        # Read Excel file with no header
        try:
            df_raw = pd.read_excel(excel_file, header=None)
        except Exception as e:
            return JsonResponse({
                'error': f'Error reading Excel file: {str(e)}'
            }, status=400)

        # Extract metadata from the second row (row index 1)
        metadata_row = df_raw.iloc[1]
        quarter = str(metadata_row[0]).strip()
        subject_name = str(metadata_row[1]).strip()
        section_name = str(metadata_row[2]).strip()

        # Get the subject object
        try:
            subject = Subject.objects.get(name=subject_name)
        except Subject.DoesNotExist:
            return JsonResponse({
                'error': f'Subject "{subject_name}" not found in the system.'
            }, status=400)

        # Get the section object
        match = re.match(r"Grade (\d+) - (.+)", section_name)
        if match:
            grade_level = int(match.group(1))
            section_id = match.group(2).strip()
            try:
                section = Sections.objects.get(grade_level=grade_level, section_id=section_id)
            except Sections.DoesNotExist:
                return JsonResponse({
                    'error': f'Section with grade level {grade_level} and section id "{section_id}" not found in the system.'
                }, status=400)
        else:
            return JsonResponse({
                'error': f'Invalid section format in Excel file: {section_name}. Expected format: "Grade X - SectionName".'
            }, status=400)

        # Find the header row (the row containing 'Student ID' and 'LEARNER'S NAME')
        header_row_idx = None
        required_columns = ['Student ID', "LEARNER'S NAME"]
        for idx, row in df_raw.iterrows():
            row_values = [str(cell).strip().upper() for cell in row.values]
            if all(any(req_col.upper() == val for val in row_values) for req_col in required_columns):
                header_row_idx = idx
                break
        if header_row_idx is None:
            return JsonResponse({
                'error': f'Required columns {', '.join(required_columns)} not found in the Excel file.'
            }, status=400)

        # Re-read the Excel file with the correct header row
        try:
            df = pd.read_excel(excel_file, header=header_row_idx)
        except Exception as e:
            return JsonResponse({
                'error': f'Error re-reading Excel file: {str(e)}'
            }, status=400)

        # Validate required columns with case-insensitive comparison
        required_columns = ['Student ID', "LEARNER'S NAME"]
        found_columns = {}
        
        # Find required columns with case-insensitive comparison
        for required_col in required_columns:
            found = False
            for col in df.columns:
                if col.upper() == required_col.upper():
                    found_columns[required_col] = col
                    found = True
                    break
            if not found:
                return JsonResponse({
                    'error': f'Required column "{required_col}" not found in the Excel file. Please make sure your Excel file has the following columns: {", ".join(required_columns)}'
                }, status=400)
        
        # Find the grade column
        grade_column = None
        possible_grade_columns = [
            subject.name.upper(),  # Subject name in uppercase
            subject.name,          # Subject name as is
            subject.name.lower(),  # Subject name in lowercase
            'Grade',              # Generic grade column
            'VAL. ED.',          # Values Education specific
            'VAL ED',            # Without period
            'VAL.ED.',           # Without space
            'VALED',             # Without space and period
            'VALUES EDUCATION',  # Full name
        ]
        
        for col_name in possible_grade_columns:
            if col_name in df.columns:
                grade_column = col_name
                break
        
        if not grade_column:
            # If still not found, try to find any column containing the subject name
            for col in df.columns:
                if subject.name.upper() in col.upper():
                    grade_column = col
                    break
        
        if not grade_column:
            return JsonResponse({
                'error': 'Could not find grade column. Please make sure your Excel file has one of these columns:\n' +
                        f'- {subject.name}\n' +
                        '- Grade\n' +
                        f'Current columns in file: {", ".join(list(df.columns))}'
            }, status=400)
            
        # Process grades
        grades_data = []
        errors = []
        warnings = []
        
        for idx, row in df.iterrows():
            try:
                student_id = str(row[found_columns['Student ID']]).strip()
                student_name = str(row[found_columns["LEARNER'S NAME"]]).strip()
                grade_value = row[grade_column]
                
                # Skip empty rows
                if pd.isna(student_id) or pd.isna(grade_value):
                    continue
                    
                # Validate grade value
                try:
                    grade_value = float(grade_value)
                    if not (0 <= grade_value <= 100):
                        errors.append(f'Row {idx + 2}: Invalid grade value for student {student_id}: {grade_value}. Grade must be between 0 and 100.')
                        continue
                except ValueError:
                    errors.append(f'Row {idx + 2}: Invalid grade value for student {student_id}: {grade_value}')
                    continue

                # Get student object
                try:
                    student = Student.objects.get(student_id=student_id)
                except Student.DoesNotExist:
                    errors.append(f'Row {idx + 2}: Student with ID {student_id} not found')
                    continue

                # Get school year object
                try:
                    school_year = SchoolYear.objects.get(id=school_year_id)
                except SchoolYear.DoesNotExist:
                    return JsonResponse({
                        'error': f'School year with ID {school_year_id} not found'
                    }, status=400)

                # Get remarks if available
                remarks = ''
                if 'Remarks' in df.columns:
                    remarks = str(row['Remarks']).strip() if not pd.isna(row['Remarks']) else ''

                # Create grade data
                grade_data = {
                    'student_id': student_id,
                    'student_name': student_name,
                    'grade': grade_value,
                    'remarks': remarks
                }
                grades_data.append(grade_data)

                # Create or update grade in database
                grade, created = Grades.objects.update_or_create(
                    student=student,
                    subject=subject,
                    quarter=quarter,
                    school_year=school_year,
                    section=section,
                    teacher=teacher,
                    defaults={
                        'grade': Decimal(str(grade_value)),
                        'remarks': remarks,
                        'status': 'draft',
                        'uploaded_at': timezone.now()
                    }
                )

                # Send email notification to the student
                try:
                    subject_line = f"New Grade Uploaded: {subject.name} (Quarter {quarter})"
                    message = f"""
Hello {student.first_name},

Your grade for {subject.name} (Quarter {quarter}) has been uploaded:
Grade: {grade_value}
Remarks: {remarks or 'None'}

Please log in to your student portal to view details.

Best regards,
{teacher.first_name} {teacher.last_name}
"""
                    send_mail(
                        subject_line,
                        message,
                        settings.DEFAULT_FROM_EMAIL,
                        [student.email],
                        fail_silently=True,
                    )
                except Exception as e:
                    warnings.append(f'Failed to send email to {student.email}: {str(e)}')

            except Exception as e:
                errors.append(f'Row {idx + 2}: Error processing row: {str(e)}')

        if not grades_data:
            return JsonResponse({
                'error': 'No valid grades found in the Excel file'
            }, status=400)

        response_data = {
            'success': True,
            'message': f'Successfully processed {len(grades_data)} grades',
            'preview_data': grades_data
        }
        
        if errors:
            response_data['errors'] = errors
        if warnings:
            response_data['warnings'] = warnings

        return JsonResponse(response_data)

    except Exception as e:
        print(f"Error processing grades: {str(e)}")
        return JsonResponse({
            'error': f'Error processing grades: {str(e)}'
        }, status=500)

@login_required
def get_enrolled_students(request):
    """API endpoint to get enrolled students for a section or advisory class"""
    try:
        section_id = request.GET.get('section_id')
        is_advisory = request.GET.get('is_advisory', 'false').lower() == 'true'
        
        section = Sections.objects.get(section_id=section_id)
        
        # Get enrollment model based on grade level
        enrollment_model = {
            7: Enrollment,
            8: Grade8Enrollment,
            9: Grade9Enrollment,
            10: Grade10Enrollment,
            11: Grade11Enrollment,
            12: Grade12Enrollment
        }.get(section.grade_level)

        if enrollment_model:
            # Base query
            enrollments = enrollment_model.objects.filter(
                section=section,
                school_year=SchoolYear.get_active().display_name
            ).select_related('student')
            
            # For advisory, we want all students
            if not is_advisory:
                # For subjects, we might want to add additional filters
                subject_id = request.GET.get('subject_id')
                if subject_id:
                    enrollments = enrollments.filter(subject_id=subject_id)
            
            # Order by last name
            enrollments = enrollments.order_by('student__last_name')
        
        students_data = [{
                'student_id': enrollment.student.student_id,
                'last_name': enrollment.student.last_name,
                'first_name': enrollment.student.first_name,
                'middle_name': enrollment.student.middle_name or '',
                'gender': enrollment.student.gender,
                'status': enrollment.status
            } for enrollment in enrollments]
        
        return JsonResponse({
            'success': True,
            'students': students_data
            })
        
        return JsonResponse({
            'success': False,
            'error': 'Invalid grade level'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@require_http_methods(["POST"])
def upload_grades_ajax(request):
    try:
        # Get required fields
        subject_id = request.POST.get('subject')
        quarter = request.POST.get('quarter')
        school_year_id = request.POST.get('school_year')
        section_id = request.POST.get('section')
        excel_file = request.FILES.get('file')

        # Validate required fields
        if not all([subject_id, quarter, school_year_id, section_id, excel_file]):
            missing_fields = []
            if not subject_id: missing_fields.append('Subject')
            if not quarter: missing_fields.append('Quarter')
            if not school_year_id: missing_fields.append('School Year')
            if not section_id: missing_fields.append('Section')
            if not excel_file: missing_fields.append('Excel File')
            return JsonResponse({
                'status': 'error',
                'message': f'Missing required fields: {", ".join(missing_fields)}'
            })

        # Validate file type
        if not excel_file.name.endswith(('.xlsx', '.xls')):
            return JsonResponse({
                'status': 'error',
                'message': 'Please upload an Excel file (.xlsx or .xls)'
            })

        # Read Excel file
        df = pd.read_excel(excel_file)

        # Validate required columns
        required_columns = ['Student ID', 'Grade']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            return JsonResponse({
                'status': 'error',
                'message': f'Missing required columns: {", ".join(missing_columns)}'
            })

        # Get the teacher
        teacher = request.user.teachers

        # Process grades
        grades_data = []
        for _, row in df.iterrows():
            student_id = str(row['Student ID']).strip()
            grade_value = row['Grade']
            
            # Skip empty rows
            if pd.isna(student_id) or pd.isna(grade_value):
                continue
                
            # Validate grade value
            try:
                grade_value = float(grade_value)
                if not (0 <= grade_value <= 100):
                    return JsonResponse({
                        'status': 'error',
                        'message': f'Invalid grade value for student {student_id}: {grade_value}. Grade must be between 0 and 100.'
                    })
            except ValueError:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Invalid grade value for student {student_id}: {grade_value}'
                })

            # Get student object
            try:
                student = Student.objects.get(student_id=student_id)
            except Student.DoesNotExist:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Student with ID {student_id} not found'
                })

            # Get subject object
            try:
                subject = Subject.objects.get(id=subject_id)
            except Subject.DoesNotExist:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Subject with ID {subject_id} not found'
                })

            # Get school year object
            try:
                school_year = SchoolYear.objects.get(id=school_year_id)
            except SchoolYear.DoesNotExist:
                return JsonResponse({
                    'status': 'error',
                    'message': f'School year with ID {school_year_id} not found'
                })

            # Get section object
            try:
                section = Sections.objects.get(id=section_id)
            except Sections.DoesNotExist:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Section with ID {section_id} not found'
                })

            # Create grade data
            grade_data = {
                'student_id': student_id,
                'student_name': f"{student.last_name}, {student.first_name}",
                'grade': grade_value,
                'remarks': row.get('Remarks', '')
            }
            grades_data.append(grade_data)

            # Create or update grade in database
            grade, created = Grades.objects.update_or_create(
                student=student,
                subject=subject,
                quarter=quarter,
                school_year=school_year,
                section=section,
                teacher=teacher,
                defaults={
                    'grade': Decimal(str(grade_value)),
                    'remarks': row.get('Remarks', ''),
                    'status': 'draft',
                    'uploaded_at': timezone.now()
                }
            )

        if not grades_data:
            return JsonResponse({
                'status': 'error',
                'message': 'No valid grades found in the Excel file'
            })

        return JsonResponse({
            'status': 'success',
            'message': f'Successfully processed {len(grades_data)} grades',
            'preview_data': grades_data
        })

    except Exception as e:
        print(f"Error processing grades: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'Error processing grades: {str(e)}'
        })

@require_http_methods(["POST"])
def confirm_import_grades_ajax(request):
    """
    Confirm and process grade imports from an Excel file.
    Creates or updates grades in the dashboard's Grades model.
    """
    try:
        # Get required fields
        subject_id = request.POST.get('subject')
        quarter = request.POST.get('quarter')
        school_year_id = request.POST.get('school_year')
        section_id = request.POST.get('section')
        excel_file = request.FILES.get('excel_file')
        preview_data = request.POST.get('preview_data')

        # Validate required fields
        if not all([subject_id, quarter, school_year_id, section_id, preview_data]):
            return JsonResponse({
                'status': 'error',
                'message': 'Missing required fields'
            })

        # Get required objects
        try:
            subject = Subject.objects.get(id=subject_id)
            school_year = SchoolYear.objects.get(id=school_year_id)
            section = Sections.objects.get(id=section_id)
            teacher = request.user.teachers
        except (Subject.DoesNotExist, SchoolYear.DoesNotExist, Sections.DoesNotExist) as e:
            return JsonResponse({
                'status': 'error',
                'message': f'Required object not found: {str(e)}'
            })

        # Parse preview data
        try:
            grades_data = json.loads(preview_data)
        except json.JSONDecodeError:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid preview data format'
            })

        # Process each grade
        success_count = 0
        error_messages = []
        
        for grade_info in grades_data:
            try:
                student_id = grade_info.get('student_id')
                grade_value = grade_info.get('grade')
                remarks = grade_info.get('remarks', '')

                if not student_id or not grade_value:
                    error_messages.append(f'Missing required data for student {student_id}')
                    continue

                student = Student.objects.get(student_id=student_id)
                
                # Create or update the grade
                grade, created = Grades.objects.update_or_create(
                    student=student,
                    subject=subject,
                    quarter=quarter,
                    school_year=school_year,
                    section=section,
                    teacher=teacher,
                    defaults={
                        'grade': Decimal(str(grade_value)),
                        'remarks': remarks,
                        'status': 'submitted',
                        'excel_file': excel_file if excel_file else None,
                        'created_at': timezone.now() if created else F('created_at'),
                        'updated_at': timezone.now()
                    }
                )
                success_count += 1
                
            except Student.DoesNotExist:
                error_messages.append(f'Student with ID {student_id} not found')
            except Exception as e:
                error_messages.append(f'Error processing grade for student {student_id}: {str(e)}')

        # Clean up session data
        if 'preview_data' in request.session:
            del request.session['preview_data']

        # Return response
        if success_count > 0:
            message = f'Successfully processed {success_count} grades.'
            if error_messages:
                message += f' Errors: {", ".join(error_messages)}'
            
            return JsonResponse({
                'status': 'success',
                'message': message
            })
        else:
            return JsonResponse({
                'status': 'error',
                'message': f'Failed to process any grades. Errors: {", ".join(error_messages)}'
            })

    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'An error occurred: {str(e)}'
        })

@login_required
def generate_grade_template(request):
    """Generate an Excel template for grade upload"""
    try:
        # Get parameters
        school_year_id = request.GET.get('school_year')
        quarter = request.GET.get('quarter')
        subject_id = request.GET.get('subject')
        section_id = request.GET.get('section')
        
        # Validate parameters
        if not all([school_year_id, quarter, subject_id, section_id]):
            return JsonResponse({
                'status': 'error',
                'message': 'Missing required parameters'
            }, status=400)
            
        # Get the school year object
        try:
            school_year = SchoolYear.objects.get(id=school_year_id)
        except SchoolYear.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid school year'
            }, status=400)
            
        # Get the subject and section
        try:
            subject = Subject.objects.get(id=subject_id)
            section = Sections.objects.get(id=section_id)
        except (Subject.DoesNotExist, Sections.DoesNotExist):
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid subject or section'
            }, status=400)
            
        # Get the teacher
        teacher = Teachers.objects.get(user=request.user)
        
        # Get the schedule for this subject and section
        schedule = Schedules.objects.filter(
            teacher_id=teacher,
            subject=subject,
            section_id=section
        ).first()
        
        if not schedule:
            return JsonResponse({
                'status': 'error',
                'message': 'No schedule found for the selected criteria'
            }, status=400)
            
        # Get enrollment model based on grade level
        enrollment_model = {
            7: Enrollment,
            8: Grade8Enrollment,
            9: Grade9Enrollment,
            10: Grade10Enrollment,
            11: Grade11Enrollment,
            12: Grade12Enrollment
        }.get(section.grade_level)
        
        if not enrollment_model:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid grade level'
            }, status=400)
            
        # Get students enrolled in this section
        enrollments = enrollment_model.objects.filter(
            section=section,
            school_year=school_year.display_name,
            status__in=['Active', 'Transferee', 'Returnee']
        ).select_related('student').order_by('student__last_name')
        
        if not enrollments:
            return JsonResponse({
                'status': 'error',
                'message': 'No students found in the selected section'
            }, status=400)
            
        # Create Excel workbook in memory
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output)
        worksheet = workbook.add_worksheet('Grade Template')
        
        # Define formats
        title_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'font_size': 14
        })
        
        header_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'bg_color': '#90EE90',
            'border': 1
        })
        
        subheader_format = workbook.add_format({
            'bold': True,
            'align': 'left',
            'border': 1
        })
        
        cell_format = workbook.add_format({
            'align': 'center',
            'border': 1
        })
        
        # Set column widths
        worksheet.set_column('A:A', 15)  # Student ID
        worksheet.set_column('B:B', 30)  # LEARNER'S NAME
        worksheet.set_column('C:C', 15)  # GENDER
        worksheet.set_column('D:D', 15)  # Subject Grade
        worksheet.set_column('E:E', 30)  # Remarks
        
        # Add metadata in first row (required by upload function)
        metadata_headers = ['Quarter', 'Subject', 'Section']
        metadata_values = [quarter, subject.name, f"Grade {section.grade_level} - {section.section_id}"]
        for col, header in enumerate(metadata_headers):
            worksheet.write(0, col, header, header_format)
        for col, value in enumerate(metadata_values):
            worksheet.write(1, col, value, cell_format)

        # Add a blank row for spacing (row 2)
        # (Optional, can be omitted if not needed)

        # Add title and section info (starting from row 4)
        worksheet.merge_range('A4:F4', 'QUARTERLY ASSESSMENT REPORT', title_format)
        worksheet.merge_range('A5:F5', f'GRADE {section.grade_level} - {section.section_id}', header_format)

        # Add school year info (row 6)
        worksheet.write('A6', 'School Year:', subheader_format)
        worksheet.write('B6', school_year.display_name, cell_format)

        # Add column headers (row 7)
        headers = ['Student ID', "LEARNER'S NAME", 'GENDER', subject.name.upper(), 'Remarks']
        for col, header in enumerate(headers):
            worksheet.write(6, col, header, header_format)

        # Add student data (row 8 onwards)
        for row, enrollment in enumerate(enrollments, 7):
            student = enrollment.student
            worksheet.write(row, 0, student.student_id, cell_format)
            worksheet.write(row, 1, f"{student.last_name}, {student.first_name} {student.middle_name or ''}".upper(), cell_format)
            worksheet.write(row, 2, student.gender, cell_format)
            worksheet.write(row, 3, '', cell_format)  # Empty grade cell
            worksheet.write(row, 4, '', cell_format)  # Empty remarks cell

        # Add data validation for grade column
        worksheet.data_validation(7, 3, len(enrollments) + 6, 3, {
            'validate': 'decimal',
            'criteria': 'between',
            'minimum': 0,
            'maximum': 100,
            'input_message': 'Enter a grade between 0 and 100',
            'error_message': 'Grade must be between 0 and 100'
        })
        
        # Close the workbook
        workbook.close()
        
        # Prepare response
        output.seek(0)
        response = HttpResponse(
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
        filename = f"grade_template_{school_year.display_name}_Q{quarter}_{section.grade_level}-{section.section_id}_{subject.name}.xlsx"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
        
    except Exception as e:
        print(f"Error generating template: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'Error generating template: {str(e)}'
        }, status=500)

@login_required
def student_registration(request):
    """Handle student registration"""
    try:
        teacher = Teachers.objects.get(user=request.user)
        context = {
            'teacher': teacher,
        }
        return render(request, 'Studentregistration.html', context)
    except Exception as e:
        return render(request, 'Studentregistration.html', {
            'error': f'Error: {str(e)}',
            'user': request.user
        })

@login_required
def subject_students_view(request, subject_id, grade_level, section_id):
    """View for displaying students enrolled in a subject"""
    try:
        teacher = Teachers.objects.get(user=request.user)
        active_school_year = SchoolYear.get_active()
        
        # Get the subject
        subject = Subject.objects.get(subject_id=subject_id)
        section = Sections.objects.get(grade_level=grade_level, section_id=section_id)
        
        # Get enrollment model based on grade level
        enrollment_model = {
            7: Enrollment,
            8: Grade8Enrollment,
            9: Grade9Enrollment,
            10: Grade10Enrollment,
            11: Grade11Enrollment,
            12: Grade12Enrollment
        }.get(grade_level)

        if enrollment_model:
            enrollments = enrollment_model.objects.filter(
                section=section,
                school_year=active_school_year.display_name
            ).select_related('student').order_by('student__last_name')
            
            students_data = [{
                'student_id': enrollment.student.student_id,
                'last_name': enrollment.student.last_name,
                'first_name': enrollment.student.first_name,
                'middle_name': enrollment.student.middle_name or '',
                'gender': enrollment.student.gender,
                'status': enrollment.status
            } for enrollment in enrollments]
        else:
            students_data = []

        context = {
            'teacher': teacher,
            'subject': subject,
            'section': section,
            'students': students_data,
            'active_school_year': active_school_year,
            'total_students': len(students_data)
        }
        
        return render(request, 'subject_students.html', context)
        
    except Exception as e:
        print(f"Error in subject_students_view: {str(e)}")
        return render(request, 'subject_students.html', {
            'error': f'Error: {str(e)}',
            'user': request.user
        })

@login_required
def get_subject_students(request):
    """API endpoint to get enrolled students for a subject"""
    try:
        section_id = request.GET.get('section_id')
        subject_id = request.GET.get('subject_id')
        
        # Validate required parameters
        if not section_id or not subject_id:
            missing = []
            if not section_id: missing.append("section_id")
            if not subject_id: missing.append("subject_id")
            return JsonResponse({
                'success': False,
                'error': f'Missing required parameters: {", ".join(missing)}'
            })
        
        # Get section and subject
        try:
            section = Sections.objects.get(section_id=section_id)
            subject = Subject.objects.get(subject_id=subject_id)
        except (Sections.DoesNotExist, Subject.DoesNotExist) as e:
            return JsonResponse({
                'success': False,
                'error': f'Invalid section or subject: {str(e)}'
            })
        
        # Get enrollment model based on grade level
        enrollment_model = {
            7: Enrollment,
            8: Grade8Enrollment,
            9: Grade9Enrollment,
            10: Grade10Enrollment,
            11: Grade11Enrollment,
            12: Grade12Enrollment
        }.get(section.grade_level)

        if enrollment_model:
            # Get all enrollments for the section
            enrollments = enrollment_model.objects.filter(
                section=section,
                school_year=SchoolYear.get_active().display_name
            ).select_related('student')
            
            # Get schedules for this subject and section
            schedule = Schedules.objects.filter(
                section=section,
                subject=subject,
                teacher_id=request.user.teachers
            ).first()
            
            if schedule:
                # Order by last name
                enrollments = enrollments.order_by('student__last_name')
                
                students_data = [{
                    'student_id': enrollment.student.student_id,
                    'last_name': enrollment.student.last_name,
                    'first_name': enrollment.student.first_name,
                    'middle_name': enrollment.student.middle_name or '',
                    'gender': enrollment.student.gender,
                    'status': enrollment.status
                } for enrollment in enrollments]
                
                return JsonResponse({
                    'success': True,
                    'students': students_data,
                    'total_count': len(students_data),
                    'section_info': {
                        'grade_level': section.grade_level,
                        'section_id': section.section_id
                    },
                    'subject_info': {
                        'name': subject.name,
                        'subject_id': subject.subject_id
                    }
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'You are not authorized to view students for this subject and section'
                })
        
        return JsonResponse({
            'success': False,
            'error': 'Invalid grade level'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
def student_enrollment(request):
    """View for student enrollment page"""
    try:
        teacher = Teachers.objects.get(user=request.user)
        active_school_year = SchoolYear.get_active()
        
        if not active_school_year:
            messages.error(request, 'Enrollment is not available. No active school year.')
            return redirect('profile')
        
        context = {
            'teacher': teacher,
            'active_school_year': active_school_year,
        }
        
        if request.method == 'POST':
            try:
                student_id = request.POST.get('student_id')
                grade_level = int(request.POST.get('grade_level'))
                section_id = request.POST.get('section')
                school_year = request.POST.get('school_year')
                status = request.POST.get('status')
                
                # Verify school year matches active school year
                if school_year != active_school_year.display_name:
                    messages.error(request, 'Invalid school year. Enrollment is only allowed for the active school year.')
                    return render(request, 'Studentregistration.html', context)
                
                # Get the student
                student = Student.objects.get(student_id=student_id)
                section = Sections.objects.get(id=section_id)
                
                # Verify section grade level matches selected grade level
                if section.grade_level != grade_level:
                    messages.error(request, 'Selected section does not match the grade level.')
                    return render(request, 'Studentregistration.html', context)
                
                # Get the appropriate enrollment model
                enrollment_model = {
                    7: Enrollment,
                    8: Grade8Enrollment,
                    9: Grade9Enrollment,
                    10: Grade10Enrollment,
                    11: Grade11Enrollment,
                    12: Grade12Enrollment
                }.get(grade_level)
                
                if enrollment_model:
                    # Check if student is already enrolled
                    existing_enrollment = enrollment_model.objects.filter(
                        student=student,
                        school_year=school_year
                    ).first()
                    
                    if existing_enrollment:
                        messages.error(request, 'Student is already enrolled for this school year')
                    else:
                        # Create new enrollment
                        enrollment_model.objects.create(
                            student=student,
                            section=section,
                            school_year=school_year,
                            status=status
                        )
                        messages.success(request, 'Student enrolled successfully')
                else:
                    messages.error(request, 'Invalid grade level')
                    
            except Student.DoesNotExist:
                messages.error(request, 'Student not found')
            except Exception as e:
                messages.error(request, f'Error enrolling student: {str(e)}')
        
        return render(request, 'Studentregistration.html', context)
        
    except Exception as e:
        return render(request, 'Studentregistration.html', {
            'error': f'Error: {str(e)}',
            'user': request.user
        })

@login_required
def get_sections(request):
    """API endpoint to get sections for a grade level"""
    try:
        grade_level = request.GET.get('grade_level')
        sections = Sections.objects.filter(grade_level=grade_level)
        
        sections_data = [{
            'id': section.id,
            'section_id': section.section_id
        } for section in sections]
        
        return JsonResponse({
            'success': True,
            'sections': sections_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
def search_student(request):
    """API endpoint to search for a student"""
    try:
        student_id = request.GET.get('student_id')
        student = Student.objects.get(student_id=student_id)
        
        return JsonResponse({
            'success': True,
            'student': {
                'student_id': student.student_id,
                'first_name': student.first_name,
                'last_name': student.last_name,
                'gender': student.gender,
                'status': 'Enrolled' if student.is_enrolled else 'Not Enrolled'
            }
        })
        
    except Student.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Student not found'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
def advisory_enrollment(request):
    """View for advisory teacher enrollment page"""
    try:
        teacher = Teachers.objects.get(user=request.user)
        active_school_year = SchoolYear.get_active()
        
        if not active_school_year:
            messages.error(request, 'Enrollment is not available. No active school year.')
            return redirect('profile')
        
        # Get advisory sections for the teacher
        advisory_sections = Sections.objects.filter(adviser=teacher)
        
        if not advisory_sections.exists():
            messages.warning(request, 'You are not assigned as an adviser to any section.')
            return redirect('profile')
        
        # Get available students (not yet enrolled in any section for the active school year)
        enrolled_students = set()
        for grade_level in range(7, 13):
            enrollment_model = {
                7: Enrollment,
                8: Grade8Enrollment,
                9: Grade9Enrollment,
                10: Grade10Enrollment,
                11: Grade11Enrollment,
                12: Grade12Enrollment
            }.get(grade_level)
            
            if enrollment_model:
                enrolled_students.update(
                    enrollment_model.objects.filter(
                        school_year=active_school_year.display_name
                    ).values_list('student_id', flat=True)
                )
        
        available_students = Student.objects.exclude(id__in=enrolled_students)
        
        # Get enrollments for each advisory section
        sections_data = []
        for section in advisory_sections:
            # Get the appropriate enrollment model
            enrollment_model = {
                7: Enrollment,
                8: Grade8Enrollment,
                9: Grade9Enrollment,
                10: Grade10Enrollment,
                11: Grade11Enrollment,
                12: Grade12Enrollment
            }.get(section.grade_level)
            
            if enrollment_model:
                enrollments = enrollment_model.objects.filter(
                    section=section,
                    school_year=active_school_year.display_name
                ).select_related('student')
                
                active_students = enrollments.filter(status='Active')
                
                sections_data.append({
                    'section': section,
                    'enrollments': enrollments,
                    'active_count': active_students.count(),
                    'total_count': enrollments.count()
                })
        
        context = {
            'teacher': teacher,
            'active_school_year': active_school_year,
            'sections_data': sections_data,
            'available_students': available_students
        }
        
        if request.method == 'POST':
            try:
                student_id = request.POST.get('student_id')
                section_id = request.POST.get('section')
                
                # Get student and section
                student = Student.objects.get(student_id=student_id)
                section = Sections.objects.get(id=section_id)
                
                # Verify this is an advisory section for the teacher
                if not section.adviser or section.adviser != teacher:
                    messages.error(request, 'Invalid section. You can only enroll students in your advisory sections.')
                    return render(request, 'advisory_enrollment.html', context)
                
                # Check if student is already enrolled in any grade level for the current school year
                is_enrolled = False
                for grade_level in range(7, 13):
                    enrollment_model = {
                        7: Enrollment,
                        8: Grade8Enrollment,
                        9: Grade9Enrollment,
                        10: Grade10Enrollment,
                        11: Grade11Enrollment,
                        12: Grade12Enrollment
                    }.get(grade_level)
                    
                    if enrollment_model:
                        existing_enrollment = enrollment_model.objects.filter(
                            student=student,
                            school_year=active_school_year.display_name
                        ).first()
                        
                        if existing_enrollment:
                            is_enrolled = True
                            messages.error(request, f'Student is already enrolled in Grade {grade_level} for the current school year.')
                            break
                
                if is_enrolled:
                    return render(request, 'advisory_enrollment.html', context)
                
                # Check if student has already been enrolled in this grade level in any school year
                is_grade_valid, grade_message = validate_grade_level_enrollment(student, section.grade_level)
                if not is_grade_valid:
                    messages.error(request, grade_message)
                    return render(request, 'advisory_enrollment.html', context)
                
                # Check for failing grades in previous school year
                if section.grade_level > 7:  # Only check for grades 8 and above
                    previous_grade = section.grade_level - 1
                    previous_school_years = SchoolYear.objects.filter(
                        is_active=False
                    ).order_by('-year_start')

                    for prev_year in previous_school_years:
                        # Get grades for the previous year
                        grades = Grades.objects.filter(
                            student=student,
                            school_year=prev_year,
                            section__grade_level=previous_grade
                        )

                        if grades.exists():
                            # Check if any subject has a failing grade (below 75)
                            failing_subjects = []
                            for grade in grades:
                                if grade.grade < 75:
                                    failing_subjects.append(grade.subject.name)

                            if failing_subjects:
                                messages.error(
                                    request,
                                    f'Cannot enroll student. They have failing grades in the following subjects from Grade {previous_grade}: {", ".join(failing_subjects)}'
                                )
                                return render(request, 'advisory_enrollment.html', context)
                            break  # Stop checking other years once we find grades

                # Check student's previous enrollment grade level
                previous_grade_level = None
                previous_school_years = SchoolYear.objects.filter(
                    is_active=False
                ).order_by('-year_start')
                
                for prev_year in previous_school_years:
                    # Check each enrollment model for the previous year
                    for grade in range(7, 13):
                        enrollment_model = {
                            7: Enrollment,
                            8: Grade8Enrollment,
                            9: Grade9Enrollment,
                            10: Grade10Enrollment,
                            11: Grade11Enrollment,
                            12: Grade12Enrollment
                        }.get(grade)
                        
                        if enrollment_model:
                            prev_enrollment = enrollment_model.objects.filter(
                                student=student,
                                school_year=prev_year.display_name,
                                status='Active'
                            ).first()
                            
                            if prev_enrollment:
                                previous_grade_level = grade
                                break
                    
                    if previous_grade_level:
                        break
                
                # If student has previous enrollment, check grade level restriction
                if previous_grade_level and section.grade_level <= previous_grade_level:
                    messages.error(
                        request, 
                        f'Cannot enroll student in Grade {section.grade_level}. '
                        f'Student was previously enrolled in Grade {previous_grade_level}.'
                    )
                    return render(request, 'advisory_enrollment.html', context)
                
                # Get enrollment model for the section's grade level
                enrollment_model = {
                    7: Enrollment,
                    8: Grade8Enrollment,
                    9: Grade9Enrollment,
                    10: Grade10Enrollment,
                    11: Grade11Enrollment,
                    12: Grade12Enrollment
                }.get(section.grade_level)
                
                if enrollment_model:
                    # Create new enrollment with Active status
                    enrollment_model.objects.create(
                        student=student,
                        section=section,
                        school_year=active_school_year.display_name,
                        status='Active'
                    )
                    
                    # Update student status in Student model
                    student.status = 'Enrolled'
                    student.school_year = active_school_year.display_name
                    student.save()
                    
                    messages.success(request, 'Student enrolled successfully')
                else:
                    messages.error(request, 'Invalid grade level')
                    
            except Student.DoesNotExist:
                messages.error(request, 'Student not found')
            except Sections.DoesNotExist:
                messages.error(request, 'Invalid section')
            except Exception as e:
                messages.error(request, f'Error enrolling student: {str(e)}')
        
        return render(request, 'advisory_enrollment.html', context)
        
    except Exception as e:
        return render(request, 'advisory_enrollment.html', {
            'error': f'Error: {str(e)}',
            'user': request.user
        })

@login_required
def search_students(request):
    """API endpoint to search for students by ID or name"""
    try:
        search_query = request.GET.get('query', '').strip()
        if not search_query:
            return JsonResponse({
                'success': False,
                'error': 'Search query is required'
            })

        # Search by ID or name
        students = Student.objects.filter(
            Q(student_id__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query)
        )[:10]  # Limit to 10 results
        
        students_data = [{
            'student_id': student.student_id,
            'first_name': student.first_name,
            'last_name': student.last_name,
            'gender': student.gender,
            'student_status': student.student_status
        } for student in students]
        
        return JsonResponse({
            'success': True,
            'students': students_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
def grades_view(request):
    """Combined view for managing both subject and advisory grades"""
    try:
        teacher = Teachers.objects.get(user=request.user)
        
        # Get all school years and active school year
        school_years = SchoolYear.objects.all().order_by('-year_start')
        active_school_year = SchoolYear.get_active()
        
        # Convert school years to JSON format for JavaScript
        school_years_json = json.dumps([{
            'id': year.id,
            'display_name': year.display_name,
            'is_active': year.is_active
        } for year in school_years])
        
        # Get filter parameters with defaults
        selected_year_id = request.GET.get('school_year', str(active_school_year.id) if active_school_year else '')
        selected_quarter = request.GET.get('quarter', '')
        selected_subject_id = request.GET.get('subject', '')
        selected_section_id = request.GET.get('section', '')

        # Get the selected school year object
        selected_school_year = None
        if selected_year_id:
            try:
                selected_school_year = SchoolYear.objects.get(id=selected_year_id)
            except SchoolYear.DoesNotExist:
                selected_school_year = active_school_year

        # Get subjects assigned to this teacher through schedules
        teacher_schedules = Schedules.objects.filter(
            teacher_id=teacher
        ).select_related('subject', 'section')
        
        # Get the unique subjects from those schedules
        teacher_subjects = Subject.objects.filter(
            id__in=teacher_schedules.values_list('subject_id', flat=True)
        ).distinct().order_by('name')

        # Get all sections for the teacher
        teacher_sections = Sections.objects.filter(
            id__in=teacher_schedules.values_list('section_id', flat=True)
        ).distinct().order_by('grade_level', 'section_id')
        
        # Convert sections to JSON for JavaScript
        sections_json = json.dumps([{
            'id': section.id,
            'name': f"Grade {section.grade_level} - {section.section_id}",
            'grade_level': section.grade_level,
            'section_id': section.section_id
        } for section in teacher_sections])
        
        # Define quarter choices
        QUARTER_CHOICES = [
            ('1', 'First Quarter'),
            ('2', 'Second Quarter'),
            ('3', 'Third Quarter'),
            ('4', 'Fourth Quarter')
        ]
        
        # Initialize students list
        students = []
        
        # Fetch student grades if all filters are selected
        if all([selected_school_year, selected_quarter, selected_subject_id, selected_section_id]):
            try:
                subject = Subject.objects.get(id=selected_subject_id)
                section = Sections.objects.get(id=selected_section_id)
                
                # Get enrollment model based on grade level
                enrollment_model = {
                    7: Enrollment,
                    8: Grade8Enrollment,
                    9: Grade9Enrollment,
                    10: Grade10Enrollment,
                    11: Grade11Enrollment,
                    12: Grade12Enrollment
                }.get(section.grade_level)
                
                if enrollment_model:
                    enrollments = enrollment_model.objects.filter(
                        section=section,
                        school_year=selected_school_year.display_name,
                        status='Active'
                    ).select_related('student').order_by('student__last_name')
                    
                    # Get grades for these students
                    grades = Grades.objects.filter(
                        student__in=[e.student for e in enrollments],
                        subject=subject,
                        quarter=selected_quarter,
                        school_year=selected_school_year,
                        teacher=teacher
                    )
                    
                    # Create student list with grades
                    for enrollment in enrollments:
                        student_grade = next(
                            (grade for grade in grades if grade.student_id == enrollment.student.id),
                            None
                        )
                        
                        students.append({
                            'student_id': enrollment.student.student_id,
                            'name': f"{enrollment.student.last_name}, {enrollment.student.first_name} {enrollment.student.middle_name or ''}".strip(),
                            'grade': student_grade.grade if student_grade else None,
                            'remarks': student_grade.remarks if student_grade else None
                        })
                
            except (Subject.DoesNotExist, Sections.DoesNotExist) as e:
                messages.error(request, str(e))
        
        context = {
            'teacher': teacher,
            'active_school_year': active_school_year,
            'school_years': school_years,
            'school_years_json': school_years_json,
            'sections_json': sections_json,
            'selected_year': selected_year_id,
            'teacher_subjects': teacher_subjects,
            'teacher_sections': teacher_sections,
            'quarter_choices': QUARTER_CHOICES,
            'selected_quarter': selected_quarter,
            'selected_subject': selected_subject_id,
            'selected_section': selected_section_id,
            'students': students
        }
        
        return render(request, 'teacher_grades.html', context)
        
    except Exception as e:
        print(f"Error in grades_view: {str(e)}")
        return render(request, 'teacher_grades.html', {
            'error': f'Error: {str(e)}',
            'user': request.user
        })

@login_required
@require_POST
def update_grade(request):
    """API endpoint to update a student's grade"""
    try:
        # Get required fields
        student_id = request.POST.get('student_id')
        subject_id = request.POST.get('subject')
        school_year_id = request.POST.get('school_year')
        quarter = request.POST.get('quarter')
        section_id = request.POST.get('section')
        grade_value = request.POST.get('grade')
        remarks = request.POST.get('remarks')
        reason = request.POST.get('reason')

        # Validate required fields
        if not all([student_id, subject_id, school_year_id, quarter, section_id, grade_value, reason]):
            return JsonResponse({
                'success': False,
                'error': 'Missing required fields'
            })

        # Get the teacher
        teacher = Teachers.objects.get(user=request.user)

        # Get the student
        student = Student.objects.get(id=student_id)
        
        # Get the subject
        subject = Subject.objects.get(id=subject_id)
        
        # Get the section
        section = Sections.objects.get(id=section_id)

        # Get the school year object
        school_year = SchoolYear.objects.get(id=school_year_id)

        # Get or create the grade
        grade, created = Grades.objects.update_or_create(
            student=student,
            subject=subject,
            quarter=quarter,
            school_year=school_year,  # Now passing the SchoolYear instance
            section=section,
            defaults={
                'grade': grade_value,
                'teacher': teacher,
                'remarks': remarks,
                'status': 'draft'
            }
        )

        # Create grade change log
        GradeChangeLog.objects.create(
            grade=grade,
            old_grade=grade.grade if not created else None,
            new_grade=grade_value,
            changed_by=teacher,
            reason=reason
        )

        return JsonResponse({
            'success': True,
            'message': 'Grade updated successfully'
        })

    except Student.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Student not found'
        })
    except Subject.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Subject not found'
        })
    except Sections.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Section not found'
        })
    except SchoolYear.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'School year not found'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
def get_subjects(request):
    """API endpoint to get subjects for a teacher"""
    try:
        print("=== get_subjects called ===")
        teacher = Teachers.objects.get(user=request.user)
        school_year_id = request.GET.get('school_year')

        print(f"Teacher ID: {teacher.id}")
        print(f"School Year ID: {school_year_id}")

        if not school_year_id:
            return JsonResponse({
                'success': False,
                'error': 'School year is required'
            })

        # Get the school year object
        try:
            school_year = SchoolYear.objects.get(id=school_year_id)
            school_year_display = school_year.display_name  # Using the display_name property
            print(f"Found school year: {school_year_display}")
        except SchoolYear.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': f'School year with ID {school_year_id} not found'
            })
        
        # Get all schedules for this teacher
        schedules = Schedules.objects.filter(
            teacher_id=teacher
        ).select_related('subject', 'section')

        print(f"Found {schedules.count()} schedules")

        # Get unique subjects with their sections
        subjects_data = {}
        
        for schedule in schedules:
            subject = schedule.subject
            if subject.id not in subjects_data:
                # Count sections for this subject
                sections_count = Sections.objects.filter(
                    schedules__teacher_id=teacher,
                    schedules__subject=subject
                ).distinct().count()
                
                subjects_data[subject.id] = {
                    'id': subject.id,
                    'name': subject.name,
                    'subject_id': subject.subject_id,
                    'sections_count': sections_count
                }
                print(f"Added subject: {subject.name} with {sections_count} sections")

        # Convert to list and sort by name
        subjects = sorted(subjects_data.values(), key=lambda x: x['name'])

        print(f"Returning {len(subjects)} subjects")
        return JsonResponse({
            'success': True,
            'subjects': subjects
        })

    except Exception as e:
        print(f"Error in get_subjects: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@require_http_methods(["GET"])
def get_sections_for_subject(request):
    """Get sections for a specific subject"""
    try:
        subject_id = request.GET.get('subject_id')
        school_year_id = request.GET.get('school_year')
        
        if not subject_id or not school_year_id:
            return JsonResponse({
                'success': False,
                'error': 'Subject ID and School Year are required'
            })
            
        teacher = Teachers.objects.get(user=request.user)
        subject = Subject.objects.get(id=subject_id)
        school_year = SchoolYear.objects.get(id=school_year_id)
        
        # Get all sections where the teacher is assigned to teach this subject
        sections = Section.objects.filter(
            schedule__teacher=teacher,
            schedule__subject=subject,
            schedule__school_year=school_year
        ).distinct()
        
        sections_data = [{
            'id': section.id,
            'name': section.name,
            'enrollment_count': section.get_enrollment_count(school_year)
        } for section in sections]
        
        return JsonResponse({
            'success': True,
            'sections': sections_data
        })
        
    except Teachers.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Teacher not found'
        })
    except Subject.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Subject not found'
        })
    except SchoolYear.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'School year not found'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@require_http_methods(["POST"])
def preview_grades(request):
    """
    Preview grades from uploaded Excel file before confirming import
    """
    try:
        # Get required fields
        subject_id = request.POST.get('subject')
        quarter = request.POST.get('quarter')
        school_year_id = request.POST.get('school_year')
        section_id = request.POST.get('section')
        
        # Validate required fields
        if not all([subject_id, quarter, school_year_id, section_id]):
            return JsonResponse({
                'status': 'error',
                'message': 'Missing required fields'
            })
            
        # Get the uploaded file
        excel_file = request.FILES.get('file')
        if not excel_file:
            return JsonResponse({
                'status': 'error',
                'message': 'No file uploaded'
            })
            
        # Read Excel file
        df = pd.read_excel(excel_file)
        
        # Validate file structure
        required_columns = ['Student Name', 'Grade']
        if not all(col in df.columns for col in required_columns):
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid file format. Required columns: Student Name, Grade'
            })
            
        # Process grades data
        preview_data = []
        for _, row in df.iterrows():
            preview_data.append({
                'student_name': row['Student Name'],
                'grade': float(row['Grade'])
            })
            
        # Store preview data in session for later use
        request.session['preview_data'] = json.dumps(preview_data)
        
        return JsonResponse({
            'status': 'success',
            'data': preview_data
        })
        
    except Exception as e:
        print(f"Error previewing grades: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'Error processing file: {str(e)}'
        })

@login_required
def get_teacher_subjects(request):
    """API endpoint to get subjects for a teacher based on school year"""
    try:
        teacher = Teachers.objects.get(user=request.user)
        school_year = request.GET.get('school_year')
        
        if not school_year:
            return JsonResponse({'error': 'School year is required'}, status=400)
            
        # Get the school year object
        try:
            school_year_obj = SchoolYear.objects.get(id=school_year)
        except SchoolYear.DoesNotExist:
            return JsonResponse({'error': 'Invalid school year'}, status=400)
        
        # Get subjects from schedules
        subjects = Subject.objects.filter(
            schedules__teacher_id=teacher,
            schedules__school_year=school_year_obj.display_name
        ).distinct().order_by('name')
        
        subjects_data = [{
            'id': subject.id,
            'name': subject.name
        } for subject in subjects]
        
        return JsonResponse({'subjects': subjects_data})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def get_teacher_sections(request):
    """API endpoint to get sections for a teacher based on school year and subject"""
    try:
        teacher = Teachers.objects.get(user=request.user)
        school_year = request.GET.get('school_year')
        subject_id = request.GET.get('subject')
        
        if not all([school_year, subject_id]):
            return JsonResponse({'error': 'School year and subject are required'}, status=400)
            
        # Get the school year object
        try:
            school_year_obj = SchoolYear.objects.get(id=school_year)
        except SchoolYear.DoesNotExist:
            return JsonResponse({'error': 'Invalid school year'}, status=400)
            
        # Get sections from schedules
        sections = Sections.objects.filter(
            schedules__teacher_id=teacher,
            schedules__school_year=school_year_obj.display_name,
            schedules__subject_id=subject_id
        ).distinct().order_by('grade_level', 'section_id')
        
        sections_data = [{
            'id': section.id,
            'name': f"Grade {section.grade_level} - {section.section_id}",
            'grade_level': section.grade_level,
            'section_id': section.section_id
        } for section in sections]
        
        return JsonResponse({'sections': sections_data})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def upload_grades(request):
    """API endpoint to handle grade uploads from Excel files"""
    try:
        if request.method != 'POST':
            return JsonResponse({'error': 'Method not allowed'}, status=405)
            
        teacher = Teachers.objects.get(user=request.user)
        school_year_id = request.POST.get('school_year')
        excel_file = request.FILES.get('grades_file')
        
        if not all([school_year_id, excel_file]):
            missing = []
            if not school_year_id: missing.append('school_year')
            if not excel_file: missing.append('grades_file')
            return JsonResponse({
                'error': f'Missing required fields: {", ".join(missing)}'
            }, status=400)
            
        # Validate file type
        if not excel_file.name.endswith(('.xlsx', '.xls')):
            return JsonResponse({
                'error': 'Invalid file type. Please upload an Excel file (.xlsx or .xls)'
            }, status=400)

        # Read Excel file with no header
        try:
            df_raw = pd.read_excel(excel_file, header=None)
        except Exception as e:
            return JsonResponse({
                'error': f'Error reading Excel file: {str(e)}'
            }, status=400)

        # Extract metadata from the second row (row index 1)
        metadata_row = df_raw.iloc[1]
        quarter = str(metadata_row[0]).strip()
        subject_name = str(metadata_row[1]).strip()
        section_name = str(metadata_row[2]).strip()

        # Get the subject object
        try:
            subject = Subject.objects.get(name=subject_name)
        except Subject.DoesNotExist:
            return JsonResponse({
                'error': f'Subject "{subject_name}" not found in the system.'
            }, status=400)

        # Get the section object
        match = re.match(r"Grade (\d+) - (.+)", section_name)
        if match:
            grade_level = int(match.group(1))
            section_id = match.group(2).strip()
            try:
                section = Sections.objects.get(grade_level=grade_level, section_id=section_id)
            except Sections.DoesNotExist:
                return JsonResponse({
                    'error': f'Section with grade level {grade_level} and section id "{section_id}" not found in the system.'
                }, status=400)
        else:
            return JsonResponse({
                'error': f'Invalid section format in Excel file: {section_name}. Expected format: "Grade X - SectionName".'
            }, status=400)

        # Find the header row (the row containing 'Student ID' and 'LEARNER'S NAME')
        header_row_idx = None
        required_columns = ['Student ID', "LEARNER'S NAME"]
        for idx, row in df_raw.iterrows():
            row_values = [str(cell).strip().upper() for cell in row.values]
            if all(any(req_col.upper() == val for val in row_values) for req_col in required_columns):
                header_row_idx = idx
                break
        if header_row_idx is None:
            return JsonResponse({
                'error': f'Required columns {', '.join(required_columns)} not found in the Excel file.'
            }, status=400)

        # Re-read the Excel file with the correct header row
        try:
            df = pd.read_excel(excel_file, header=header_row_idx)
        except Exception as e:
            return JsonResponse({
                'error': f'Error re-reading Excel file: {str(e)}'
            }, status=400)

        # Validate required columns with case-insensitive comparison
        required_columns = ['Student ID', "LEARNER'S NAME"]
        found_columns = {}
        
        # Find required columns with case-insensitive comparison
        for required_col in required_columns:
            found = False
            for col in df.columns:
                if col.upper() == required_col.upper():
                    found_columns[required_col] = col
                    found = True
                    break
            if not found:
                return JsonResponse({
                    'error': f'Required column "{required_col}" not found in the Excel file. Please make sure your Excel file has the following columns: {", ".join(required_columns)}'
                }, status=400)
        
        # Find the grade column
        grade_column = None
        possible_grade_columns = [
            subject.name.upper(),  # Subject name in uppercase
            subject.name,          # Subject name as is
            subject.name.lower(),  # Subject name in lowercase
            'Grade',              # Generic grade column
            'VAL. ED.',          # Values Education specific
            'VAL ED',            # Without period
            'VAL.ED.',           # Without space
            'VALED',             # Without space and period
            'VALUES EDUCATION',  # Full name
        ]
        
        for col_name in possible_grade_columns:
            if col_name in df.columns:
                grade_column = col_name
                break
        
        if not grade_column:
            # If still not found, try to find any column containing the subject name
            for col in df.columns:
                if subject.name.upper() in col.upper():
                    grade_column = col
                    break
        
        if not grade_column:
            return JsonResponse({
                'error': 'Could not find grade column. Please make sure your Excel file has one of these columns:\n' +
                        f'- {subject.name}\n' +
                        '- Grade\n' +
                        f'Current columns in file: {", ".join(list(df.columns))}'
            }, status=400)
            
        # Process grades
        grades_data = []
        errors = []
        warnings = []
        
        for idx, row in df.iterrows():
            try:
                student_id = str(row[found_columns['Student ID']]).strip()
                student_name = str(row[found_columns["LEARNER'S NAME"]]).strip()
                grade_value = row[grade_column]
                
                # Skip empty rows
                if pd.isna(student_id) or pd.isna(grade_value):
                    continue
                    
                # Validate grade value
                try:
                    grade_value = float(grade_value)
                    if not (0 <= grade_value <= 100):
                        errors.append(f'Row {idx + 2}: Invalid grade value for student {student_id}: {grade_value}. Grade must be between 0 and 100.')
                        continue
                except ValueError:
                    errors.append(f'Row {idx + 2}: Invalid grade value for student {student_id}: {grade_value}')
                    continue

                # Get student object
                try:
                    student = Student.objects.get(student_id=student_id)
                except Student.DoesNotExist:
                    errors.append(f'Row {idx + 2}: Student with ID {student_id} not found')
                    continue

                # Get school year object
                try:
                    school_year = SchoolYear.objects.get(id=school_year_id)
                except SchoolYear.DoesNotExist:
                    return JsonResponse({
                        'error': f'School year with ID {school_year_id} not found'
                    }, status=400)

                # Get remarks if available
                remarks = ''
                if 'Remarks' in df.columns:
                    remarks = str(row['Remarks']).strip() if not pd.isna(row['Remarks']) else ''

                # Create grade data
                grade_data = {
                    'student_id': student_id,
                    'student_name': student_name,
                    'grade': grade_value,
                    'remarks': remarks
                }
                grades_data.append(grade_data)

                # Create or update grade in database
                grade, created = Grades.objects.update_or_create(
                    student=student,
                    subject=subject,
                    quarter=quarter,
                    school_year=school_year,
                    section=section,
                    teacher=teacher,
                    defaults={
                        'grade': Decimal(str(grade_value)),
                        'remarks': remarks,
                        'status': 'draft',
                        'uploaded_at': timezone.now()
                    }
                )

                # Send email notification to the student
                try:
                    subject_line = f"New Grade Uploaded: {subject.name} (Quarter {quarter})"
                    message = f"""
Hello {student.first_name},

Your grade for {subject.name} (Quarter {quarter}) has been uploaded:
Grade: {grade_value}
Remarks: {remarks or 'None'}

Please log in to your student portal to view details.

Best regards,
{teacher.first_name} {teacher.last_name}
"""
                    send_mail(
                        subject_line,
                        message,
                        settings.DEFAULT_FROM_EMAIL,
                        [student.email],
                        fail_silently=True,
                    )
                except Exception as e:
                    warnings.append(f'Failed to send email to {student.email}: {str(e)}')

            except Exception as e:
                errors.append(f'Row {idx + 2}: Error processing row: {str(e)}')

        if not grades_data:
            return JsonResponse({
                'error': 'No valid grades found in the Excel file'
            }, status=400)

        response_data = {
            'success': True,
            'message': f'Successfully processed {len(grades_data)} grades',
            'preview_data': grades_data
        }
        
        if errors:
            response_data['errors'] = errors
        if warnings:
            response_data['warnings'] = warnings

        return JsonResponse(response_data)

    except Exception as e:
        print(f"Error processing grades: {str(e)}")
        return JsonResponse({
            'error': f'Error processing grades: {str(e)}'
        }, status=500)

@login_required
def account_settings(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Important!
            messages.success(request, 'Your password was successfully updated!')
            return redirect('TeacherPortal:account_settings')
        else:
            messages.error(request, 'Please correct the error below.')
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'Account.html', {'form': form})

@login_required
def registrar(request):
    """View for registrar dashboard"""
    try:
        # Get all school years ordered by start year
        school_years = SchoolYear.objects.all().order_by('-year_start')
        
        # Get active school year
        active_school_year = SchoolYear.get_active()
        
        # Get all sections
        sections = Sections.objects.all().order_by('grade_level', 'section_id')
        
        context = {
            'school_years': school_years,
            'active_school_year': active_school_year,
            'sections': sections
        }
        return render(request, 'Registrar.html', context)
    except Exception as e:
        print(f"Error in registrar view: {str(e)}")
        return render(request, 'Registrar.html', {
            'error': f'Error: {str(e)}'
        })

@login_required
def registrar_dashboard(request):
    return render(request, 'Registrar.html')

@login_required
def get_student_grades(request):
    """API endpoint to get all student grades for the registrar, grouped by school year and grade level"""
    try:
        student_id = request.GET.get('student_id')
        if not student_id:
            return JsonResponse({'success': False, 'error': 'Student ID is required'})

        # Get the student
        try:
            student = Student.objects.get(student_id=student_id)
        except Student.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Student not found'})

        # Get all enrollments for this student
        enrollments = []
        for model in [Enrollment, Grade8Enrollment, Grade9Enrollment, Grade10Enrollment, Grade11Enrollment, Grade12Enrollment]:
            enrollments += list(model.objects.filter(student=student))

        # Group by school year and grade level
        results = {}
        from dashboard.models import SchoolYear
        for enrollment in enrollments:
            key = (enrollment.school_year, enrollment.section.grade_level)
            if key not in results:
                results[key] = {
                    'school_year': enrollment.school_year,
                    'grade_level': enrollment.section.grade_level,
                    'section': enrollment.section.section_id,
                    'grades': []
                }
            # Find the SchoolYear object matching the enrollment's school_year string
            try:
                year_start, year_end = map(int, enrollment.school_year.split('-'))
                school_year_obj = SchoolYear.objects.filter(year_start=year_start, year_end=year_end).first()
            except Exception:
                school_year_obj = None
            if not school_year_obj:
                continue  # skip if not found
            # Get grades for this enrollment
            grades = Grades.objects.filter(
                student=student,
                school_year=school_year_obj,
                section=enrollment.section
            ).select_related('subject')
            for grade in grades:
                results[key]['grades'].append({
                    'subject': grade.subject.name,
                    'quarter': grade.quarter,
                    'grade': float(grade.grade)
                })

        # Convert results to a list for JSON
        data = list(results.values())
        return JsonResponse({'success': True, 'student': {
            'name': f'{student.last_name}, {student.first_name}',
            'student_id': student.student_id
        }, 'records': data})
    except Exception as e:
        print(f"Error in get_student_grades: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def teacher_events_api(request):
    events = Event.objects.all().order_by('start_date')
    events_data = [{
        'id': event.id,
        'title': event.title,
        'start': event.start_date.strftime('%Y-%m-%d'),
        'end': event.end_date.strftime('%Y-%m-%d') if event.end_date else event.start_date.strftime('%Y-%m-%d'),
        'description': event.description,
    } for event in events]
    return JsonResponse({'events': events_data})


@login_required
def teacher_calendar_view(request):
    """View for displaying the school events calendar"""
    try:
        teacher = Teachers.objects.get(user=request.user)
        context = {
            'teacher': teacher,
        }
        return render(request, 'teacher_calendar.html', context)
    except Exception as e:
        print(f"Error in teacher_calendar_view: {str(e)}")
        return render(request, 'teacher_calendar.html', {
            'error': f'Error: {str(e)}',
            'user': request.user
        })

@login_required
def get_grades(request):
    """API endpoint to get grades for the table"""
    try:
        teacher = Teachers.objects.get(user=request.user)
        
        # Get filter parameters
        school_year_id = request.GET.get('school_year')
        quarter = request.GET.get('quarter')
        subject_id = request.GET.get('subject')
        section_id = request.GET.get('section')
        
        if not all([school_year_id, quarter, subject_id, section_id]):
            return JsonResponse({
                'success': False,
                'error': 'Missing required parameters'
            })
            
        # Get the school year object
        try:
            school_year = SchoolYear.objects.get(id=school_year_id)
        except SchoolYear.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Invalid school year'
            })
            
        # Get the subject and section
        try:
            subject = Subject.objects.get(id=subject_id)
            section = Sections.objects.get(id=section_id)
        except (Subject.DoesNotExist, Sections.DoesNotExist):
            return JsonResponse({
                'success': False,
                'error': 'Invalid subject or section'
            })
            
        # Get enrollment model based on grade level
        enrollment_model = {
            7: Enrollment,
            8: Grade8Enrollment,
            9: Grade9Enrollment,
            10: Grade10Enrollment,
            11: Grade11Enrollment,
            12: Grade12Enrollment
        }.get(section.grade_level)
        
        if not enrollment_model:
            return JsonResponse({
                'success': False,
                'error': 'Invalid grade level'
            })
            
        # Get all enrolled students
        enrollments = enrollment_model.objects.filter(
            section=section,
            school_year=school_year.display_name,
            status__in=['Active', 'Transferee', 'Returnee']
        ).select_related('student').order_by('student__last_name')
        
        # Get grades for these students
        grades = Grades.objects.filter(
            student__in=[e.student for e in enrollments],
            subject=subject,
            quarter=quarter,
            school_year=school_year,
            teacher=teacher
        )
        
        # Create response data
        grades_data = []
        for enrollment in enrollments:
            student_grade = next(
                (grade for grade in grades if grade.student_id == enrollment.student.id),
                None
            )
            
            grades_data.append({
                'id': student_grade.id if student_grade else None,
                'student': {
                    'id': enrollment.student.id,
                    'student_id': enrollment.student.student_id,
                    'first_name': enrollment.student.first_name,
                    'last_name': enrollment.student.last_name
                },
                'grade': float(student_grade.grade) if student_grade and student_grade.grade else None,
                'remarks': student_grade.remarks if student_grade else None,
                'subject': {
                    'id': subject.id,
                    'name': subject.name
                },
                'school_year': {
                    'id': school_year.id,
                    'display_name': school_year.display_name
                },
                'section': {
                    'id': section.id,
                    'name': f"Grade {section.grade_level} - {section.section_id}"
                },
                'quarter': quarter
            })
            
        return JsonResponse({
            'success': True,
            'grades': grades_data
        })
        
    except Exception as e:
        print(f"Error in get_grades: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
def get_all_subjects_sections(request):
    """API endpoint to get all subjects and sections for a teacher in a given school year and quarter"""
    try:
        teacher = Teachers.objects.get(user=request.user)
        school_year_id = request.GET.get('school_year')
        quarter = request.GET.get('quarter')

        if not all([school_year_id, quarter]):
            return JsonResponse({
                'success': False,
                'error': 'School year and quarter are required'
            })

        # Get the school year object
        try:
            school_year = SchoolYear.objects.get(id=school_year_id)
        except SchoolYear.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Invalid school year'
            })

        # Get all schedules for this teacher
        schedules = Schedules.objects.filter(
            teacher_id=teacher,
            school_year=school_year.display_name
        ).select_related('subject', 'section').distinct()

        # Organize data by subject and section
        subjects_sections = []
        for schedule in schedules:
            subject = schedule.subject
            section = schedule.section

            # Get enrollment model based on grade level
            enrollment_model = {
                7: Enrollment,
                8: Grade8Enrollment,
                9: Grade9Enrollment,
                10: Grade10Enrollment,
                11: Grade11Enrollment,
                12: Grade12Enrollment
            }.get(section.grade_level)

            if enrollment_model:
                # Get enrollment count
                enrollment_count = enrollment_model.objects.filter(
                    section=section,
                    school_year=school_year.display_name,
                    status='Active'
                ).count()

                # Check if this subject-section combination already exists
                existing_entry = next(
                    (entry for entry in subjects_sections 
                     if entry['subject']['id'] == subject.id 
                     and entry['section']['id'] == section.id),
                    None
                )

                if not existing_entry:
                    subjects_sections.append({
                        'subject': {
                            'id': subject.id,
                            'name': subject.name,
                            'subject_id': subject.subject_id
                        },
                        'section': {
                            'id': section.id,
                            'name': f"Grade {section.grade_level} - {section.section_id}",
                            'grade_level': section.grade_level,
                            'section_id': section.section_id,
                            'student_count': enrollment_count
                        }
                    })

        return JsonResponse({
            'success': True,
            'subjects_sections': subjects_sections,
            'total_combinations': len(subjects_sections)
        })

    except Exception as e:
        print(f"Error in get_all_subjects_sections: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
def generate_all_templates(request):
    """Generate a zip file containing all grade templates for a teacher"""
    try:
        teacher = Teachers.objects.get(user=request.user)
        school_year_id = request.GET.get('school_year')
        quarter = request.GET.get('quarter')

        if not all([school_year_id, quarter]):
            return JsonResponse({
                'success': False,
                'error': 'School year and quarter are required'
            })

        # Get the school year object
        try:
            school_year = SchoolYear.objects.get(id=school_year_id)
        except SchoolYear.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Invalid school year'
            })

        # Get all unique subject-section combinations for this teacher
        teacher_schedules = Schedules.objects.filter(
            teacher_id=teacher
        ).select_related('subject', 'section').distinct()

        # Create a set to track unique subject-section combinations
        processed_combinations = set()

        # Create a BytesIO object to store the zip file
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for schedule in teacher_schedules:
                subject = schedule.subject
                section = schedule.section
                
                # Create a unique key for this subject-section combination
                combination_key = f"{subject.id}_{section.id}"
                
                # Skip if we've already processed this combination
                if combination_key in processed_combinations:
                    continue
                    
                processed_combinations.add(combination_key)

                # Get enrollment model based on grade level
                enrollment_model = {
                    7: Enrollment,
                    8: Grade8Enrollment,
                    9: Grade9Enrollment,
                    10: Grade10Enrollment,
                    11: Grade11Enrollment,
                    12: Grade12Enrollment
                }.get(section.grade_level)

                if enrollment_model:
                    # Get enrolled students
                    enrollments = enrollment_model.objects.filter(
                        section=section,
                        school_year=school_year.display_name,
                        status__in=['Active', 'Transferee', 'Returnee']
                    ).select_related('student').order_by('student__last_name')

                    if enrollments:
                        # Create Excel workbook for this template
                        output = BytesIO()
                        workbook = xlsxwriter.Workbook(output)
                        worksheet = workbook.add_worksheet('Grade Template')

                        # Define formats
                        title_format = workbook.add_format({
                            'bold': True,
                            'align': 'center',
                            'font_size': 14
                        })
                        header_format = workbook.add_format({
                            'bold': True,
                            'align': 'center',
                            'bg_color': '#90EE90',
                            'border': 1
                        })
                        subheader_format = workbook.add_format({
                            'bold': True,
                            'align': 'left',
                            'border': 1
                        })
                        cell_format = workbook.add_format({
                            'align': 'center',
                            'border': 1
                        })

                        # Set column widths
                        worksheet.set_column('A:A', 15)  # Student ID
                        worksheet.set_column('B:B', 30)  # LEARNER'S NAME
                        worksheet.set_column('C:C', 15)  # GENDER
                        worksheet.set_column('D:D', 15)  # Subject Grade
                        worksheet.set_column('E:E', 30)  # Remarks

                        # Add metadata in first row (required by upload function)
                        metadata_headers = ['Quarter', 'Subject', 'Section']
                        metadata_values = [quarter, subject.name, f"Grade {section.grade_level} - {section.section_id}"]
                        for col, header in enumerate(metadata_headers):
                            worksheet.write(0, col, header, header_format)
                        for col, value in enumerate(metadata_values):
                            worksheet.write(1, col, value, cell_format)

                        # Add title and section info (starting from row 4)
                        worksheet.merge_range('A4:F4', 'QUARTERLY ASSESSMENT REPORT', title_format)
                        worksheet.merge_range('A5:F5', f'GRADE {section.grade_level} - {section.section_id}', header_format)

                        # Add school year info (row 6)
                        worksheet.write('A6', 'School Year:', subheader_format)
                        worksheet.write('B6', school_year.display_name, cell_format)

                        # Add column headers (row 7)
                        headers = ['Student ID', "LEARNER'S NAME", 'GENDER', subject.name.upper(), 'Remarks']
                        for col, header in enumerate(headers):
                            worksheet.write(6, col, header, header_format)

                        # Add student data (row 8 onwards)
                        for row, enrollment in enumerate(enrollments, 7):
                            student = enrollment.student
                            worksheet.write(row, 0, student.student_id, cell_format)
                            worksheet.write(row, 1, f"{student.last_name}, {student.first_name} {student.middle_name or ''}".upper(), cell_format)
                            worksheet.write(row, 2, student.gender, cell_format)
                            worksheet.write(row, 3, '', cell_format)  # Empty grade cell
                            worksheet.write(row, 4, '', cell_format)  # Empty remarks cell

                        # Add data validation for grade column
                        worksheet.data_validation(7, 3, len(enrollments) + 6, 3, {
                            'validate': 'decimal',
                            'criteria': 'between',
                            'minimum': 0,
                            'maximum': 100,
                            'input_message': 'Enter a grade between 0 and 100',
                            'error_message': 'Grade must be between 0 and 100'
                        })

                        # Close the workbook
                        workbook.close()
                        output.seek(0)

                        # Add to zip file
                        filename = f"grade_template_{school_year.display_name}_Q{quarter}_{section.grade_level}-{section.section_id}_{subject.name}.xlsx"
                        zip_file.writestr(filename, output.getvalue())

        # Prepare response
        zip_buffer.seek(0)
        response = HttpResponse(
            zip_buffer.read(),
            content_type='application/zip'
        )
        
        response['Content-Disposition'] = f'attachment; filename="grade_templates_{school_year.display_name}_Q{quarter}.zip"'
        return response

    except Exception as e:
        print(f"Error generating templates: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': f'Error generating templates: {str(e)}'
        }, status=500)

@login_required
def get_section_grades(request):
    """API endpoint to get all students and their grades for a section"""
    try:
        teacher = Teachers.objects.get(user=request.user)
        
        # Get filter parameters
        school_year_id = request.GET.get('school_year')
        quarter = request.GET.get('quarter')
        subject_id = request.GET.get('subject')
        section_id = request.GET.get('section')
        
        if not all([school_year_id, quarter, subject_id, section_id]):
            return JsonResponse({
                'success': False,
                'error': 'Missing required parameters'
            })
            
        # Get the school year object
        try:
            school_year = SchoolYear.objects.get(id=school_year_id)
        except SchoolYear.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Invalid school year'
            })
            
        # Get the subject and section
        try:
            subject = Subject.objects.get(id=subject_id)
            section = Sections.objects.get(id=section_id)
        except (Subject.DoesNotExist, Sections.DoesNotExist):
            return JsonResponse({
                'success': False,
                'error': 'Invalid subject or section'
            })
            
        # Get enrollment model based on grade level
        enrollment_model = {
            7: Enrollment,
            8: Grade8Enrollment,
            9: Grade9Enrollment,
            10: Grade10Enrollment,
            11: Grade11Enrollment,
            12: Grade12Enrollment
        }.get(section.grade_level)
        
        if not enrollment_model:
            return JsonResponse({
                'success': False,
                'error': 'Invalid grade level'
            })
            
        # Get all enrolled students
        enrollments = enrollment_model.objects.filter(
            section=section,
            school_year=school_year.display_name,
            status__in=['Active', 'Transferee', 'Returnee']
        ).select_related('student').order_by('student__last_name')
        
        # Get grades for these students
        grades = Grades.objects.filter(
            student__in=[e.student for e in enrollments],
            subject=subject,
            quarter=quarter,
            school_year=school_year,
            teacher=teacher
        )
        
        # Create response data
        students_data = []
        for enrollment in enrollments:
            student_grade = next(
                (grade for grade in grades if grade.student_id == enrollment.student.id),
                None
            )
            
            students_data.append({
                'id': enrollment.student.id,
                'student_id': enrollment.student.student_id,
                'first_name': enrollment.student.first_name,
                'last_name': enrollment.student.last_name,
                'grade': float(student_grade.grade) if student_grade and student_grade.grade else None,
                'remarks': student_grade.remarks if student_grade else None
            })
            
        return JsonResponse({
            'success': True,
            'students': students_data
        })
        
    except Exception as e:
        print(f"Error in get_section_grades: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })
    