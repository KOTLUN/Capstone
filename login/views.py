from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from dashboard.views import dashboard_view
from dashboard.models import Teachers, Student, StudentAccount
from django.contrib.auth.views import (
    PasswordResetView, 
    PasswordResetDoneView,
    PasswordResetConfirmView,
    PasswordResetCompleteView
)

from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.shortcuts import render, redirect
from dashboard.models import Teachers, Student
from django.urls import reverse_lazy, reverse
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.conf import settings
import os
import base64
from email.mime.text import MIMEText
from django.utils import timezone
import logging
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

# Set up logging
logger = logging.getLogger(__name__)


def login_view(request):
    """Handle login and root URL access"""
    # If user is already authenticated, redirect to appropriate dashboard
    if request.user.is_authenticated:
        if request.user.is_superuser:
            return redirect('dashboard:dashboard')
        try:
            teacher = Teachers.objects.get(user=request.user)
            return redirect('TeacherPortal:profile')
        except Teachers.DoesNotExist:
            try:
                student = Student.objects.get(user=request.user)
                return redirect('student_profile', student_id=student.id)
            except Student.DoesNotExist:
                logout(request)
                request.session.flush()
                messages.error(request, "No associated profile found. Please contact the administrator.")
                return render(request, 'login.html')

    # Handle login form submission
    if request.method == "POST":
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None and user.is_active:
            login(request, user)
            
            # Check if user needs to change password
            try:
                teacher = Teachers.objects.get(user=user)
                if teacher.force_password_change:
                    return redirect('force_password_change')
            except Teachers.DoesNotExist:
                try:
                    student = Student.objects.get(user=user)
                    if student.force_password_change:
                        return redirect('force_password_change')
                except Student.DoesNotExist:
                    pass
            
            # Redirect to appropriate dashboard
            if user.is_superuser:
                return redirect('dashboard:dashboard')
            try:
                teacher = Teachers.objects.get(user=user)
                return redirect('TeacherPortal:profile')
            except Teachers.DoesNotExist:
                try:
                    student = Student.objects.get(user=user)
                    return redirect('student_profile', student_id=student.id)
                except Student.DoesNotExist:
                    logout(request)
                    request.session.flush()
                    messages.error(request, "No associated profile found. Please contact the administrator.")
                    return render(request, 'login.html')
        else:
            messages.error(request, "Invalid username or password.")
    
    # For GET requests or failed login attempts, show the login page
    return render(request, 'login.html')



def logout_view(request):
    """Handle user logout and redirect to login page"""
    if request.user.is_authenticated:
        # Clear the session
        request.session.flush()
        # Logout the user
        logout(request)
        messages.success(request, "You have been successfully logged out.")
    return redirect('login')


def home_view(request):
    return render(request, 'main.html')


'''def logout_view(request):
    logout(request)
    return redirect('/')'''



'''def register_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')

        if password != confirm_password:
            messages.error(request, 'Passwords do not match')
            return render(request, 'register.html')

        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username is already taken')
            return render(request, 'register.html')

        user = User.objects.create_user(username=username, password=password)
        user.save()
        messages.success(request, 'Account created successfully. You can now login.')
        return redirect('/')

    return render(request, 'register.html')'''

# Password Reset Views
class CustomPasswordResetView(PasswordResetView):
    template_name = 'password_reset/password_reset_form.html'
    email_template_name = 'password_reset/password_reset_email.html'
    success_url = reverse_lazy('password_reset_done')

class CustomPasswordResetDoneView(PasswordResetDoneView):
    template_name = 'login/password_reset_done.html'

class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'login/password_reset_confirm.html'
    success_url = reverse_lazy('password_reset_complete')
    
    def form_valid(self, form):
        print("Password reset form is valid, processing...")
        # Save the form which updates the user's password
        form.save()
        
        # Get the user that was just updated
        user = form.user
        print(f"User password updated: {user.username}")
        
        # Update the password in the Teachers model
        try:
            teacher = Teachers.objects.get(user=user)
            # Make sure we're getting the updated password from the user model
            teacher.password = user.password
            teacher.save()
            print(f"Teacher password updated for: {teacher.username}")
        except Teachers.DoesNotExist:
            print(f"No teacher profile found for user: {user.username}")
        except Exception as e:
            print(f"Error updating teacher password: {str(e)}")
        
        # Call parent's form_valid to handle the redirect
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        print(f"Reset form context: validlink={context.get('validlink', False)}")
        return context

class CustomPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = 'login/password_reset_complete.html'

