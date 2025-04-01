from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
import csv
import pandas as pd
from .models import Grade
from dashboard.models import Student, Teachers, Subject, Sections, Schedules, Enrollment, Grades
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.contrib import messages
from datetime import datetime
from django.db.models import Q
from django.utils import timezone

@login_required
def profile_view(request):
    # Get the teacher information based on the logged-in user
    try:
        # Try to get the teacher by the associated user account
        teacher = Teachers.objects.get(user=request.user)
        
        # Print teacher info for debugging
        print(f"Found teacher: {teacher.first_name} {teacher.last_name}")
        
        # Get sections where this teacher is the adviser
        teacher_sections = Sections.objects.filter(adviser=teacher)
        
        # Get subjects from these sections through the schedules relationship
        section_subjects = Subject.objects.filter(schedules__section__in=teacher_sections).distinct()
        
        context = {
            'teacher': teacher,
            'section_subjects': section_subjects,
            'teacher_sections': teacher_sections
        }
        return render(request, 'Profile.html', context)
    except Teachers.DoesNotExist:
        # Print error for debugging
        print(f"No teacher found for user: {request.user.username}")
        
        # Try to get all teachers to see what's available
        all_teachers = Teachers.objects.all()
        print(f"Available teachers: {[t.username for t in all_teachers]}")
        
        # If no teacher profile is found, create a basic context with user info
        context = {
            'error': 'Teacher profile not found',
            'user': request.user
        }
        return render(request, 'Profile.html', context)
    except Exception as e:
        # Catch any other exceptions
        print(f"Error retrieving teacher: {str(e)}")
        context = {
            'error': f'Error: {str(e)}',
            'user': request.user
        }
        return render(request, 'Profile.html', context)


def update_profile(request):
    if request.method == 'POST':
        # Get the teacher instance
        teacher = Teachers.objects.get(username=request.user.username)
        
        # Update fields from form data
        teacher.first_name = request.POST.get('first_name')
        teacher.middle_name = request.POST.get('middle_name')
        teacher.last_name = request.POST.get('last_name')
        teacher.gender = request.POST.get('gender')
        teacher.date_of_birth = request.POST.get('date_of_birth')
        teacher.religion = request.POST.get('religion')
        teacher.mobile_number = request.POST.get('mobile_number')
        teacher.email = request.POST.get('email')
        teacher.address = request.POST.get('address')
        
        # Handle profile photo upload
        if 'teacher_photo' in request.FILES:
            teacher.teacher_photo = request.FILES['teacher_photo']
        
        # Save the updated teacher
        teacher.save()
        
        # Redirect back to profile page
        return redirect('profile')
    
    # If not POST, redirect to profile
    return redirect('profile')

    
def add_student(request):
    # Your view logic here
    pass

def logout_view(request):
    logout(request)
    return redirect('login')  # Redirect to your login page

@login_required
def teacher_subjects_view(request):
    try:
        # Get the teacher
        teacher = Teachers.objects.get(user=request.user)
        
        # Get sections where this teacher is the adviser
        teacher_sections = Sections.objects.filter(adviser=teacher)
        
        # Get subjects taught by this teacher through schedules
        teacher_subjects = Subject.objects.filter(
            schedules__teacher_id=teacher
        ).distinct()
        
        # For each subject, attach the students from enrollment records
        for subject in teacher_subjects:
            # Get all schedules for this subject taught by this teacher
            subject_schedules = Schedules.objects.filter(
                subject=subject,
                teacher_id=teacher
            )
            
            # Get all sections from these schedules
            schedule_sections = [schedule.section for schedule in subject_schedules]
            
            # Get students enrolled in these sections
            enrolled_students = Student.objects.filter(
                enrollments__section__in=schedule_sections,
                enrollments__status='Active'  # Only get active enrollments
            ).distinct()
            
            # Add section information to each student for display
            students_with_info = []
            for student in enrolled_students:
                # Find the enrollment record for this student in one of the sections
                enrollment = Enrollment.objects.filter(
                    student=student,
                    section__in=schedule_sections,
                    status='Active'
                ).first()
                
                if enrollment:
                    # Add grade information directly to avoid template issues
                    try:
                        from TeacherPortal.models import Grade
                        grade = Grade.objects.filter(
                            student=student.student_id,
                            course=subject.subject_id
                        ).order_by('-uploaded_at').first()
                        
                        current_grade = grade.grade if grade else None
                    except:
                        current_grade = None
                    
                    # Create a dictionary with all needed student info
                    student_info = {
                        'student': student,
                        'section': enrollment.section,
                        'enrollment_status': enrollment.status,
                        'school_year': enrollment.school_year,
                        'current_grade': current_grade
                    }
                    students_with_info.append(student_info)
            
            # Attach the processed students to the subject
            subject.students_info = students_with_info
        
        # Get all students enrolled in sections where this teacher is the adviser
        advisory_students = []
        for section in teacher_sections:
            section_enrollments = Enrollment.objects.filter(
                section=section,
                status='Active'
            ).select_related('student')
            
            for enrollment in section_enrollments:
                advisory_students.append({
                    'student': enrollment.student,
                    'section': section,
                    'enrollment_status': enrollment.status,
                    'school_year': enrollment.school_year
                })
        
        context = {
            'teacher': teacher,
            'teacher_sections': teacher_sections,
            'teacher_subjects': teacher_subjects,
            'advisory_students': advisory_students
        }
        
        return render(request, 'teacher_subjects.html', context)
    
    except Teachers.DoesNotExist:
        return render(request, 'teacher_subjects.html', {
            'error': 'Teacher profile not found',
            'user': request.user
        })
    except Exception as e:
        return render(request, 'teacher_subjects.html', {
            'error': f'Error: {str(e)}',
            'user': request.user
        })

