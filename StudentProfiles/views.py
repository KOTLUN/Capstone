from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect
from django.db.models import Avg, Q
from dashboard.models import (
    Student, Enrollment, Guardian, Subject, 
    Schedules, SchoolYear
)
from TeacherPortal.models import Grade
import json
from decimal import Decimal
from django.utils import timezone
from django.http import HttpResponse
from random import randint
from django.db import connection

@login_required
def student_profile(request, student_id):
    # Get the student or return 404
    student = get_object_or_404(Student, id=student_id)
    
    # Security check - only allow viewing if the logged-in user matches the student's user
    # or if the user is an admin/staff
    if request.user != student.user and not request.user.is_staff:
        messages.error(request, "You don't have permission to view this profile.")
        return redirect('login')
    
    # Get the student's current enrollment - using direct ID lookup
    current_enrollment = Enrollment.objects.filter(
        student_id=student.id,  # Use direct field name
        status='Active'
    ).first()
    
    # If enrolled, get the section information
    if current_enrollment:
        student.section = current_enrollment.section.section_id
        student.grade_level = current_enrollment.section.grade_level
        student.school_year = current_enrollment.school_year
    
    # Get the student's guardian information
    guardians = Guardian.objects.filter(student_id=student.id)
    
    context = {
        'student': student,
        'is_enrolled': current_enrollment is not None,
        'guardians': guardians
    }
    
    return render(request, 'student_profile.html', context)

