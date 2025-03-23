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

# Set up logging
logger = logging.getLogger(__name__)

def login_view(request):
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
            logger.info(f"Is superuser: {user.is_superuser}")
            
            # Check if the user is an admin
            if user.is_superuser:
                logger.info("User is superuser, redirecting to dashboard")
                return redirect('dashboard')

            # Check if the user is a teacher
            try:
                teacher_profile = Teachers.objects.get(user=user)
                logger.info(f"User is a teacher: {teacher_profile.first_name} {teacher_profile.last_name}")
                return redirect('profile')
            except Teachers.DoesNotExist:
                logger.info("User is not a teacher")
                
                # Check if user has a student profile directly
                try:
                    student = Student.objects.get(user=user)
                    logger.info(f"Found student profile: {student.first_name} {student.last_name} (ID: {student.id})")
                    
                    # Redirect to student profile
                    return redirect('student_profile', student_id=student.id)
                except Student.DoesNotExist:
                    logger.info("No direct student profile found")
                    
                    # Try to find student through StudentAccount
                    try:
                        student_account = StudentAccount.objects.get(user=user)
                        logger.info(f"Found student account for student ID: {student_account.student.id}")
                        
                        # Update last login time
                        student_account.last_login = timezone.now()
                        student_account.save(update_fields=['last_login'])
                        
                        # Redirect to student profile
                        return redirect('student_profile', student_id=student_account.student.id)
                    except StudentAccount.DoesNotExist:
                        logger.error(f"No student account found for user ID: {user.id}")
                        messages.error(request, "Access denied. You are not authorized to access this system.")
                        logout(request)  # Log out the user since they don't have proper access
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


