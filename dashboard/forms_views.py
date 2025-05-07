from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .forms_models import SchoolForm, TeacherForm, FormSubmission
from django.http import HttpResponseForbidden
import os

@login_required
def all_forms_view(request):
    """View all available forms"""
    try:
        # Get all active forms
        if request.user.is_staff:
            # Admin can see all forms
            forms = SchoolForm.objects.filter(is_active=True).order_by('-date_uploaded')
        else:
            # Teachers can only see forms not uploaded by admin
            forms = SchoolForm.objects.filter(
                is_active=True,
                uploaded_by__is_staff=False
            ).order_by('-date_uploaded')
        
        # Get forms submitted by the current user
        my_forms = SchoolForm.objects.filter(
            uploaded_by=request.user.username,
            is_active=True
        ).order_by('-date_uploaded')
        
        # Get forms assigned to the current teacher
        teacher_forms = TeacherForm.objects.filter(
            teacher=request.user,
            form__is_active=True
        ).select_related('form')
        
        # Get pending submissions for administrators
        pending_submissions = None
        if request.user.is_staff:
            pending_submissions = FormSubmission.objects.filter(
                status='pending'
            ).select_related(
                'teacher_form',
                'teacher_form__form',
                'teacher_form__teacher'
            ).order_by('-submitted_date')
        
        context = {
            'forms': forms,
            'my_forms': my_forms,
            'teacher_forms': teacher_forms,
            'pending_submissions': pending_submissions,
            'is_admin': request.user.is_staff,
        }
        
        return render(request, 'allforms.html', context)
        
    except Exception as e:
        messages.error(request, f'Error loading forms: {str(e)}')
        return redirect('dashboard:allforms')

@login_required
def upload_form(request):
    """Handle form file uploads"""
    if request.method == 'POST':
        try:
            # Get form data
            title = request.POST.get('title')
            category = request.POST.get('category')
            description = request.POST.get('description')
            form_file = request.FILES.get('form_file')

            # Validate required fields
            if not all([title, category, form_file]):
                messages.error(request, 'Please fill in all required fields.')
                return redirect('dashboard:allforms')

            # Validate file size (10MB limit)
            if form_file.size > 10 * 1024 * 1024:
                messages.error(request, 'File size exceeds the 10MB limit.')
                return redirect('dashboard:allforms')

            # Validate file type
            allowed_extensions = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.jpg', '.jpeg', '.png']
            file_extension = os.path.splitext(form_file.name)[1].lower()
            if file_extension not in allowed_extensions:
                messages.error(request, 'Invalid file type. Allowed types: PDF, DOC, DOCX, XLS, XLSX, PPT, PPTX, JPG, JPEG, PNG')
                return redirect('dashboard:allforms')

            # Create new SchoolForm instance
            form = SchoolForm.objects.create(
                title=title,
                category=category,
                description=description,
                file=form_file,
                uploaded_by=request.user.username,
                is_active=True
            )

            messages.success(request, 'Form uploaded successfully!')
            return redirect('dashboard:allforms')

        except Exception as e:
            messages.error(request, f'Error uploading form: {str(e)}')
            return redirect('dashboard:allforms')

    # If not POST request, redirect to forms page
    return redirect('dashboard:allforms')

@login_required
def delete_form(request, form_id):
    """Delete a form and its associated file"""
    try:
        form = get_object_or_404(SchoolForm, id=form_id)
        
        # Check if user is authorized to delete
        if request.user.username != form.uploaded_by:
            return HttpResponseForbidden("You are not authorized to delete this form.")
        
        # Delete the file from storage if it exists
        if form.file:
            if os.path.isfile(form.file.path):
                os.remove(form.file.path)
        
        # Delete the form from database
        form.delete()
        
        messages.success(request, 'Form deleted successfully!')
        return redirect('dashboard:allforms')
        
    except Exception as e:
        messages.error(request, f'Error deleting form: {str(e)}')
        return redirect('dashboard:allforms')

@login_required
def submit_form(request, form_id):
    """Handle form submission by teachers"""
    if request.method == 'POST':
        try:
            form = get_object_or_404(SchoolForm, id=form_id)
            submitted_file = request.FILES.get('submitted_file')
            
            if not submitted_file:
                messages.error(request, 'Please attach a file.')
                return redirect('dashboard:allforms')
            
            # Create or update TeacherForm
            teacher_form, created = TeacherForm.objects.get_or_create(
                teacher=request.user,
                form=form,
                defaults={'is_completed': False}
            )
            
            # Create FormSubmission
            submission = FormSubmission.objects.create(
                teacher_form=teacher_form,
                submitted_file=submitted_file,
                status='pending'
            )
            
            messages.success(request, 'Form submitted successfully!')
            return redirect('dashboard:allforms')
            
        except Exception as e:
            messages.error(request, f'Error submitting form: {str(e)}')
            return redirect('dashboard:allforms')
    
    return redirect('dashboard:allforms')

@login_required
def review_submission(request, submission_id):
    """Review a form submission"""
    if request.method == 'POST':
        try:
            submission = get_object_or_404(FormSubmission, id=submission_id)
            status = request.POST.get('status')
            feedback = request.POST.get('feedback')
            
            if status not in ['approved', 'rejected']:
                messages.error(request, 'Invalid status.')
                return redirect('dashboard:allforms')
            
            submission.status = status
            submission.feedback = feedback
            submission.reviewed_by = request.user
            submission.review_date = timezone.now()
            submission.save()
            
            if status == 'approved':
                submission.teacher_form.is_completed = True
                submission.teacher_form.completed_date = timezone.now()
                submission.teacher_form.save()
            
            messages.success(request, f'Submission {status} successfully!')
            return redirect('dashboard:allforms')
            
        except Exception as e:
            messages.error(request, f'Error reviewing submission: {str(e)}')
            return redirect('dashboard:allforms')
    
    return redirect('dashboard:allforms') 