@login_required
def student_dashboard(request, student_id):
    # Get the student or return 404
    student = get_object_or_404(Student, id=student_id)
    
    # Security check
    if request.user != student.user and not request.user.is_staff:
        messages.error(request, "You don't have permission to view this dashboard.")
        return redirect('login')
    
    # Get all available school years for the filter dropdown
    school_years = SchoolYear.get_all_years()
    
    # Get active school year
    active_school_year = SchoolYear.get_active()
    
    # Get the selected school year from request, default to active year
    selected_year_param = request.GET.get('school_year')
    
    if selected_year_param:
        # Find the selected school year
        for year in school_years:
            if year.display_name == selected_year_param:
                selected_year = year
                break
        else:
            selected_year = active_school_year
    else:
        selected_year = active_school_year
    
    # Use the selected year's display name for queries
    if selected_year:
        current_school_year = selected_year.display_name
    else:
        # Fallback if no school year is available
        current_school_year = "2029-2030 (Active)"  # Default to match existing data
    
    # Get the student's current enrollment
    # Extract base year format for better matching
    year_base = current_school_year.split(' ')[0] if ' ' in current_school_year else current_school_year
    
    # Use direct ID lookup for enrollment
    current_enrollment = Enrollment.objects.filter(
        student_id=student.id,  # Use direct field name
        school_year__contains=year_base
    ).first()
    
    # Get current subjects and grades
    subjects = []
    subject_grades_data = {}
    detailed_grades = []
    
    # Get all grades for this student directly from Grade model using Q objects
    # Extract the year portion (e.g., "2025-2026") from the display name
    year_base = current_school_year.split(' ')[0] if ' ' in current_school_year else current_school_year
    print(f"Using base year format for matching: {year_base}")
    
    # Use raw SQL instead of ORM since there's a mismatch in the model definition
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT * FROM teacherportal_grade 
            WHERE (student = %s OR student = %s) 
            AND school_year LIKE %s
            """,
            [student.student_id, str(student.student_id), f"%{year_base}%"]
        )
        # Convert the results to a list of dictionaries
        columns = [col[0] for col in cursor.description]
        all_grades_raw = [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    # Create a custom Grade class to mimic Django model behavior
    class GradeObject:
        def __init__(self, data):
            for key, value in data.items():
                setattr(self, key, value)
    
    # Convert raw results to GradeObject instances
    all_grades = [GradeObject(grade_data) for grade_data in all_grades_raw]
    
    # Debug student ID information
    print(f"Student ID info: {student.student_id} (type: {type(student.student_id).__name__})")
    print(f"String version: {str(student.student_id)}")
    print(f"Looking for grades in school year: {current_school_year}")
    
    # Debug query results
    print(f"Found {len(all_grades)} grades for student {student.student_id} in {current_school_year}")
    
    # No need to print the SQL query since we used raw SQL
    
    # Create a map of subject courses to actual subjects
    subject_map = {}
    
    if current_enrollment:
        # Get subjects for this section
        section_subjects = Subject.objects.filter(
            schedules__section=current_enrollment.section
        ).distinct()
        
        # Create mapping from subject ID to subject
        for subject in section_subjects:
            subject_map[subject.subject_id] = subject
        
        # Add subjects that might have grades but aren't in schedules
        # Extract course IDs from our custom grade objects
        course_ids = list(set([g.course for g in all_grades if hasattr(g, 'course')]))
        
        for course_id in course_ids:
            if course_id not in subject_map:
                # Try to find the subject by ID
                subject = Subject.objects.filter(subject_id=course_id).first()
                if subject:
                    subject_map[course_id] = subject
        
        subjects = list(subject_map.values())
    
    # Create default subject names if not found in mapping
    default_subject_names = {
        '0001': 'English',
        '0002': 'Math',
        '0003': 'Science',
        '0004': 'Social Studies'
    }
    
    # Process grades by course/subject
    # Extract unique course IDs directly from our custom grade objects
    unique_courses = list(set([g.course for g in all_grades if hasattr(g, 'course')]))
    
    for course_id in unique_courses:
        # Get subject object if available, otherwise create dummy
        if course_id in subject_map:
            subject = subject_map[course_id]
            subject_name = subject.name
        else:
            # Use default name if available, otherwise use course ID as name
            subject_name = default_subject_names.get(course_id, f"Subject {course_id}")
            
            # Create a dummy subject object with course info
            subject = type('Subject', (), {
                'name': subject_name,
                'subject_id': course_id,
                'current_grade': 'N/A',
                'teacher': type('Teacher', (), {'full_name': 'Unknown Teacher'})
            })
            
            subjects.append(subject)
        
        # Get all grades for this course
        course_grades = [g for g in all_grades if g.course == course_id]
        
        # Initialize quarterly grades
        quarterly_grades = [0, 0, 0, 0]  # Quarters 1-4
        
        # Process each grade
        for grade in course_grades:
            try:
                quarter_idx = int(grade.quarter) - 1  # Convert quarter to 0-based index
                if 0 <= quarter_idx < 4:  # Ensure valid quarter
                    quarterly_grades[quarter_idx] = float(grade.grade)
                    print(f"Course {course_id} ({subject_name}) - Quarter {grade.quarter}: {grade.grade}")
            except (ValueError, TypeError) as e:
                print(f"Error processing grade: {e}")
                continue
        
        # Set current grade for the subject (most recent value)
        latest_grade = course_grades[-1]
        if latest_grade:
            subject.current_grade = str(latest_grade.grade)
        
        # Calculate subject average from valid grades
        valid_grades = [g for g in quarterly_grades if g > 0]
        subject_average = round(sum(valid_grades) / len(valid_grades), 2) if valid_grades else 0
        
        # Store grades for chart
        subject_grades_data[subject_name] = quarterly_grades
        
        # Store detailed grades for table
        detailed_grades.append({
            'subject': subject_name,
            'quarterly_grades': quarterly_grades,
            'average': subject_average
        })
    
    # If no grades found, just log a message but don't create dummy data
    if not detailed_grades:
        print(f"No grades found for student {student.student_id} in {current_school_year}")
    
    # Get schedule for the selected section
    schedule = []
    if current_enrollment:
        schedule = Schedules.objects.filter(
            section=current_enrollment.section
        ).order_by('start_time')
    
    # Create a clean schedule list with unique entries
    unique_schedule = []
    seen_slots = set()
    
    if schedule:
        for slot in schedule:
            slot_key = f"{slot.start_time.strftime('%H:%M')}-{slot.subject.name}-{slot.room}"
            if slot_key not in seen_slots:
                unique_schedule.append({
                    'start_time': slot.start_time,
                    'end_time': slot.end_time,
                    'subject': slot.subject,
                    'room': slot.room
                })
                seen_slots.add(slot_key)
    
    unique_schedule.sort(key=lambda x: x['start_time'])
    
    # Calculate overall average from valid grades
    all_grades = []
    for grade_data in detailed_grades:
        valid_subject_grades = [g for g in grade_data['quarterly_grades'] if g > 0]
        if valid_subject_grades:
            all_grades.extend(valid_subject_grades)
    
    overall_average = round(sum(all_grades) / len(all_grades), 2) if all_grades else 0
    
    # Prepare data for the chart
    quarters = ['First Quarter', 'Second Quarter', 'Third Quarter', 'Fourth Quarter']
    
    context = {
        'student': student,
        'current_enrollment': current_enrollment,
        'subjects': subjects,
        'schedule': unique_schedule,
        'overall_average': overall_average,
        'quarters': json.dumps(quarters),
        'subject_grades_data': json.dumps(subject_grades_data),
        'detailed_grades': detailed_grades,
        'school_years': school_years,
        'active_school_year': active_school_year,
        'selected_year': selected_year,
        'current_school_year': current_school_year,
        'user': request.user,
    }
    
    return render(request, 'mydashboard.html', context)

@login_required
def update_profile(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    
    # Security check
    if request.user != student.user and not request.user.is_staff:
        messages.error(request, "You don't have permission to update this profile.")
        return redirect('login')
    
    if request.method == 'POST':
        # Handle file upload
        if 'student_photo' in request.FILES:
            student.student_photo = request.FILES['student_photo']
        
        # Update student information
        student.first_name = request.POST.get('first_name', student.first_name)
        student.middle_name = request.POST.get('middle_name', student.middle_name)
        student.last_name = request.POST.get('last_name', student.last_name)
        student.email = request.POST.get('email', student.email)
        student.mobile_number = request.POST.get('mobile_number', student.mobile_number)
        student.address = request.POST.get('address', student.address)
        student.religion = request.POST.get('religion', student.religion)
        
        try:
            student.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('student_profile', student_id=student.id)
        except Exception as e:
            messages.error(request, f'Error updating profile: {str(e)}')
    
    context = {
        'student': student,
    }
    
    return render(request, 'update_profile.html', context)

@login_required
def create_test_grades(request, student_id):
    """Create test grades for a student to test the dashboard."""
    if not request.user.is_staff:
        messages.error(request, "Only staff can create test grades.")
        return redirect('login')
    
    # Get the student
    student = get_object_or_404(Student, id=student_id)
    
    # Get active school year
    active_school_year = SchoolYear.get_active()
    current_school_year = active_school_year.display_name if active_school_year else "2029-2030 (Active)"
    
    # Get current enrollment - Using direct ID lookup
    current_enrollment = Enrollment.objects.filter(
        student_id=student.id,  # Use direct field name
        school_year__contains=current_school_year.split(' ')[0]
    ).first()
    
    if not current_enrollment:
        messages.error(request, f"No enrollment found for {student.first_name} in {current_school_year}")
        return redirect('student_dashboard', student_id=student_id)
    
    # Get subjects
    subjects = Subject.objects.filter(
        schedules__section=current_enrollment.section
    ).distinct()
    
    # Create test grades for each subject
    grades_created = 0
    
    # Use raw SQL for checking and creating grades
    with connection.cursor() as cursor:
        for subject in subjects:
            # Create grades for the first three quarters
            for quarter in ['1', '2', '3']:
                # Check if grade already exists with raw SQL
                cursor.execute(
                    """
                    SELECT id FROM teacherportal_grade 
                    WHERE student = %s AND course = %s AND quarter = %s AND school_year = %s
                    """,
                    [student.student_id, subject.subject_id, quarter, current_school_year]
                )
                existing_grade = cursor.fetchone()
                
                if not existing_grade:
                    # Generate a random grade between 75 and 98
                    grade_value = randint(75, 98)
                    
                    # Create the grade with raw SQL
                    now = timezone.now()
                    cursor.execute(
                        """
                        INSERT INTO teacherportal_grade 
                        (student, course, grade, quarter, school_year, teacher, status, uploaded_at, date_created, date_modified) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        [
                            student.student_id, 
                            subject.subject_id, 
                            grade_value, 
                            quarter, 
                            current_school_year, 
                            "TESTUSER", 
                            "approved", 
                            now,
                            now,
                            now
                        ]
                    )
                    grades_created += 1
    
    messages.success(request, f"Created {grades_created} test grades for {student.first_name}")
    return redirect('student_dashboard', student_id=student_id)

