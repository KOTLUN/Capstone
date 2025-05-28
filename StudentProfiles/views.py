from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect
from django.db.models import Avg, Q
from dashboard.models import (
    Student, Enrollment, Guardian, Subject, 
    Schedules, SchoolYear, Grade8Enrollment,
    Grade9Enrollment, Grade10Enrollment,
    Grade11Enrollment, Grade12Enrollment,Grades,
    Announcement, Feedback
)
import json
from decimal import Decimal
from django.utils import timezone
from django.http import HttpResponse
from random import randint
from django.db import connection
from django.contrib.auth.hashers import check_password
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth import update_session_auth_hash

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
    
    # Get all events
    from dashboard.models import Event
    events = Event.objects.all().order_by('start_date', 'start_time')
    
    # Convert events to JSON format for the calendar
    events_json = json.dumps([{
        'id': event.id,
        'title': event.title,
        'description': event.description,
        'start_date': event.start_date.strftime('%Y-%m-%d'),
        'start_time': event.start_time.strftime('%H:%M'),
        'end_date': event.end_date.strftime('%Y-%m-%d'),
        'end_time': event.end_time.strftime('%H:%M')
    } for event in events])
    
    # Get recent announcements
    announcements = Announcement.objects.all().order_by('-created_at')[:5]
    
    context = {
        'student': student,
        'is_enrolled': current_enrollment is not None,
        'guardians': guardians,
        'events_json': events_json,
        'announcements': announcements,
    }
    
    return render(request, 'student_profile.html', context)

from dashboard.models import Grades  # Make sure this is imported

