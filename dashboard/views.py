from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Student, Teachers, Subject, Schedules, Sections, Enrollment, StudentAccount, Guardian, Grades, DroppedStudent, TransferredStudent, CompletedStudent
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.db.models import Count
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
from django.db.models import Avg


# Create your views here.
def dashboard_view(request):
    # Get selected school year from request, default to current year
    current_year = datetime.now().year
    default_school_year = f"{current_year}-{current_year+1}"
    selected_school_year = request.GET.get('school_year', default_school_year)

    # Get total number of enrolled students for selected school year
    total_students = Enrollment.objects.filter(
        school_year=selected_school_year,
        status='Active'
    ).count()
    
    # Calculate student growth (comparing to last month for the selected school year)
    last_month = datetime.now() - timedelta(days=30)
    students_last_month = Enrollment.objects.filter(
        school_year=selected_school_year,
        status='Active',
        enrollment_date__lt=last_month
    ).count()
    
    if students_last_month > 0:
        student_growth = ((total_students - students_last_month) / students_last_month) * 100
    else:
        student_growth = 0

    # Get existing school years from enrollments
    db_school_years = list(Enrollment.objects.values_list('school_year', flat=True).distinct().order_by('-school_year'))
    
    # Use default years if no data exists
    default_years = [f"{year}-{year+1}" for year in range(current_year-2, current_year+1)]
    school_years = db_school_years if db_school_years else default_years
    
    # Initialize school years data structure
    school_years_data = {}
    
    for school_year in school_years:
        try:
            year_start = int(school_year.split('-')[0])
            
            # Get monthly enrollment data
            monthly_data = (
                Enrollment.objects
                .filter(
                    school_year=school_year,
                    status='Active'
                )
                .annotate(month=ExtractMonth('enrollment_date'))
                .values('month')
                .annotate(count=Count('id'))
            )

            # Initialize monthly counts
            monthly_counts = [0] * 12
            for item in monthly_data:
                month_index = item['month'] - 1
                monthly_counts[month_index] = item['count']

            # Get yearly data
            yearly_labels = []
            yearly_data = []
            
            for i in range(-3, 1):
                year = year_start + i
                year_range = f"{year}-{year+1}"
                yearly_labels.append(year_range)
                
                count = Enrollment.objects.filter(
                    school_year=year_range,
                    status='Active'
                ).count()
                yearly_data.append(count)

            school_years_data[school_year] = {
                'monthly': {
                    'labels': ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
                    'data': monthly_counts
                },
                'yearly': {
                    'labels': yearly_labels,
                    'data': yearly_data
                }
            }
            
        except (ValueError, IndexError) as e:
            print(f"Error processing school year {school_year}: {str(e)}")
            continue

    # Get simple counts for other stats
    total_teachers = Teachers.objects.count()
    total_sections = Sections.objects.count()

    context = {
        'total_students': total_students,
        'student_growth': round(student_growth, 1),
        'total_teachers': total_teachers,
        'teacher_growth': 0,
        'total_sections': total_sections,
        'section_growth': 0,
        'school_years_data': json.dumps(school_years_data),
        'available_school_years': school_years,
        'selected_school_year': selected_school_year  # Add selected year to context
    }
    
    return render(request, 'main.html', context)

