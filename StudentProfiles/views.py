from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect
from dashboard.models import Student, Enrollment, Guardian

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