@login_required
@login_required
def student_dashboard(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    if request.user != student.user and not request.user.is_staff:
        messages.error(request, "You don't have permission to view this dashboard.")
        return redirect('login')

    school_years = SchoolYear.objects.all().order_by('-year_start')

    try:
        active_school_year = SchoolYear.objects.get(is_active=True)
    except SchoolYear.DoesNotExist:
        messages.error(request, "No active school year found.")
        return redirect('login')

    current_school_year = active_school_year
    current_school_year_display = f"{active_school_year.year_start}-{active_school_year.year_end} (Active)"
    current_enrollment = get_current_enrollment(student, current_school_year)

    quarters_display = ['First Quarter', 'Second Quarter', 'Third Quarter', 'Fourth Quarter']

    # Get all grades for this student in the current school year
    grades = Grades.objects.select_related('subject').filter(
        student=student,
        school_year=current_school_year
    ).order_by('subject__name', 'quarter')

    # Build a set of subjects that have grades
    subjects_with_grades = set(grade.subject for grade in grades)

    # Only build subject_grades for these subjects
    subject_grades = {}
    for subject in subjects_with_grades:
        subject_grades[subject.name] = {
            'quarters': {},
            'average': None,
            'status': 'No Grades'
        }

    # Fill in grade data
    for grade in grades:
        subject_name = grade.subject.name
        quarter = str(grade.quarter)
        if subject_name in subject_grades:
            subject_grades[subject_name]['quarters'][quarter] = {
                'grade': float(grade.grade),
                'status': grade.status,
                'remarks': grade.remarks,
                'uploaded_at': grade.uploaded_at.strftime('%Y-%m-%d %H:%M:%S') if grade.uploaded_at else None
            }

    # Compute average and status
    for subject_name, data in subject_grades.items():
        valid_grades = [q['grade'] for q in data['quarters'].values() if q and 'grade' in q]
        if valid_grades:
            data['average'] = sum(valid_grades) / len(valid_grades)
            data['status'] = 'Passing' if data['average'] >= 75 else 'Failing'

    # Chart data
    chart_data = {}
    for subject, data in subject_grades.items():
        if data['quarters']:
            chart_data[subject] = []
            for q in range(1, 5):
                quarter_data = data['quarters'].get(str(q), {})
                chart_data[subject].append(quarter_data.get('grade'))

    detailed_grades = bool(chart_data)

    subject_grades_metadata = {}
    for subject, data in subject_grades.items():
        subject_grades_metadata[subject] = {}
        for quarter, grade_data in data['quarters'].items():
            subject_grades_metadata[subject][quarter] = {
                'status': grade_data.get('status'),
                'remarks': grade_data.get('remarks'),
                'uploaded_at': grade_data.get('uploaded_at')
            }

    # Get recent announcements
    announcements = Announcement.objects.all().order_by('-created_at')[:5]

    context = {
        'student': student,
        'current_enrollment': current_enrollment,
        'current_school_year': current_school_year,
        'active_school_year': active_school_year,
        'school_years': school_years,
        'school_year_display': current_school_year_display,
        'quarters': quarters_display,
        'quarters_json': json.dumps(quarters_display),
        'subject_grades_data': chart_data,
        'subject_grades_data_json': json.dumps(chart_data),
        'subject_grades_metadata': json.dumps(subject_grades_metadata),
        'detailed_grades': detailed_grades,
        'has_grades': bool(chart_data),
        'subject_grades': subject_grades,
        'announcements': announcements,
    }

    return render(request, 'mydashboard.html', context)

@login_required
def student_grades(request, student_id):
    try:
        student = Student.objects.get(student_id=student_id)
    
        # Check if the requesting user is the student or a staff member
        if not (request.user == student.user or request.user.is_staff):
            messages.error(request, "You don't have permission to view these grades.")
            return redirect('login')
    
        # Get all school years for the dropdown
        school_years = SchoolYear.objects.all().order_by('-year_start')
        
        # Get active school year
        try:
            active_school_year = SchoolYear.objects.get(is_active=True)
            current_school_year = f"{active_school_year.year_start}-{active_school_year.year_end}"
        except SchoolYear.DoesNotExist:
            messages.error(request, "No active school year found.")
            return redirect('login')
    
        # Get all grades for this student in the current school year
        from dashboard.models import Grades as TeacherGrade
        grades = TeacherGrade.objects.filter(
            student=student_id,
            school_year=current_school_year
        )
    
        # Build a set of subjects that have grades
        subjects_with_grades = set(Subject.objects.get(subject_id=grade.course) for grade in grades)
    
        # Only build subject_grades for these subjects
        subject_grades = {}
        for subject in subjects_with_grades:
            subject_grades[subject.name] = {
                'grades': {'1': None, '2': None, '3': None, '4': None},
                'final_grade': None,
                'status': 'No Grades'
            }
    
        # Process grades by subject
        for grade in grades:
            try:
                subject = Subject.objects.get(subject_id=grade.course)
                if subject.name not in subject_grades:
                    continue  # Only process grades for subjects with grades
                subject_grades[subject.name]['grades'][grade.quarter] = grade.grade
                # Calculate final grade for available quarters
                valid_grades = [g for g in subject_grades[subject.name]['grades'].values() if g is not None]
                if valid_grades:
                    final_grade = sum(valid_grades) / len(valid_grades)
                    subject_grades[subject.name]['final_grade'] = final_grade
                    subject_grades[subject.name]['status'] = 'Passing' if final_grade >= 75 else 'Failing'
            except Subject.DoesNotExist:
                continue
    
        context = {
            'student': student,
            'current_school_year': current_school_year,
            'school_years': school_years,
            'subject_grades': subject_grades
        }
        
        return render(request, 'student_grades.html', context)
        
    except Student.DoesNotExist:
        messages.error(request, "Student not found.")
        return redirect('login')
    except Exception as e:
        messages.error(request, f"An error occurred: {str(e)}")
        return redirect('login')

@login_required
def student_subjects(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    
    if request.user != student.user and not request.user.is_staff:
        messages.error(request, "You don't have permission to view this dashboard.")
        return redirect('login')
    
    # Get active school year
    try:
        active_school_year = SchoolYear.objects.get(is_active=True)
        current_school_year = f"{active_school_year.year_start}-{active_school_year.year_end}"
    except SchoolYear.DoesNotExist:
        messages.error(request, "No active school year found.")
        return redirect('login')
    
    # Get current enrollment
    current_enrollment = get_current_enrollment(student, current_school_year)
    
    # Get subjects
    subjects = []
    if current_enrollment:
        subjects = Subject.objects.filter(
            schedules__section=current_enrollment.section
        ).distinct()
    
    # Get recent announcements
    announcements = Announcement.objects.all().order_by('-created_at')[:5]
    
    context = {
        'student': student,
        'current_enrollment': current_enrollment,
        'current_school_year': current_school_year,
        'subjects': subjects,
        'announcements': announcements,
    }
    
    return render(request, 'student_subjects.html', context)

@login_required
def student_schedule(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    
    if request.user != student.user and not request.user.is_staff:
        messages.error(request, "You don't have permission to view this dashboard.")
        return redirect('login')
    
    # Get active school year
    try:
        active_school_year = SchoolYear.objects.get(is_active=True)
        current_school_year = f"{active_school_year.year_start}-{active_school_year.year_end}"
    except SchoolYear.DoesNotExist:
        messages.error(request, "No active school year found.")
        return redirect('login')
    
    # Get current enrollment
    current_enrollment = get_current_enrollment(student, current_school_year)
    
    # Get schedule
    schedule = []
    if current_enrollment:
        schedule = Schedules.objects.filter(
            section=current_enrollment.section
        ).order_by('start_time')
    
    # Get recent announcements
    announcements = Announcement.objects.all().order_by('-created_at')[:5]
    
    context = {
        'student': student,
        'current_enrollment': current_enrollment,
        'current_school_year': current_school_year,
        'schedule': schedule,
        'announcements': announcements,
    }
    
    return render(request, 'student_schedule.html', context)

def get_current_enrollment(student, current_school_year):
    # Define enrollment models for each grade level
    enrollment_models = {
        7: Enrollment,
        8: Grade8Enrollment,
        9: Grade9Enrollment,
        10: Grade10Enrollment,
        11: Grade11Enrollment,
        12: Grade12Enrollment
    }
    
    # Try to find enrollment in any grade level for the active school year
    for grade_level, model in enrollment_models.items():
        enrollment = model.objects.filter(
            student_id=student.id,
            school_year=current_school_year,
            status__in=['Active', 'Transferee']  # Include both Active and Transferee statuses
        ).first()
        if enrollment:
            return enrollment
    return None

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
    active_school_year = SchoolYear.objects.filter(is_active=True).first()
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

@login_required
def get_grade_analytics(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    print(f"Debug: Found student with ID {student.id} and student_id {student.student_id}")
    
    if request.user != student.user and not request.user.is_staff:
        messages.error(request, "You don't have permission to view this data.")
        return redirect('login')
    
    # Get active school year
    try:
        active_school_year = SchoolYear.objects.get(is_active=True)
        # Format school year to match the database format
        current_school_year = f"{active_school_year.year_start}-{active_school_year.year_end} (Active)"
        print(f"Debug: Current school year: {current_school_year}")
    except SchoolYear.DoesNotExist:
        print("Debug: No active school year found")
        messages.error(request, "No active school year found.")
        return redirect('login')
    
    # Initialize data structures
    subject_grades = {}
    quarters = ['1', '2', '3', '4']
    detailed_grades = False
    
    try:
        # Get all subjects from the dashboard_subject table
        subjects = Subject.objects.all()
        print(f"Debug: Found {subjects.count()} subjects in total")
        
        # Initialize subject_grades dictionary with all subjects
        for subject in subjects:
            subject_grades[subject.name] = {q: None for q in quarters}
            print(f"Debug: Initialized grades for subject: {subject.name} ({subject.subject_id})")
        
        # Fetch grades using raw SQL for reliability
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    g.course, 
                    g.quarter, 
                    g.grade, 
                    s.name as subject_name,
                    g.status,
                    g.remarks,
                    g.uploaded_at,
                    g.date_created,
                    g.date_modified,
                    g.date_submitted,
                    g.date_approved
                FROM teacherportal_grade g
                JOIN dashboard_subject s ON g.course = s.subject_id
                WHERE g.student = %s 
                AND g.school_year = %s
                ORDER BY g.course, g.quarter
            """, [student.student_id, current_school_year])
            
            grades = cursor.fetchall()
            print(f"Debug: Found {len(grades)} grades in database")
            
            # Process each grade
            for grade_row in grades:
                course_id, quarter, grade_value, subject_name, status, remarks, uploaded_at, date_created, date_modified, date_submitted, date_approved = grade_row
                try:
                    if subject_name in subject_grades:
                        # Store grade value and additional metadata
                        subject_grades[subject_name][quarter] = {
                            'grade': float(grade_value) if grade_value is not None else None,
                            'status': status,
                            'remarks': remarks,
                            'uploaded_at': uploaded_at.strftime('%Y-%m-%d %H:%M:%S') if uploaded_at else None,
                            'date_created': date_created.strftime('%Y-%m-%d %H:%M:%S') if date_created else None,
                            'date_modified': date_modified.strftime('%Y-%m-%d %H:%M:%S') if date_modified else None,
                            'date_submitted': date_submitted.strftime('%Y-%m-%d %H:%M:%S') if date_submitted else None,
                            'date_approved': date_approved.strftime('%Y-%m-%d %H:%M:%S') if date_approved else None
                        }
                        print(f"Debug: Processed grade for {subject_name}, Q{quarter}: {grade_value}")
                except (ValueError, IndexError) as e:
                    print(f"Debug: Error processing grade: {e}")
                    continue
        
        # Convert the data structure to lists for each subject
        chart_data = {
            subject: [grades[q]['grade'] if grades[q] and 'grade' in grades[q] else None for q in quarters]
            for subject, grades in subject_grades.items()
            if any(grades[q] and 'grade' in grades[q] for q in quarters)  # Only include subjects with grades
        }
        
        # Check if we have any valid grades
        detailed_grades = bool(chart_data)
        print(f"Debug: Has detailed grades: {detailed_grades}")
        print("Debug: Chart data:")
        for subject, grades in chart_data.items():
            print(f"  - {subject}: {grades}")
        
        # Convert data to JSON-safe format
        import json
        chart_data_json = json.dumps(chart_data)
        quarters_display = ['First Quarter', 'Second Quarter', 'Third Quarter', 'Fourth Quarter']
        quarters_json = json.dumps(quarters_display)
        
        context = {
            'student': student,
            'current_school_year': current_school_year,
            'quarters': quarters_display,
            'quarters_json': quarters_json,
            'subject_grades_data': chart_data,
            'subject_grades_data_json': chart_data_json,
            'detailed_grades': detailed_grades,
            'has_grades': bool(chart_data),
            'subject_grades_metadata': subject_grades  # Include full grade metadata
        }
        
    except Exception as e:
        print(f"Debug: Error processing grades: {str(e)}")
        import traceback
        print("Debug: Full traceback:")
        print(traceback.format_exc())
        context = {
            'student': student,
            'current_school_year': current_school_year,
            'detailed_grades': False,
            'has_grades': False,
            'error_message': "An error occurred while processing grades."
        }
    
    return render(request, 'mydashboard.html', context)

@login_required
def student_grade_details(request, student_id):
    """
    Detailed view of student grades with additional information and analytics.
    """
    student = get_object_or_404(Student, id=student_id)
    
    # Security check
    if request.user != student.user and not request.user.is_staff:
        messages.error(request, "You don't have permission to view this dashboard.")
        return redirect('login')
    
    # Get all school years for the dropdown
    school_years = SchoolYear.objects.all().order_by('-year_start')
    
    # Get active school year
    try:
        active_school_year = SchoolYear.objects.get(is_active=True)
        current_school_year = f"{active_school_year.year_start}-{active_school_year.year_end} (Active)"
    except SchoolYear.DoesNotExist:
        messages.error(request, "No active school year found.")
        return redirect('login')
    
    # Get current enrollment
    current_enrollment = get_current_enrollment(student, current_school_year)
    
    # Only get subjects for the student's enrolled section
    if current_enrollment:
        subjects = Subject.objects.filter(schedules__section=current_enrollment.section).distinct()
    else:
        subjects = Subject.objects.none()
    
    # Initialize data structures
    subject_grades = {}
    grade_analytics = {
        'total_subjects': 0,
        'subjects_with_grades': 0,
        'passing_subjects': 0,
        'failing_subjects': 0,
        'highest_grade': 0,
        'lowest_grade': 100,
        'average_grade': 0
    }
    
    try:
        grade_analytics['total_subjects'] = subjects.count()
        
        # Initialize subject_grades dictionary
        for subject in subjects:
            subject_grades[subject.name] = {
                'quarters': {},
                'average': None,
                'status': 'No Grades',
                'subject_id': subject.subject_id
            }
        
        # Fetch grades using raw SQL
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT g.course, g.quarter, g.grade, s.name as subject_name,
                       g.remarks, g.uploaded_at, g.status as grade_status
                FROM teacherportal_grade g
                JOIN dashboard_subject s ON g.course = s.subject_id
                WHERE g.student = %s 
                AND g.school_year = %s
                ORDER BY g.course, g.quarter
            """, [student.student_id, current_school_year])
            
            grades = cursor.fetchall()
            
            # Process each grade
            for grade_row in grades:
                course_id, quarter, grade_value, subject_name, remarks, uploaded_at, grade_status = grade_row
                try:
                    if subject_name in subject_grades:
                        grade_value = float(grade_value)
                        subject_grades[subject_name]['quarters'][quarter] = {
                            'grade': grade_value,
                            'remarks': remarks,
                            'uploaded_at': uploaded_at,
                            'status': grade_status
                        }
                        # Update analytics
                        if grade_value > grade_analytics['highest_grade']:
                            grade_analytics['highest_grade'] = grade_value
                        if grade_value < grade_analytics['lowest_grade']:
                            grade_analytics['lowest_grade'] = grade_value
                except (ValueError, IndexError) as e:
                    print(f"Error processing grade: {e}")
                    continue
        
        # Calculate averages and update status for each subject
        total_grades = []
        for subject_name, data in subject_grades.items():
            valid_grades = [g['grade'] for g in data['quarters'].values() if g is not None]
            if valid_grades:
                data['average'] = sum(valid_grades) / len(valid_grades)
                total_grades.append(data['average'])
                grade_analytics['subjects_with_grades'] += 1
                if data['average'] >= 75:
                    data['status'] = 'Passing'
                    grade_analytics['passing_subjects'] += 1
                else:
                    data['status'] = 'Failing'
                    grade_analytics['failing_subjects'] += 1
        
        # Calculate overall average
        if total_grades:
            grade_analytics['average_grade'] = sum(total_grades) / len(total_grades)
        
    except Exception as e:
        print(f"Error processing grades: {str(e)}")
        import traceback
        print("Full traceback:")
        print(traceback.format_exc())
    
    context = {
        'student': student,
        'current_enrollment': current_enrollment,
        'current_school_year': current_school_year,
        'school_years': school_years,
        'subject_grades': subject_grades,
        'grade_analytics': grade_analytics
    }
    
    return render(request, 'student_grade_details.html', context)

@login_required
def change_password(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    
    # Security check
    if request.user != student.user and not request.user.is_staff:
        messages.error(request, "You don't have permission to change this password.")
        return redirect('login')
    
    if request.method == 'POST':
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        # Verify current password
        if not check_password(current_password, request.user.password):
            messages.error(request, 'Current password is incorrect.')
            return redirect('student_profile', student_id=student.id)
        
        # Check if new passwords match
        if new_password != confirm_password:
            messages.error(request, 'New passwords do not match.')
            return redirect('student_profile', student_id=student.id)
        
        try:
            # Validate the new password
            validate_password(new_password, request.user)
            
            # Update the password
            request.user.set_password(new_password)
            request.user.save()
            
            # Update the session to prevent logout
            update_session_auth_hash(request, request.user)
            
            messages.success(request, 'Password updated successfully!')
            return redirect('student_profile', student_id=student.id)
            
        except ValidationError as e:
            messages.error(request, '\n'.join(e.messages))
            return redirect('student_profile', student_id=student.id)
    
    return redirect('student_profile', student_id=student.id)



@login_required
def send_feedback(request):
    student = Student.objects.get(user=request.user)  # Add this line
    if request.method == 'POST':
        message = request.POST.get('message')
        Feedback.objects.create(student=student, message=message)
        messages.success(request, 'Feedback sent to admin successfully!')
        return redirect('student_dashboard', student_id=student.id)
    return render(request, 'send_feedback.html', {'student': student})  # Pass student to template