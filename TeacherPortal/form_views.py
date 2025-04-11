import os
import mimetypes
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.db.models import Q

from .form_models import SchoolForm
from dashboard.models import Teachers, SchoolYear

@login_required
def forms_view(request):
    """View for forms management page"""
    try:
        teacher = Teachers.objects.get(user=request.user)
        active_school_year = SchoolYear.get_active()
        
        # Get filter parameters with defaults
        category_filter = request.GET.get('category', '')
        search_query = request.GET.get('search', '')
        
        # Get all forms (with filters if provided)
        forms_query = SchoolForm.objects.all()
        
        # Apply category filter if provided
        if category_filter:
            forms_query = forms_query.filter(category=category_filter)
        
        # Apply search filter if provided
        if search_query:
            forms_query = forms_query.filter(
                Q(title__icontains=search_query) |
                Q(description__icontains=search_query)
            )
        
        # Order by latest upload
        forms = forms_query.order_by('-date_uploaded')
        
        # Get form categories for filter
        categories = SchoolForm.CATEGORY_CHOICES
        
        context = {
            'teacher': teacher,
            'active_school_year': active_school_year,
            'forms': forms,
            'categories': categories,
            'selected_category': category_filter,
            'search_query': search_query,
            'total_forms': forms.count(),
            'can_upload': True  # You can define logic to control who can upload
        }
        
        return render(request, 'forms.html', context)
    except Exception as e:
        print(f"Error in forms_view: {str(e)}")
        return render(request, 'forms.html', {
            'error': f'Error: {str(e)}',
            'user': request.user
        })

@login_required
@require_POST
def upload_form(request):
    """Handle form file uploads"""
    try:
        teacher = Teachers.objects.get(user=request.user)
        active_school_year = SchoolYear.get_active()
        
        # Get form data
        title = request.POST.get('title')
        category = request.POST.get('category')
        description = request.POST.get('description')
        file = request.FILES.get('file')
        
        # Validate required fields
        if not all([title, category, file]):
            messages.error(request, 'Please provide a title, category, and file')
            return redirect('uploadforms')
        
        # Validate file size (10MB limit)
        if file.size > 10 * 1024 * 1024:
            messages.error(request, 'File size must be less than 10MB')
            return redirect('uploadforms')
        
        # Create new form
        form = SchoolForm(
            title=title,
            category=category,
            description=description,
            file=file,
            uploaded_by=teacher.user.username,
            school_year=active_school_year.display_name if active_school_year else None
        )
        form.save()
        
        messages.success(request, 'Form uploaded successfully')
        return redirect('uploadforms')
    except Exception as e:
        messages.error(request, f'Error uploading form: {str(e)}')
        return redirect('uploadforms')

@login_required
def download_form(request, form_id):
    """Handle form file downloads"""
    try:
        form = get_object_or_404(SchoolForm, id=form_id)
        
        # Check if file exists
        if not form.file:
            messages.error(request, 'File not found')
            return redirect('forms')
        
        # Get file path
        file_path = form.file.path
        
        # Increment download counter
        form.downloads += 1
        form.save()
        
        # Set content type based on file extension
        file_type = mimetypes.guess_type(file_path)[0]
        if not file_type:
            file_type = 'application/octet-stream'
        
        # Open file for reading
        with open(file_path, 'rb') as f:
            response = HttpResponse(f.read(), content_type=file_type)
            response['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
            return response
            
    except Exception as e:
        messages.error(request, f'Error downloading form: {str(e)}')
        return redirect('forms')

@login_required
def delete_form(request, form_id):
    """Handle form deletion"""
    try:
        form = get_object_or_404(SchoolForm, id=form_id)
        
        # Check if user is authorized to delete
        # For example, only allow the original uploader or admins
        if request.user.is_staff or form.uploaded_by == request.user.username:
            # Delete the file from storage
            if form.file:
                if os.path.exists(form.file.path):
                    os.remove(form.file.path)
            
            # Delete the database record
            form.delete()
            
            messages.success(request, 'Form deleted successfully')
        else:
            messages.error(request, 'You are not authorized to delete this form')
            
        return redirect('forms')
    except Exception as e:
        messages.error(request, f'Error deleting form: {str(e)}')
        return redirect('forms')

@login_required
def view_form(request, form_id):
    """View form details and preview"""
    try:
        form = get_object_or_404(SchoolForm, id=form_id)
        teacher = Teachers.objects.get(user=request.user)
        
        # Check if preview is possible
        can_preview = form.file_extension in ['pdf', 'jpg', 'jpeg', 'png', 'gif']
        
        context = {
            'teacher': teacher,
            'form': form,
            'can_preview': can_preview
        }
        
        return render(request, 'form_detail.html', context)
    except Exception as e:
        messages.error(request, f'Error viewing form: {str(e)}')
        return redirect('forms')

@login_required
@require_POST
def forms_search_ajax(request):
    """API endpoint for searching forms via AJAX"""
    try:
        query = request.POST.get('query', '')
        category = request.POST.get('category', '')
        
        # Start with all forms
        forms = SchoolForm.objects.all()
        
        # Apply category filter
        if category:
            forms = forms.filter(category=category)
        
        # Apply search query
        if query:
            forms = forms.filter(
                Q(title__icontains=query) |
                Q(description__icontains=query)
            )
        
        # Limit to 20 results
        forms = forms.order_by('-date_uploaded')[:20]
        
        forms_data = [{
            'id': form.id,
            'title': form.title,
            'category': form.get_category_display(),
            'file_type': form.file_type,
            'uploaded_by': form.uploaded_by,
            'date_uploaded': form.date_uploaded.strftime('%Y-%m-%d'),
            'file_size': form.file_size_display,
            'downloads': form.downloads,
            'icon_class': form.file_icon_class
        } for form in forms]
        
        return JsonResponse({
            'success': True,
            'forms': forms_data,
            'count': len(forms_data)
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
def upload_forms_page(request):
    """View for the form upload page"""
    try:
        teacher = Teachers.objects.get(user=request.user)
        active_school_year = SchoolYear.get_active()
        
        # Get filter parameters with defaults
        category_filter = request.GET.get('category', '')
        search_query = request.GET.get('search', '')
        
        # Get all forms (with filters if provided)
        forms_query = SchoolForm.objects.all()
        
        # Apply category filter if provided
        if category_filter:
            forms_query = forms_query.filter(category=category_filter)
        
        # Apply search filter if provided
        if search_query:
            forms_query = forms_query.filter(
                Q(title__icontains=search_query) |
                Q(description__icontains=search_query)
            )
        
        # Order by latest upload
        forms = forms_query.order_by('-date_uploaded')
        
        # Get the form categories for the dropdown
        categories = SchoolForm.CATEGORY_CHOICES
        
        context = {
            'teacher': teacher,
            'active_school_year': active_school_year,
            'categories': categories,
            'forms': forms,
            'selected_category': category_filter,
            'search_query': search_query,
            'total_forms': forms.count(),
        }
        
        return render(request, 'uploadforms.html', context)
    except Exception as e:
        print(f"Error in upload_forms_page: {str(e)}")
        return render(request, 'uploadforms.html', {
            'error': f'Error: {str(e)}',
            'user': request.user
        })