@login_required
def teacher_schedule_view(request):
    try:
        # Get the teacher
        teacher = Teachers.objects.get(user=request.user)
        
        # Get all schedules for this teacher
        schedules = Schedules.objects.filter(
            teacher_id=teacher
        ).select_related('subject', 'section').order_by('day', 'start_time')
        
        context = {
            'teacher': teacher,
            'schedules': schedules
        }
        
        return render(request, 'teacher_schedule.html', context)
    
    except Teachers.DoesNotExist:
        return render(request, 'teacher_schedule.html', {
            'error': 'Teacher profile not found',
            'user': request.user
        })
    except Exception as e:
        return render(request, 'teacher_schedule.html', {
            'error': f'Error: {str(e)}',
            'user': request.user
        })

@login_required
def import_grades_view(request):
    """View for the grade import page"""
    try:
        # Get the teacher
        teacher = Teachers.objects.get(user=request.user)
        
        # Get subjects taught by this teacher
        teacher_subjects = Subject.objects.filter(
            schedules__teacher_id=teacher
        ).distinct()
        
        context = {
            'teacher': teacher,
            'subjects': teacher_subjects
        }
        
        return render(request, 'import_grades.html', context)
    
    except Teachers.DoesNotExist:
        messages.error(request, "Teacher profile not found")
        return redirect('profile')
    except Exception as e:
        messages.error(request, f"Error: {str(e)}")
        return redirect('profile')