def forgot_password(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        try:
            user = User.objects.get(email=email)
            # Generate password reset token
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            
            # Create reset link using the URL name
            reset_url = reverse('password_reset_confirm', kwargs={'uidb64': uid, 'token': token})
            reset_link = f"{request.scheme}://{request.get_host()}{reset_url}"
            
            # Send email using Django's send_mail
            subject = "Password Reset Request"
            message = f"""
            Hello {user.username},
            
            You recently requested to reset your password. Click the link below to reset it:
            
            {reset_link}
            
            If you did not request a password reset, please ignore this email.
            
            This link will expire in 24 hours.
            
            Regards,
            SCSHS Team
            """
            
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
            
            messages.success(request, "Password reset link has been sent to your email.")
            return redirect('password_reset_done')
        except User.DoesNotExist:
            messages.error(request, "No user is associated with this email address.")
    
    return render(request, 'login/password_reset_form.html')

@login_required
def teacher_dashboard(request):
    try:
        # Check if user is a teacher
        teacher = Teachers.objects.get(user=request.user)
        logger.info(f"Teacher {teacher.first_name} {teacher.last_name} accessing dashboard")
        return redirect('TeacherPortal:profile')  # Redirect to teacher profile page
    except Teachers.DoesNotExist:
        logger.error(f"Non-teacher user {request.user.username} attempted to access teacher dashboard")
        messages.error(request, "You don't have permission to access the teacher dashboard.")
        return redirect('login')

@login_required
def admin_dashboard(request):
    if not request.user.is_superuser:
        return redirect('login')
    return redirect('dashboard:dashboard')  # Updated namespace

@login_required
def student_dashboard(request):
    try:
        # Check if the user is properly authenticated
        if not request.user.is_authenticated:
            logger.error(f"User {request.user.email} is not authenticated")
            messages.error(request, "Please log in to access your dashboard.")
            return redirect('login')
            
        # Get the student profile associated with the user
        try:
            student = Student.objects.get(user=request.user)
            if not student.has_account:
                logger.error(f"Student {student.email} does not have an active account")
                messages.error(request, "Your account is not activated. Please contact the administrator.")
                return redirect('login')
                
            logger.info(f"Found student profile for user {request.user.email} with ID {student.id}")
            return redirect('student_profile', student_id=student.id)
            
        except Student.DoesNotExist:
            logger.error(f"No student profile found for user {request.user.email}")
            messages.error(request, "Student profile not found. Please contact the administrator.")
            return redirect('login')
            
    except Exception as e:
        logger.error(f"Error in student_dashboard: {str(e)}")
        messages.error(request, "An error occurred. Please try again.")
        return redirect('login')

def root_view(request):
    """Handle root URL access and redirect appropriately"""
    if not request.user.is_authenticated:
        # Clear any existing session data
        request.session.flush()
        return redirect('login')
    
    # Redirect authenticated users to their dashboard/profile
    if request.user.is_superuser:
        return redirect('dashboard:dashboard')
    try:
        teacher = Teachers.objects.get(user=request.user)
        return redirect('TeacherPortal:profile')
    except Teachers.DoesNotExist:
        pass
    try:
        student = Student.objects.get(user=request.user)
        return redirect('student_profile', student_id=student.id)
    except Student.DoesNotExist:
        pass
    
    # If no profile found, log out and show login
    logout(request)
    request.session.flush()  # Clear session data
    messages.error(request, "No associated profile found. Please contact the administrator.")
    return redirect('login')

@login_required
def force_password_change(request):
    if request.method == 'POST':
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        # Verify current password
        if not request.user.check_password(current_password):
            messages.error(request, 'Current password is incorrect.')
            return render(request, 'login/force_password_change.html')
        
        # Check if new passwords match
        if new_password != confirm_password:
            messages.error(request, 'New passwords do not match.')
            return render(request, 'login/force_password_change.html')
        
        # Validate new password
        try:
            validate_password(new_password, request.user)
        except ValidationError as e:
            messages.error(request, '\n'.join(e.messages))
            return render(request, 'login/force_password_change.html')
        
        # Update password in User model
        request.user.set_password(new_password)
        request.user.save()
        
        # Update password and force_password_change flag in Teacher/Student model
        try:
            teacher = Teachers.objects.get(user=request.user)
            teacher.password = request.user.password  # Sync with User model's password
            teacher.force_password_change = False
            teacher.save()
            logger.info(f"Teacher {teacher.username} changed password successfully")
            messages.success(request, 'Password changed successfully.')
            return redirect('/teacher/profile/')  # Redirect to teacher profile
        except Teachers.DoesNotExist:
            try:
                student = Student.objects.get(user=request.user)
                student.password = request.user.password  # Sync with User model's password
                student.force_password_change = False
                student.save()
                logger.info(f"Student {student.username} changed password successfully")
                messages.success(request, 'Password changed successfully.')
                return redirect(f'/student-profile/{student.id}/')  # Redirect to student profile
            except Student.DoesNotExist:
                logger.error(f"No Teacher or Student profile found for user {request.user.username}")
                messages.error(request, "No associated profile found. Please contact the administrator.")
                return redirect('login')
    
    return render(request, 'login/force_password_change.html')

@login_required
def proceed_to_login(request):
    """Handle the proceed to login action, keeping the generated password"""
    try:
        # Check if user is a teacher
        teacher = Teachers.objects.get(user=request.user)
        if teacher.force_password_change:
            # Keep the force_password_change flag as True
            return redirect('TeacherPortal:profile')
    except Teachers.DoesNotExist:
        try:
            # Check if user is a student
            student = Student.objects.get(user=request.user)
            if student.force_password_change:
                # Keep the force_password_change flag as True
                return redirect('student_profile', student_id=student.id)
        except Student.DoesNotExist:
            pass
    
    # If no profile found or not forced to change password, redirect to login
    messages.error(request, "No associated profile found. Please contact the administrator.")
    return redirect('login')


