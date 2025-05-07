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

# Set up logging
logger = logging.getLogger(__name__)

def login_view(request):
    # Save the next parameter in the session if it exists
    next_url = request.GET.get('next')
    if next_url:
        request.session['next'] = next_url
        logger.info(f"Saved next URL in session: {next_url}")

    if request.method == "POST":
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        # Add debug logging
        logger.info(f"Login attempt for username: {username}")

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            
            # Log user details for debugging
            logger.info(f"User authenticated: {user.username} (ID: {user.id})")
            logger.info(f"User email: {user.email}")
            logger.info(f"User is active: {user.is_active}")
            logger.info(f"User is staff: {user.is_staff}")
            logger.info(f"User is superuser: {user.is_superuser}")
            
            # Get the next URL from session
            next_url = request.session.get('next')
            if next_url:
                del request.session['next']
                logger.info(f"Redirecting to next URL: {next_url}")
                return redirect(next_url)
            
            # Check if the user is an admin
            if user.is_superuser:
                logger.info("User is superuser, redirecting to dashboard")
                return redirect('dashboard:dashboard')

            # Check if the user is a teacher
            try:
                teacher = Teachers.objects.get(user=user)
                logger.info(f"Teacher authenticated: {teacher.first_name} {teacher.last_name}")
                logger.info(f"Teacher email: {teacher.email}")
                logger.info(f"Teacher has user account: {teacher.user is not None}")
                return redirect('TeacherPortal:profile')
            except Teachers.DoesNotExist:
                logger.info(f"No teacher profile found for user: {user.username}")

            # Check if the user is a student
            try:
                student = Student.objects.get(user=user)
                logger.info(f"Student authenticated: {student.first_name} {student.last_name}")
                logger.info(f"Student email: {student.email}")
                logger.info(f"Student has account: {student.has_account}")
                logger.info(f"Student has user account: {student.user is not None}")
                return redirect('student_profile', student_id=student.id)
            except Student.DoesNotExist:
                logger.error(f"User {username} has no associated teacher or student profile")
                messages.error(request, "Invalid username or password.")
                logout(request)
                return redirect('login')
        else:
            logger.warning(f"Authentication failed for username: {username}")
            messages.error(request, "Invalid username or password.")

    return render(request, 'login.html')




def logout_view(request):
    logout(request)
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
    if not request.user.email.endswith('@admin.stcfi.edu.ph'):
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
    if not request.user.is_authenticated:
        return render(request, 'login.html')
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
    # If no profile, log out and show login
    logout(request)
    messages.error(request, "No associated profile found. Please contact the administrator.")
    return render(request, 'login.html')