@login_required
def upload_grades(request):
    """Process the uploaded Excel file with grades"""
    if request.method != 'POST':
        return redirect('import_grades')
    
    try:
        # Get the teacher
        teacher = Teachers.objects.get(user=request.user)
        
        # Get form data
        subject_id = request.POST.get('subject')
        quarter = request.POST.get('quarter')
        school_year = request.POST.get('school_year')
        excel_file = request.FILES.get('grades_file')
        
        if not all([subject_id, quarter, school_year, excel_file]):
            messages.error(request, "All fields are required")
            return redirect('import_grades')
        
        # Validate file extension
        if not excel_file.name.endswith(('.xls', '.xlsx')):
            messages.error(request, "Only Excel files (.xls, .xlsx) are allowed")
            return redirect('import_grades')
        
        # Get the subject
        subject = Subject.objects.get(id=subject_id)
        subject_name = subject.name.lower()
        print(f"Looking for subject: {subject_name}")
        
        # Get all students enrolled in this subject through schedules and enrollments
        enrolled_students = []
        
        # Get all schedules for this subject taught by this teacher
        subject_schedules = Schedules.objects.filter(
            subject=subject,
            teacher_id=teacher
        )
        
        # Get all sections from these schedules
        schedule_sections = [schedule.section for schedule in subject_schedules]
        
        # Get students enrolled in these sections
        enrolled_students = Student.objects.filter(
            enrollments__section__in=schedule_sections,
            enrollments__status='Active'  # Only get active enrollments
        ).distinct()
        
        print(f"Found {len(enrolled_students)} students enrolled in {subject.name}")
        
        # Create a dictionary of enrolled students for faster lookup
        enrolled_student_dict = {}
        for student in enrolled_students:
            # Create keys with different name formats for flexible matching
            full_name = f"{student.first_name} {student.last_name}".lower()
            enrolled_student_dict[full_name] = student
            
            # Also add with middle name if available
            if student.middle_name:
                full_name_with_middle = f"{student.first_name} {student.middle_name} {student.last_name}".lower()
                enrolled_student_dict[full_name_with_middle] = student
                
                # Add with middle initial
                middle_initial = student.middle_name[0] if student.middle_name else ""
                full_name_with_initial = f"{student.first_name} {middle_initial}. {student.last_name}".lower()
                enrolled_student_dict[full_name_with_initial] = student
            
            # Add last name, first name format
            last_first = f"{student.last_name}, {student.first_name}".lower()
            enrolled_student_dict[last_first] = student
            
            # Add last name, first name, middle name format
            if student.middle_name:
                last_first_middle = f"{student.last_name}, {student.first_name} {student.middle_name}".lower()
                enrolled_student_dict[last_first_middle] = student
            
            # Print student names for debugging
            print(f"Enrolled student: {student.first_name} {student.last_name}")
        
        # Read the Excel file
        try:
            # Read without headers
            df = pd.read_excel(excel_file, header=None)
            print(f"Excel shape: {df.shape}")
            
            # Print first few rows for debugging
            print("First 20 rows:")
            for i in range(min(20, len(df))):
                row_values = [str(x) for x in df.iloc[i].tolist()[:10]]  # First 10 columns
                print(f"Row {i}: {row_values}")
            
        except ImportError:
            messages.error(request, "Missing required package 'openpyxl'. Please contact your system administrator.")
            return redirect('import_grades')
        except Exception as e:
            messages.error(request, f"Error reading Excel file: {str(e)}")
            return redirect('import_grades')
        
        # Find the row with column headers (FILIPINO, ENGLISH, MATH, etc.)
        header_row = None
        for i in range(min(20, len(df))):
            row_str = ' '.join(str(x).lower() for x in df.iloc[i] if pd.notna(x))
            if 'filipino' in row_str and 'english' in row_str and 'math' in row_str:
                header_row = i
                print(f"Found header row at index {i}: {row_str}")
                break
        
        if header_row is None:
            messages.error(request, "Could not find subject headers in the Excel file")
            return redirect('import_grades')
        
        # Find the subject column
        subject_column = None
        for j in range(df.shape[1]):
            cell_value = str(df.iloc[header_row, j]).lower()
            if subject_name in cell_value:
                subject_column = j
                print(f"Found subject column at position {j}: {df.iloc[header_row, j]}")
                break
        
        # If we couldn't find the exact subject name, try common abbreviations
        if subject_column is None:
            subject_abbr = {
                'mathematics': ['math', 'mat', 'm'],
                'english': ['eng', 'e', 'epp'],
                'science': ['sci', 's'],
                'filipino': ['fil', 'f'],
                'araling panlipunan': ['ap', 'a'],
                'physical education': ['pe', 'p', 'ph']
            }
            
            for subj, abbrs in subject_abbr.items():
                if subj in subject_name or any(abbr in subject_name for abbr in abbrs):
                    for j in range(df.shape[1]):
                        cell_value = str(df.iloc[header_row, j]).lower()
                        if any(abbr == cell_value for abbr in abbrs):
                            subject_column = j
                            print(f"Found subject column by abbreviation at position {j}: {df.iloc[header_row, j]}")
                            break
                    if subject_column is not None:
                        break
        
        if subject_column is None:
            messages.error(request, f"Could not find column for subject '{subject.name}' in the Excel file")
            return redirect('import_grades')
        
        # Find the name column (usually the first column)
        name_column = None
        for j in range(df.shape[1]):
            cell_value = str(df.iloc[header_row-1, j]).lower()
            if "name" in cell_value or "learner" in cell_value:
                name_column = j
                print(f"Found name column at position {j}: {df.iloc[header_row-1, j]}")
                break
        
        if name_column is None:
            name_column = 0  # Default to first column
            print("Defaulting to first column for student names")
        
        # Start processing from the row after the header
        start_row = header_row + 1
        print(f"Starting data processing from row {start_row}")
        
        # Process each row
        success_count = 0
        error_count = 0
        errors = []
        
        # Look specifically for EJERA, HANZ JEHO for debugging
        ejera_found = False
        
        for index in range(start_row, len(df)):
            try:
                # Get student name
                student_name = str(df.iloc[index, name_column]).strip()
                
                # Skip empty rows or non-student rows
                if pd.isna(student_name) or student_name == '' or len(student_name.split()) < 2:
                    continue
                
                # Skip rows with "Page", "SELECT", or other non-student indicators
                if any(keyword in student_name.lower() for keyword in ['page', 'select', 'total']):
                    continue
                
                # Check if this is EJERA, HANZ JEHO
                if "ejera" in student_name.lower() and "hanz" in student_name.lower():
                    print(f"Found EJERA, HANZ JEHO at row {index}")
                    print(f"Name: {student_name}")
                    print(f"Subject column: {subject_column}")
                    print(f"Grade value: {df.iloc[index, subject_column]}")
                    ejera_found = True
                
                # Try to get grade value
                try:
                    grade_value = float(df.iloc[index, subject_column])
                    # Validate grade value
                    if not (0 <= grade_value <= 100):
                        print(f"Skipping invalid grade {grade_value} for {student_name}")
                        continue  # Skip invalid grades
                except (ValueError, TypeError):
                    # Skip rows without valid grades
                    print(f"No valid grade for {student_name} at column {subject_column}")
                    continue
                
                print(f"Processing: {student_name} - Grade: {grade_value}")
                
                # Find the student by name in our enrolled students dictionary
                student = None
                student_name_lower = student_name.lower()
                
                # Try exact match first
                if student_name_lower in enrolled_student_dict:
                    student = enrolled_student_dict[student_name_lower]
                    print(f"Found exact match for {student_name}")
                else:
                    # Try partial matching
                    for enrolled_name, enrolled_student in enrolled_student_dict.items():
                        # Check if all parts of the student name are in the enrolled name
                        name_parts = student_name_lower.split()
                        if len(name_parts) >= 2 and all(part in enrolled_name for part in name_parts):
                            student = enrolled_student
                            print(f"Found student by partial match: {enrolled_name}")
                            break
                        
                        # Also check if the student name contains all parts of an enrolled name
                        enrolled_parts = enrolled_name.split()
                        if len(enrolled_parts) >= 2 and all(part in student_name_lower for part in enrolled_parts):
                            student = enrolled_student
                            print(f"Found student by reverse partial match: {enrolled_name}")
                            break
                
                if not student:
                    # Try database lookup as a last resort
                    try:
                        # For EJERA, HANZ JEHO specifically
                        if "ejera" in student_name.lower() and "hanz" in student_name.lower():
                            print("Trying special lookup for EJERA, HANZ JEHO")
                            student = Student.objects.filter(
                                last_name__icontains="ejera",
                                first_name__icontains="hanz"
                            ).first()
                            if student:
                                print(f"Found EJERA, HANZ JEHO by special lookup: {student.first_name} {student.last_name}")
                        
                        # Try to find by last name, first name format
                        if "," in student_name:
                            last_name, first_name = student_name.split(",", 1)
                            student = Student.objects.filter(
                                last_name__iexact=last_name.strip(),
                                first_name__icontains=first_name.strip().split()[0]
                            ).first()
                            
                            if student:
                                print(f"Found student by last name, first name format: {student.first_name} {student.last_name}")
                        
                        # If still not found, try a more general approach
                        if not student:
                            student = Student.objects.filter(
                                enrollments__section__in=schedule_sections,
                                enrollments__status='Active'
                            ).filter(
                                Q(first_name__icontains=student_name.split()[0]) | 
                                Q(last_name__icontains=student_name.split()[-1])
                            ).first()
                            
                            if student:
                                print(f"Found student by general lookup: {student.first_name} {student.last_name}")
                    except Exception as e:
                        print(f"Error finding student in database: {str(e)}")
                        pass
                
                if not student:
                    print(f"Student not found: {student_name}")
                    # Skip students not enrolled in this subject
                    continue
                
                # Create grade in TeacherPortal's Grade model
                Grade.objects.create(
                    student=student.student_id,  # Store student ID
                    grade=grade_value,
                    quarter=int(quarter),
                    school_year=school_year,
                    teacher=teacher.username
                )
                
                # Also update the main Grades model if it exists
                try:
                    from dashboard.models import Grades
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
                    if hasattr(grade, 'calculate_final_grade'):
                        grade.calculate_final_grade()
                        grade.save()
                except Exception as e:
                    print(f"Error updating dashboard Grades: {str(e)}")
                    # If dashboard.models.Grades doesn't exist or has different structure,
                    # we'll still have the grades in our TeacherPortal.Grade model
                    pass
                
                success_count += 1
                
            except Exception as e:
                errors.append(f"Row {index+1}: {str(e)}")
                error_count += 1
                print(f"Error processing row {index+1}: {str(e)}")
        
        if not ejera_found:
            print("EJERA, HANZ JEHO not found in the Excel file")
        
        # Prepare message
        if success_count > 0:
            messages.success(request, f"Successfully imported {success_count} grades")
        elif error_count == 0:
            messages.warning(request, "No grades were imported. Please check that your Excel file contains valid student names and grades for the selected subject.")
        
        if error_count > 0:
            error_message = f"Failed to import {error_count} grades. Errors: "
            error_message += ", ".join(errors[:5])
            if len(errors) > 5:
                error_message += f" and {len(errors) - 5} more errors"
            messages.error(request, error_message)
        
        return redirect('import_grades')
    
    except Teachers.DoesNotExist:
        messages.error(request, "Teacher profile not found")
        return redirect('profile')
    except Subject.DoesNotExist:
        messages.error(request, "Subject not found")
        return redirect('import_grades')
    except Exception as e:
        messages.error(request, f"Error processing file: {str(e)}")
        return redirect('import_grades')

