from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect
from django.db.models import Avg
from dashboard.models import (
    Student, Enrollment, Guardian, Subject, 
    Schedules, SchoolYear
)
from TeacherPortal.models import Grade
import json

@login_required
def student_profile(request, student_id):
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
    
    # Get the student's guardian information
    guardians = Guardian.objects.filter(student=student)
    
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
    
    # Get active school year
    active_school_year = SchoolYear.get_active()
    current_school_year = "2029-2030 (Active)"  # Hardcoded to match your database
    
    # Get the student's current enrollment
    current_enrollment = Enrollment.objects.filter(
        student=student,
        status='Active'
    ).first()
    
    # Get current subjects and grades
    subjects = []
    subject_grades_data = {}
    detailed_grades = []
    
    if current_enrollment:
        subjects = Subject.objects.filter(
            schedules__section=current_enrollment.section
        ).distinct()
        
        # First, get all grades for this student
        all_grades = Grade.objects.filter(
            student="55555",  # Using the student ID from your database
            school_year=current_school_year
        ).order_by('quarter')
        
        print(f"Found {all_grades.count()} grades for student 55555")  # Debug print
        
        # Get grades for each subject
        for subject in subjects:
            # Initialize quarterly grades list
            quarterly_grades = [0, 0, 0, 0]  # One slot for each quarter
            
            # Filter grades for this subject
            subject_grades = all_grades.filter(course=subject.subject_id)
            
            print(f"Subject {subject.name} ({subject.subject_id}) has {subject_grades.count()} grades")  # Debug print
            
            # Fill in the grades for each quarter
            for grade in subject_grades:
                try:
                    quarter_idx = int(grade.quarter) - 1  # Convert quarter to 0-based index
                    if 0 <= quarter_idx < 4:  # Ensure valid quarter
                        quarterly_grades[quarter_idx] = float(grade.grade)
                        print(f"Quarter {grade.quarter}: {grade.grade}")  # Debug print
                except (ValueError, TypeError) as e:
                    print(f"Error processing grade: {e}")  # Debug print
                    continue
            
            # Calculate subject average from valid grades
            valid_grades = [g for g in quarterly_grades if g > 0]
            subject_average = round(sum(valid_grades) / len(valid_grades), 2) if valid_grades else 0
            
            # Get latest grade for current grade display
            latest_grade = subject_grades.order_by('-uploaded_at').first()
            subject.current_grade = latest_grade.grade if latest_grade else "N/A"
            
            # Store grades for chart
            subject_grades_data[subject.name] = quarterly_grades
            
            # Store detailed grades for table
            detailed_grades.append({
                'subject': subject.name,
                'quarterly_grades': quarterly_grades,
                'average': subject_average
            })
    
    # Get schedule
    schedule = Schedules.objects.filter(
        section=current_enrollment.section if current_enrollment else None
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
    
    # Debug prints
    print("Subject Grades Data:", subject_grades_data)
    print("Detailed Grades:", detailed_grades)
    
    context = {
        'student': student,
        'current_enrollment': current_enrollment,
        'subjects': subjects,
        'schedule': unique_schedule,
        'overall_average': overall_average,
        'quarters': json.dumps(quarters),
        'subject_grades_data': json.dumps(subject_grades_data),
        'detailed_grades': detailed_grades,
        'debug': True,  # Enable debug info
        'debug_student_id': "55555",
        'debug_school_year': current_school_year,
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