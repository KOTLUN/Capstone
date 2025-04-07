from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
import csv
import pandas as pd
from .models import Grade
from dashboard.models import (
    Student, Teachers, Subject, Sections, Schedules, 
    Enrollment, Grade8Enrollment, Grade9Enrollment,
    Grade10Enrollment, Grade11Enrollment, Grade12Enrollment,
    SchoolYear
)
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.contrib import messages
from datetime import datetime
from django.db.models import Q
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.core.files.storage import default_storage
import json
import os

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
        
        # Define time slots
        time_slots = [
            '07:00', '08:00', '09:00', '10:00', '11:00',
            '12:00', '13:00', '14:00', '15:00', '16:00', '17:00'
        ]
        
        # Get all schedules for the teacher
        schedules = Schedules.objects.filter(
            teacher_id=teacher
        ).select_related('subject', 'section').order_by('day', 'start_time')
        
        # Organize schedules by day
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        schedule_matrix = []
        
        # Create schedule matrix
        for time in time_slots:
            row = {
                'time': datetime.strptime(time, '%H:%M').strftime('%I:%M %p'),
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
            schedules__teacher_id=teacher
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
    """Handle grade file uploads"""
    if request.method == 'POST':
        try:
            # Process grade upload
            file = request.FILES['grades_file']
            subject_id = request.POST.get('subject')
            quarter = request.POST.get('quarter')
            school_year = request.POST.get('school_year')
            
            # Process Excel file
            df = pd.read_excel(file)
            
            # Validate and save grades
            # Add your grade processing logic here
            
            messages.success(request, 'Grades uploaded successfully')
            return redirect('import_grades')
            
        except Exception as e:
            messages.error(request, f'Error uploading grades: {str(e)}')
            return redirect('import_grades')
    
    return redirect('import_grades')

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

@login_required
@require_POST
def upload_grades_ajax(request):
    """Handle AJAX grade file uploads and return preview"""
    try:
        file = request.FILES.get('grades_file')
        subject_id = request.POST.get('subject')
        quarter = request.POST.get('quarter')
        school_year = request.POST.get('school_year')

        if not all([file, subject_id, quarter, school_year]):
            return JsonResponse({
                'status': 'error',
                'message': 'Missing required fields'
            })

        # Get subject info
        subject = Subject.objects.get(id=subject_id)

        # Read Excel file
        df = pd.read_excel(file)
        
        # Basic validation
        if df.empty:
            return JsonResponse({
                'status': 'error',
                'message': 'File is empty'
            })

        # Store file temporarily for processing
        temp_file_path = default_storage.save(
            f'temp_grades/{file.name}',
            file
        )

        # Store file path in session for later processing
        request.session['temp_grade_file'] = temp_file_path
        request.session['grade_import_data'] = {
            'subject_id': subject_id,
            'quarter': quarter,
            'school_year': school_year
        }

        return JsonResponse({
            'status': 'success',
            'subject_name': subject.name,
            'count': len(df),
            'preview_data': df.head(5).to_dict('records')
        })

    except Subject.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Subject not found'
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        })

@login_required
@require_POST
def confirm_import_grades_ajax(request):
    """Process the uploaded grades file after preview confirmation"""
    try:
        # Get stored file path and import data
        temp_file_path = request.session.get('temp_grade_file')
        import_data = request.session.get('grade_import_data')

        if not temp_file_path or not import_data:
            return JsonResponse({
                'status': 'error',
                'message': 'No file to process'
            })

        # Read the stored Excel file
        df = pd.read_excel(default_storage.path(temp_file_path))

        # Get import parameters
        subject = Subject.objects.get(id=import_data['subject_id'])
        quarter = import_data['quarter']
        school_year = import_data['school_year']

        # Process grades
        grades_created = 0
        for _, row in df.iterrows():
            student_id = str(row.get('Student ID'))
            grade_value = row.get('Grade')

            if pd.isna(grade_value) or pd.isna(student_id):
                continue

            # Create or update grade
            Grade.objects.update_or_create(
                student=student_id,
                course=subject.subject_id,
                quarter=quarter,
                school_year=school_year,
                defaults={'grade': float(grade_value)}
            )
            grades_created += 1

        # Clean up
        default_storage.delete(temp_file_path)
        del request.session['temp_grade_file']
        del request.session['grade_import_data']

        return JsonResponse({
            'status': 'success',
            'count': grades_created,
            'message': f'Successfully imported {grades_created} grades'
        })

    except Exception as e:
        # Clean up on error
        if temp_file_path:
            default_storage.delete(temp_file_path)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        })

@login_required
def generate_grade_template(request):
    """Generate Excel template for grade uploads"""
    try:
        subject_id = request.GET.get('subject')
        quarter = request.GET.get('quarter')
        school_year = request.GET.get('school_year')

        if not all([subject_id, quarter, school_year]):
            return JsonResponse({
                'status': 'error',
                'message': 'Missing required parameters'
            })

        subject = Subject.objects.get(id=subject_id)
        teacher = Teachers.objects.get(user=request.user)

        # Get students for this subject
        students = []
        schedules = Schedules.objects.filter(
            subject=subject,
            teacher_id=teacher
        )

        for schedule in schedules:
            students.extend(schedule.get_enrolled_students())

        # Create template data
        template_data = [['Student ID', 'Student Name', 'Grade']]
        for student in students:
            template_data.append([
                student.student_id,
                f"{student.last_name}, {student.first_name}",
                ''  # Empty grade column
            ])

        return JsonResponse({
            'status': 'success',
            'subject_name': subject.name,
            'quarter': quarter,
            'school_year': school_year,
            'template_data': template_data,
            'students': [{'student_name': f"{s.last_name}, {s.first_name}"} for s in students]
        })

    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        })

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
        
        section = Sections.objects.get(section_id=section_id)
        subject = Subject.objects.get(subject_id=subject_id)
        
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
                subject=subject
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
                    'students': students_data
                })
            
        return JsonResponse({
            'success': False,
            'error': 'No students found for this subject'
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
                section = Sections.objects.get(id=section_id, adviser=teacher)
                
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
                    # Check if student is already enrolled
                    existing_enrollment = enrollment_model.objects.filter(
                        student=student,
                        school_year=active_school_year.display_name
                    ).first()
                    
                    if existing_enrollment:
                        messages.error(request, 'Student is already enrolled for this school year')
                    else:
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
            'status': student.status
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