@login_required
def upload_grades_ajax(request):
    """Process uploaded Excel file and return preview data"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'})
    
    try:
        # Get form data
        subject_id = request.POST.get('subject')
        quarter = request.POST.get('quarter')
        school_year = request.POST.get('school_year')
        
        if not all([subject_id, quarter, school_year]):
            return JsonResponse({'status': 'error', 'message': 'Missing required fields'})
        
        if 'grades_file' not in request.FILES:
            return JsonResponse({'status': 'error', 'message': 'No file uploaded'})
        
        uploaded_file = request.FILES['grades_file']
        
        # Get the teacher and subject
        teacher = Teachers.objects.get(user=request.user)
        subject = Subject.objects.get(id=subject_id)
        
        # Map subject names to possible column headers in the Excel file
        subject_column_mapping = {
            'filipino': ['filipino', 'fil'],
            'english': ['english', 'eng'],
            'mathematics': ['mathematics', 'math'],
            'science': ['science', 'sci'],
            'araling panlipunan': ['araling panlipunan', 'ap'],
            'technology and livelihood education': ['technology and livelihood education', 'tle', 't.l.e'],
            'music': ['music'],
            'arts': ['arts'],
            'physical education': ['physical education', 'pe', 'p.e'],
            'health': ['health'],
            'edukasyon sa pagpapakatao': ['edukasyon sa pagpapakatao', 'esp', 'e.s.p']
        }
        
        # Get possible column names for the selected subject
        possible_column_names = []
        for key, values in subject_column_mapping.items():
            if any(subj in subject.name.lower() for subj in values):
                possible_column_names.extend(values)
        
        print(f"Looking for subject columns matching: {possible_column_names}")
        
        # Get enrolled students for this subject
        subject_schedules = Schedules.objects.filter(
            subject=subject,
            teacher_id=teacher
        )
        schedule_sections = [schedule.section for schedule in subject_schedules]
        enrolled_students = Student.objects.filter(
            enrollments__section__in=schedule_sections,
            enrollments__status='Active'
        ).distinct()
        
        print(f"Found {len(enrolled_students)} enrolled students for {subject.name}")
        
        # Create a dictionary of enrolled students for faster lookup
        enrolled_student_dict = {}
        for student in enrolled_students:
            # Store by student ID for exact matching
            enrolled_student_dict[student.student_id] = student
            
            # Store by full name variations
            full_name = f"{student.first_name} {student.last_name}".lower()
            enrolled_student_dict[full_name] = student
            
            # Last name, first name format
            last_first = f"{student.last_name}, {student.first_name}".lower()
            enrolled_student_dict[last_first] = student
            
            # Add just last name for partial matching
            enrolled_student_dict[student.last_name.lower()] = student

        # Try to read the file
        try:
            # Read Excel file with multiple attempts
            try:
                df = pd.read_excel(uploaded_file, header=None, engine='openpyxl')
                print("Successfully read Excel file with openpyxl engine")
            except Exception as e1:
                print(f"Failed to read with openpyxl: {str(e1)}")
                try:
                    df = pd.read_excel(uploaded_file, header=None, engine='xlrd')
                    print("Successfully read Excel file with xlrd engine")
                except Exception as e2:
                    print(f"Failed to read with xlrd: {str(e2)}")
                    # Try reading with no specific engine
                    df = pd.read_excel(uploaded_file, header=None)
                    print("Successfully read Excel file with default engine")
            
            # Print the shape of the DataFrame
            print(f"Excel file shape: {df.shape}")
            
            # Find the header row with subject names
            header_row = None
            subject_col = None
            name_col = None
            
            # Look for rows with subject headers
            for i in range(min(20, len(df))):
                row = df.iloc[i]
                # Convert row to string and lowercase for easier matching
                row_str = [str(cell).lower() if pd.notna(cell) else "" for cell in row]
                
                # Check if this row contains subject headers
                if any(subj in " ".join(row_str) for subj in ['filipino', 'english', 'math', 'science']):
                    header_row = i
                    print(f"Found header row at index {i}: {row_str}")
                    
                    # Find the column for the selected subject
                    for j, cell in enumerate(row_str):
                        if any(subj in cell for subj in possible_column_names):
                            subject_col = j
                            print(f"Found subject column at index {j}: {cell}")
                            break
                    
                    # Find the column with student names (usually the first column)
                    for j, cell in enumerate(row_str):
                        if 'name' in cell or 'student' in cell:
                            name_col = j
                            print(f"Found name column at index {j}: {cell}")
                            break
                    
                    if name_col is None:
                        name_col = 0  # Default to first column
                    
                    break
            
            # If we couldn't find the header row, try another approach
            if header_row is None or subject_col is None:
                print("Could not find header row with standard approach, trying alternative...")
                
                # Look for a row with numeric values in multiple columns (likely grades)
                for i in range(min(30, len(df))):
                    row = df.iloc[i]
                    numeric_count = sum(1 for cell in row if pd.notna(cell) and isinstance(cell, (int, float)) and 0 <= cell <= 100)
                    
                    if numeric_count >= 3:  # If at least 3 columns have numeric grades
                        # The row above this is likely the header
                        header_row = i - 1 if i > 0 else i
                        
                        # The first column is likely student names
                        name_col = 0
                        
                        # Find a column with subject name matching our target
                        row_above = df.iloc[header_row]
                        row_above_str = [str(cell).lower() if pd.notna(cell) else "" for cell in row_above]
                        
                        for j, cell in enumerate(row_above_str):
                            if any(subj in cell for subj in possible_column_names):
                                subject_col = j
                                print(f"Found subject column at index {j}: {cell}")
                                break
                        
                        # If still not found, look for a column with numeric values
                        if subject_col is None:
                            for j, cell in enumerate(row):
                                if j != name_col and pd.notna(cell) and isinstance(cell, (int, float)) and 0 <= cell <= 100:
                                    subject_col = j
                                    print(f"Using numeric column at index {j} as subject column")
                                    break
                        
                        break
            
            if header_row is None or subject_col is None or name_col is None:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Could not identify the structure of the Excel file. Please ensure it has student names and subject grades.'
                })
            
            # Start processing from the row after the header
            start_row = header_row + 1
            
            # Process student data
            preview_data = []
            raw_data = []
            
            # Get the subject name from the header
            subject_header = str(df.iloc[header_row, subject_col]) if pd.notna(df.iloc[header_row, subject_col]) else subject.name
            
            # Process each row
            for idx in range(start_row, len(df)):
                try:
                    # Get student name and grade
                    student_name = str(df.iloc[idx, name_col]).strip() if pd.notna(df.iloc[idx, name_col]) else ''
                    grade_value = df.iloc[idx, subject_col] if pd.notna(df.iloc[idx, subject_col]) else None
                    
                    # Add to raw data for display
                    raw_data.append({
                        'name': student_name,
                        'grade': grade_value
                    })
                    
                    # Skip empty rows or non-student rows
                    if not student_name or any(skip in student_name.lower() 
                                             for skip in ['page', 'total', 'name of adviser', 'teacher']):
                        continue
                    
                    # Try to convert grade to float
                    try:
                        grade_float = float(grade_value)
                        if not (0 <= grade_float <= 100):  # Valid grade range
                            continue
                    except (ValueError, TypeError):
                        continue
                    
                    # Try to match with enrolled student
                    matched_student = None
                    student_name_lower = student_name.lower()
                    
                    # Try exact match first
                    if student_name_lower in enrolled_student_dict:
                        matched_student = enrolled_student_dict[student_name_lower]
                    else:
                        # Try matching by last name
                        for enrolled_name, enrolled_student in enrolled_student_dict.items():
                            # Check if the student name contains the enrolled name
                            if enrolled_name in student_name_lower:
                                matched_student = enrolled_student
                                break
                    
                    # If still not found, try database lookup
                    if not matched_student:
                        try:
                            # Try to find by last name
                            name_parts = student_name.split()
                            if len(name_parts) >= 1:
                                # Try the first part as last name (common in the format)
                                matched_student = Student.objects.filter(
                                    last_name__iexact=name_parts[0],
                                    enrollments__section__in=schedule_sections,
                                    enrollments__status='Active'
                                ).first()
                                
                                # If not found, try the last part as last name
                                if not matched_student and len(name_parts) > 1:
                                    matched_student = Student.objects.filter(
                                        last_name__iexact=name_parts[-1],
                                        enrollments__section__in=schedule_sections,
                                        enrollments__status='Active'
                                    ).first()
                        except Exception as e:
                            print(f"Error finding student in database: {str(e)}")
                    
                    # Add to preview if student is matched and grade is valid
                    if matched_student:
                        # Get student's section
                        enrollment = Enrollment.objects.filter(
                            student=matched_student,
                            section__in=schedule_sections,
                            status='Active'
                        ).first()
                        section_name = enrollment.section.section_name if enrollment else "Unknown"
                        
                        preview_data.append({
                            'excel_name': student_name,
                            'student_id': matched_student.student_id,
                            'student_name': f"{matched_student.last_name}, {matched_student.first_name}",
                            'grade': grade_float,
                            'section': section_name
                        })
                except Exception as row_error:
                    print(f"Error processing row {idx}: {str(row_error)}")
                    continue
            
            # Store preview data in session
            request.session['grade_preview_data'] = preview_data
            request.session['grade_import_info'] = {
                'subject_id': subject_id,
                'quarter': quarter,
                'school_year': school_year,
                'teacher_id': teacher.id
            }
            
            return JsonResponse({
                'status': 'success',
                'subject_name': subject.name,
                'subject_header': subject_header,
                'quarter': quarter,
                'school_year': school_year,
                'count': len(preview_data),
                'preview_data': preview_data,
                'raw_data': raw_data
            })
            
        except Exception as e:
            import traceback
            print("Error processing file:")
            print(traceback.format_exc())
            return JsonResponse({
                'status': 'error',
                'message': f'Error processing file: {str(e)}'
            })
            
    except Exception as e:
        import traceback
        print("Error in upload_grades_ajax:")
        print(traceback.format_exc())
        return JsonResponse({'status': 'error', 'message': str(e)})

@login_required
def confirm_import_grades_ajax(request):
    """Import grades from preview data stored in session"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'})
    
    try:
        # Get preview data from session
        preview_data = request.session.get('grade_preview_data')
        import_info = request.session.get('grade_import_info')
        
        if not preview_data or not import_info:
            return JsonResponse({'status': 'error', 'message': 'No preview data found. Please upload the file again.'})
        
        # Get import info
        subject_id = import_info.get('subject_id')
        quarter = import_info.get('quarter')
        school_year = import_info.get('school_year')
        teacher_id = import_info.get('teacher_id')
        
        if not all([subject_id, quarter, school_year, teacher_id]):
            return JsonResponse({'status': 'error', 'message': 'Missing required import information'})
        
        # Get subject and teacher
        subject = Subject.objects.get(id=subject_id)
        teacher = Teachers.objects.get(id=teacher_id)
        
        # Import grades
        count = 0
        for item in preview_data:
            try:
                student_id = item.get('student_id')
                grade_value = item.get('grade')
                
                # Check if grade already exists
                existing_grade = Grade.objects.filter(
                    student=student_id,
                    course=subject.subject_id,
                    quarter=quarter,
                    school_year=school_year
                ).first()
                
                if existing_grade:
                    # Update existing grade
                    existing_grade.grade = grade_value
                    existing_grade.date_updated = timezone.now()
                    existing_grade.save()
                else:
                    # Create new grade
                    new_grade = Grade(
                        student=student_id,
                        course=subject.subject_id,
                        quarter=quarter,
                        school_year=school_year,
                        grade=grade_value,
                        date_created=timezone.now(),
                        date_updated=timezone.now()
                    )
                    new_grade.save()
                
                count += 1
            except Exception as e:
                print(f"Error importing grade for student {item.get('student_id')}: {str(e)}")
                continue
        
        # Clear session data
        if 'grade_preview_data' in request.session:
            del request.session['grade_preview_data']
        if 'grade_import_info' in request.session:
            del request.session['grade_import_info']
        
        return JsonResponse({
            'status': 'success',
            'message': f'Successfully imported {count} grades',
            'count': count
        })
        
    except Exception as e:
        import traceback
        print("Error in confirm_import_grades_ajax:")
        print(traceback.format_exc())
        return JsonResponse({'status': 'error', 'message': str(e)})

