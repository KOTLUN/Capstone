from social_core.pipeline.user import get_username
from dashboard.models import Teachers, Student, StudentAccount
from django.contrib.auth.models import User
import logging
from social_core.pipeline.social_auth import social_user
from social_core.exceptions import AuthAlreadyAssociated, AuthForbidden
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.utils import timezone

logger = logging.getLogger(__name__)

def check_existing_email(strategy, details, user=None, *args, **kwargs):
    """Check if the email from Google matches an existing user or profile"""
    email = details.get('email')
    logger.info(f"=== Starting Google Login Process ===")
    logger.info(f"Email from Google: {email}")
    logger.info(f"Current user: {user}")
    logger.info(f"Strategy: {strategy}")
    logger.info(f"Details: {details}")
    logger.info(f"Additional args: {kwargs}")

    if email:
        try:
            # First check if this email belongs to a student
            student = Student.objects.filter(email__iexact=email).first()
            if student:
                logger.info(f"Found student: {student.first_name} {student.last_name}")
                logger.info(f"Student email: {student.email}")
                logger.info(f"Has account: {student.has_account}")
                
                # Try to get the student account
                try:
                    student_account = StudentAccount.objects.get(student=student)
                    logger.info(f"Found student account: {student_account}")
                    logger.info(f"Account is active: {student_account.is_active}")
                    logger.info(f"Associated user: {student_account.user}")
                    
                    if student_account.is_active:
                        # Return the user object to be used by the next pipeline step
                        return {'user': student_account.user}
                except StudentAccount.DoesNotExist:
                    logger.warning(f"No student account found for student {student.email}")
                
                return {'student': student}

            # Check for teacher account
            teacher = Teachers.objects.filter(email__iexact=email).first()
            if teacher:
                logger.info(f"Found teacher: {teacher.first_name} {teacher.last_name}")
                if teacher.user:
                    logger.info(f"Found teacher user account: {teacher.user}")
                    return {'user': teacher.user}
                return {'teacher': teacher}

            logger.warning(f"No matching student or teacher found for email: {email}")
            return {
                'error': 'no_profile',
                'message': f"No profile found for email: {email}. Please contact the administrator."
            }

        except Exception as e:
            logger.error(f"Error in check_existing_email: {str(e)}", exc_info=True)
            return {
                'error': 'exception',
                'message': f"An error occurred: {str(e)}"
            }

    logger.warning("No email provided in Google login details")
    return {
        'error': 'no_email',
        'message': "No email provided. Please try again."
    }

def associate_by_email(strategy, details, user=None, *args, **kwargs):
    """Associate the Google account with an existing user"""
    logger.info("=== Starting Email Association ===")
    logger.info(f"Details: {details}")
    logger.info(f"Current user: {user}")
    logger.info(f"Additional args: {kwargs}")

    if user:
        logger.info(f"User already exists: {user.username}")
        return {'user': user}

    if 'error' in kwargs:
        messages.error(strategy.request, kwargs.get('message', 'An error occurred'))
        return redirect('login')

    # Get the user from the previous step
    user = kwargs.get('user')
    if user:
        logger.info(f"Using existing user: {user.username}")
        return {'user': user}

    return None

def redirect_by_role(strategy, details, user=None, *args, **kwargs):
    """Handle final redirect after successful authentication"""
    logger.info("=== Starting Role-based Redirect ===")
    logger.info(f"User: {user}")
    logger.info(f"Details: {details}")
    
    if not user:
        logger.warning("No user object in redirect_by_role")
        messages.error(strategy.request, "Login failed. Please try again.")
        return redirect('login')

    try:
        # Check for student
        student_account = StudentAccount.objects.filter(user=user).first()
        if student_account:
            logger.info(f"Redirecting student to profile: {student_account.student.id}")
            return redirect('student_profile', student_id=student_account.student.id)

        # Check for teacher
        teacher = Teachers.objects.filter(user=user).first()
        if teacher:
            logger.info("Redirecting teacher to profile")
            return redirect('TeacherPortal:profile')

        logger.warning(f"No profile found for user: {user.username}")
        messages.error(strategy.request, "No associated profile found.")
        return redirect('login')

    except Exception as e:
        logger.error(f"Error in redirect_by_role: {str(e)}", exc_info=True)
        messages.error(strategy.request, "An error occurred during login.")
        return redirect('login') 