@login_required
def diagnostics(request, student_id):
    """
    Diagnostic view to help debug grade issues by showing all relevant info about
    the student's subjects and grades.
    """
    if not request.user.is_staff:
        messages.error(request, "Only staff can access diagnostics.")
        return redirect('login')
    
    # Get the student
    student = get_object_or_404(Student, id=student_id)
    
    # Get active school year
    active_school_year = SchoolYear.get_active()
    current_school_year = active_school_year.display_name if active_school_year else "2029-2030 (Active)"
    
    # Get current enrollment - Using direct ID lookup
    current_enrollment = Enrollment.objects.filter(
        student_id=student.id,  # Use direct field name
        school_year__contains=current_school_year.split(' ')[0]
    ).first()
    
    # Collect diagnostic info
    diagnostics = {
        'student': {
            'id': student.id,
            'student_id': student.student_id,
            'name': f"{student.first_name} {student.last_name}"
        },
        'school_year': current_school_year,
        'enrollment': current_enrollment.id if current_enrollment else None,
        'subjects': [],
        'grades': [],
        'search_parameters': {
            'student_id_raw': student.student_id,
            'student_id_str': str(student.student_id),
            'student_id_type': type(student.student_id).__name__,
            'school_year': current_school_year
        }
    }
    
    if current_enrollment:
        # Get subjects
        subjects = Subject.objects.filter(
            schedules__section=current_enrollment.section
        ).distinct()
        
        for subject in subjects:
            diagnostics['subjects'].append({
                'id': subject.id,
                'subject_id': subject.subject_id,
                'name': subject.name
            })
        
        # Get grades using raw SQL for reliability
        year_base = current_school_year.split(' ')[0] if ' ' in current_school_year else current_school_year
        print(f"Diagnostics: Using base year '{year_base}' for matching grades")
        
        # Use raw SQL to get grades
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM teacherportal_grade 
                WHERE (student = %s OR student = %s) 
                AND school_year LIKE %s
                """,
                [student.student_id, str(student.student_id), f"%{year_base}%"]
            )
            # Convert the results to a list of dictionaries
            columns = [col[0] for col in cursor.description]
            grades_raw = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        print(f"Diagnostics: Found {len(grades_raw)} grades")
        
        # Add grades to diagnostics
        for grade in grades_raw:
            diagnostics['grades'].append({
                'id': grade['id'],
                'student_id': grade['student'],
                'course': grade['course'],
                'quarter': grade['quarter'],
                'grade_value': float(grade['grade']) if grade['grade'] is not None else 0,
                'uploaded_at': grade['uploaded_at'].strftime('%Y-%m-%d %H:%M:%S') if grade['uploaded_at'] else ''
            })
    
    # Return as HTML
    html_output = f"""
    <html>
    <head>
        <title>Diagnostics for {student.first_name}</title>
        <style>
            body {{ font-family: Arial, sans-serif; padding: 20px; }}
            h1, h2 {{ color: #333; }}
            table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
            .section {{ margin-bottom: 30px; }}
        </style>
    </head>
    <body>
        <h1>Diagnostics for {student.first_name} {student.last_name}</h1>
        
        <div class="section">
            <h2>Student Information</h2>
            <table>
                <tr><th>Database ID</th><td>{student.id}</td></tr>
                <tr><th>Student ID</th><td>{student.student_id}</td></tr>
                <tr><th>Name</th><td>{student.first_name} {student.last_name}</td></tr>
                <tr><th>School Year</th><td>{current_school_year}</td></tr>
                <tr><th>Enrollment ID</th><td>{current_enrollment.id if current_enrollment else 'Not enrolled'}</td></tr>
            </table>
        </div>
        
        <div class="section">
            <h2>Subjects ({len(diagnostics['subjects'])})</h2>
            <table>
                <tr>
                    <th>Database ID</th>
                    <th>Subject ID</th>
                    <th>Name</th>
                </tr>
                {
                    ''.join([
                        f"<tr><td>{s['id']}</td><td>{s['subject_id']}</td><td>{s['name']}</td></tr>"
                        for s in diagnostics['subjects']
                    ])
                }
            </table>
        </div>
        
        <div class="section">
            <h2>Grades ({len(diagnostics['grades'])})</h2>
            <table>
                <tr>
                    <th>Database ID</th>
                    <th>Student ID</th>
                    <th>Course ID</th>
                    <th>Quarter</th>
                    <th>Grade</th>
                    <th>Uploaded At</th>
                </tr>
                {
                    ''.join([
                        f"<tr><td>{g['id']}</td><td>{g['student_id']}</td><td>{g['course']}</td><td>{g['quarter']}</td><td>{g['grade_value']}</td><td>{g['uploaded_at']}</td></tr>"
                        for g in diagnostics['grades']
                    ])
                }
            </table>
        </div>
    </body>
    </html>
    """
    
    return HttpResponse(html_output)

@login_required
def all_grades(request):
    """
    View for administrators to see all grades in the system for debugging purposes.
    """
    if not request.user.is_staff:
        messages.error(request, "Only staff can access this page.")
        return redirect('login')
    
    # Get all grades from TeacherPortal using raw SQL for reliability
    with connection.cursor() as cursor:
        # Get the most recent 200 grades
        cursor.execute(
            """
            SELECT * FROM teacherportal_grade 
            ORDER BY uploaded_at DESC 
            LIMIT 200
            """
        )
        # Convert the results to a list of dictionaries
        columns = [col[0] for col in cursor.description]
        grades = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        # Count grades by school year
        cursor.execute(
            """
            SELECT school_year, COUNT(*) as count 
            FROM teacherportal_grade 
            GROUP BY school_year 
            ORDER BY school_year DESC
            """
        )
        school_year_columns = [col[0] for col in cursor.description]
        school_year_counts = [dict(zip(school_year_columns, row)) for row in cursor.fetchall()]
    
    # HTML output
    html_output = f"""
    <html>
    <head>
        <title>All Grades</title>
        <style>
            body {{ font-family: Arial, sans-serif; padding: 20px; }}
            h1, h2 {{ color: #333; }}
            table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
            .section {{ margin-bottom: 30px; }}
        </style>
    </head>
    <body>
        <h1>All Grades in TeacherPortal</h1>
        
        <div class="section">
            <h2>School Year Distribution</h2>
            <table>
                <tr>
                    <th>School Year</th>
                    <th>Number of Grades</th>
                </tr>
                {
                    ''.join([
                        f"<tr><td>{year['school_year']}</td><td>{year['count']}</td></tr>"
                        for year in school_year_counts
                    ])
                }
            </table>
        </div>
        
        <div class="section">
            <h2>Most Recent Grades (limited to 200)</h2>
            <table>
                <tr>
                    <th>ID</th>
                    <th>Student ID</th>
                    <th>Course</th>
                    <th>Quarter</th>
                    <th>Grade</th>
                    <th>School Year</th>
                    <th>Uploaded At</th>
                </tr>
                {
                    ''.join([
                        f"<tr><td>{g['id']}</td><td>{g['student']}</td><td>{g['course']}</td><td>{g['quarter']}</td><td>{g['grade']}</td><td>{g['school_year']}</td><td>{g['uploaded_at']}</td></tr>"
                        for g in grades
                    ])
                }
            </table>
        </div>
    </body>
    </html>
    """
    
    return HttpResponse(html_output)