def students_view(request):
    # Get all students
    students = Student.objects.all()
    
    # Get unique school years from both Student and Enrollment models
    student_years = set(Student.objects.exclude(school_year__isnull=True)
                       .values_list('school_year', flat=True)
                       .distinct())
    enrollment_years = set(Enrollment.objects.values_list('school_year', flat=True)
                         .distinct())
    
    # Combine and sort school years
    school_years = sorted(student_years.union(enrollment_years), reverse=True)
    
    # Filter by school year if provided
    selected_year = request.GET.get('school_year')
    if selected_year:
        # Filter students who either have the school year directly set
        # or have an enrollment for that school year
        students = students.filter(
            models.Q(school_year=selected_year) |
            models.Q(enrollments__school_year=selected_year)
        ).distinct()
    
    context = {
        'students': students,
        'school_years': school_years,
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
            return redirect('teachers')
        except Exception as e:
            if 'user' in locals():
                user.delete()
            messages.error(request, f'Error adding teacher: {str(e)}')
            return redirect('teachers')
    
    return redirect('teachers')



def add_student(request):
    if request.method == 'POST':
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
            return redirect('students')  # Or render the form again

        # Proceed to create the student record
        Student.objects.create(
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
        messages.success(request, "Student added successfully!")
        return redirect('students')  # Redirect to the list or appropriate page

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

        context = {
            'sections': sections,
            'teachers': all_teachers,
            'available_teachers': available_teachers,
            'subjects': subjects,
            'adviser_grade_levels': adviser_grade_levels,
            'enrollment_years': enrollment_years  # Add this to context
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

def enrollment_view(request):
    enrollments = Enrollment.objects.select_related(
        'student', 
        'section',
        'dropped_details',
        'transfer_details',
        'completion_details'
    ).all()
    
    # Get students who are not currently enrolled (status is 'Not Enrolled', 'Transferred', or 'Dropped')
    available_students = Student.objects.filter(status__in=['Not Enrolled', 'Transferred', 'Dropped'])
    
    # Get all students for the edit form
    all_students = Student.objects.all()
    
    sections = Sections.objects.all()
    
    context = {
        'enrollments': enrollments,
        'sections': sections,
        'available_students': available_students,
        'all_students': all_students,
    }
    return render(request, 'enrollment.html', context)

def add_enrollment(request):
    if request.method == 'POST':
        try:
            student_id = request.POST.get('student')
            section_id = request.POST.get('section')
            school_year = request.POST.get('school_year')
            
            # Debug information
            print(f"Received data - student_id: {student_id}, section_id: {section_id}, school_year: {school_year}")
            
            # Get the student and section objects
            student = Student.objects.get(id=student_id)
            
            # Make sure we're getting the section correctly
            try:
                section = Sections.objects.get(id=section_id)
                print(f"Found section: {section}")
            except Sections.DoesNotExist:
                # Try to find by section_id instead of id
                try:
                    section = Sections.objects.get(section_id=section_id)
                    print(f"Found section by section_id: {section}")
                except Sections.DoesNotExist:
                    # List all available sections for debugging
                    all_sections = list(Sections.objects.all().values('id', 'section_id'))
                    print(f"Available sections: {all_sections}")
                    raise Sections.DoesNotExist(f"Section with ID {section_id} not found. Available sections: {all_sections}")
            
            # Check if the student is already enrolled in this section for this school year
            if Enrollment.objects.filter(student=student, section=section, school_year=school_year).exists():
                messages.error(request, f"{student.first_name} {student.last_name} is already enrolled in this section for {school_year}.")
                return redirect('enrollment')
            
            # Check if the student is already enrolled in any section for this school year
            existing_enrollment = Enrollment.objects.filter(
                student=student, 
                school_year=school_year,
                status='Active'
            ).first()
            
            if existing_enrollment:
                messages.error(
                    request, 
                    f"{student.first_name} {student.last_name} is already enrolled in {existing_enrollment.section.section_id} "
                    f"({existing_enrollment.section.grade_level}) for {school_year}. "
                    f"A student cannot be enrolled in multiple sections at the same time."
                )
                return redirect('enrollment')
            
            # Check if the student is enrolled in a different grade level
            student_grade_level = section.grade_level
            different_grade_enrollment = Enrollment.objects.filter(
                student=student,
                status='Active'
            ).exclude(section__grade_level=student_grade_level).first()
            
            if different_grade_enrollment:
                messages.error(
                    request,
                    f"{student.first_name} {student.last_name} is already enrolled in grade level "
                    f"{different_grade_enrollment.section.grade_level}. A student cannot be enrolled in multiple grade levels."
                )
                return redirect('enrollment')
            
            # Create the enrollment
            enrollment = Enrollment.objects.create(
                student=student,
                section=section,
                school_year=school_year
            )
            
            # Update student status to "Enrolled"
            student.status = "Enrolled"
            student.save()
            
            messages.success(request, f"{student.first_name} {student.last_name} successfully enrolled in {section.section_id} for {school_year}!")
            
        except Student.DoesNotExist:
            messages.error(request, 'Student not found!')
        except Sections.DoesNotExist as e:
            messages.error(request, f'Section not found! {str(e)}')
        except Exception as e:
            messages.error(request, f'Error adding enrollment: {str(e)}')
    
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
            elif new_status == 'Dropped':
                student.status = 'Dropped'
                DroppedStudent.objects.create(
                    enrollment=enrollment,
                    drop_date=request.POST.get('drop_date'),
                    reason=request.POST.get('drop_reason', 'Status changed to Dropped'),
                    remarks=request.POST.get('drop_remarks', '')
                )
                enrollment.delete()
            elif new_status == 'Transferred':
                student.status = 'Transferred'
                TransferredStudent.objects.create(
                    enrollment=enrollment,
                    transfer_date=request.POST.get('transfer_date'),
                    transfer_school=request.POST.get('transfer_school', 'Not specified'),
                    reason=request.POST.get('transfer_reason', 'Status changed to Transferred'),
                    remarks=request.POST.get('transfer_remarks', '')
                )
                enrollment.delete()
            
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
            
            messages.success(request, 'Student updated successfully!')
            
        except Student.DoesNotExist:
            messages.error(request, 'Student not found!')
        except Exception as e:
            messages.error(request, f'Error updating student: {str(e)}')
    
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
    """API endpoint to get enrolled students for a section"""
    section_id = request.GET.get('section_id')
    selected_school_year = request.GET.get('school_year')
    
    if not section_id or not selected_school_year:
        return JsonResponse({'error': 'Section ID and School Year are required'}, status=400)
    
    try:
        section = Sections.objects.get(id=section_id)
        
        # Get enrollments for this section and school year only
        enrollments = Enrollment.objects.select_related('student').filter(
            section=section,
            school_year=selected_school_year,  # Filter by exact school year
            status='Active'
        )

        # Create list of students
        students = []   
        seen_students = set()  # To track unique students
        
        for enrollment in enrollments:
            student_id = enrollment.student.student_id
            if student_id not in seen_students:  # Only add if not already added
                seen_students.add(student_id)
                students.append({
                    'student_id': student_id,
                    'first_name': enrollment.student.first_name,
                    'last_name': enrollment.student.last_name,
                    'gender': enrollment.student.gender,
                    'status': enrollment.status
                })
        
        # Sort students by ID
        students.sort(key=lambda x: x['student_id'])
        
        return JsonResponse({
            'students': students,
            'grade_level': section.grade_level,
            'section_id': section.section_id,
            'school_year': selected_school_year
        })
        
    except Sections.DoesNotExist:
        return JsonResponse({'error': 'Section not found'}, status=404)
    except Exception as e:
        print(f"Error in get_enrolled_students: {str(e)}")  # For debugging
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
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