@login_required
def preview_template(request):
    """Preview the template based on uploaded file or generate a new one"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'})
    
    try:
        subject_id = request.POST.get('subject')
        quarter = request.POST.get('quarter')
        school_year = request.POST.get('school_year')
        
        if not all([subject_id, quarter, school_year]):
            return JsonResponse({'status': 'error', 'message': 'Missing required fields'})
        
        subject = Subject.objects.get(id=subject_id)
        teacher = Teachers.objects.get(user=request.user)
        
        # Get enrolled students
        enrolled_students = Student.objects.filter(
            enrollments__section__schedules__subject=subject,
            enrollments__section__schedules__teacher_id=teacher,
            enrollments__status='Active'
        ).distinct()
        
        headers = []
        preview_data = []
        
        if 'template_file' in request.FILES:
            # Read template from uploaded file
            df = pd.read_excel(request.FILES['template_file'])
            headers = df.columns.tolist()
            
            # Get first few rows as sample data
            preview_data = df.head(5).values.tolist()
        else:
            # Generate default template
            headers = ['Student Name', subject.name]
            
            # Add sample student data
            for student in enrolled_students[:5]:
                preview_data.append([
                    f"{student.last_name}, {student.first_name}",
                    ""  # Empty grade column
                ])
        
        return JsonResponse({
            'status': 'success',
            'headers': headers,
            'preview_data': preview_data
        })
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        })

@login_required
def generate_grade_template(request):
    """Generate grade template based on uploaded file or create new one"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'})
    
    try:
        subject_id = request.POST.get('subject')
        quarter = request.POST.get('quarter')
        school_year = request.POST.get('school_year')
        
        if not all([subject_id, quarter, school_year]):
            return JsonResponse({'status': 'error', 'message': 'Missing required fields'})
        
        subject = Subject.objects.get(id=subject_id)
        teacher = Teachers.objects.get(user=request.user)
        
        # Get enrolled students
        enrolled_students = Student.objects.filter(
            enrollments__section__schedules__subject=subject,
            enrollments__section__schedules__teacher_id=teacher,
            enrollments__status='Active'
        ).distinct()
        
        template_data = []
        
        if 'template_file' in request.FILES:
            # Use uploaded template structure
            df = pd.read_excel(request.FILES['template_file'])
            headers = df.columns.tolist()
            template_data.append(headers)
            
            # Add enrolled students to template
            for student in enrolled_students:
                row = [""] * len(headers)  # Create empty row
                row[0] = f"{student.last_name}, {student.first_name}"  # Add student name
                template_data.append(row)
        else:
            # Create default template
            template_data.append(['Student Name', subject.name])
            
            # Add enrolled students
            for student in enrolled_students:
                template_data.append([
                    f"{student.last_name}, {student.first_name}",
                    ""  # Empty grade column
                ])
        
        return JsonResponse({
            'status': 'success',
            'template_data': template_data,
            'subject_name': subject.name,
            'quarter': quarter,
            'school_year': school_year
        })
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        })

