from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db.models import F, Count
from .models import Student, Section, Enrollment
import json

def enrollment_page(request):
    return render(request, 'enrollment.html')

@require_http_methods(["GET"])
def get_available_students(request):
    # Get students who are not yet enrolled
    available_students = Student.objects.exclude(
        id__in=Enrollment.objects.values('student_id')
    ).values('id', 'first_name', 'last_name')
    return JsonResponse(list(available_students), safe=False)

@require_http_methods(["GET"])
def get_available_sections(request):
    # Get sections with their current capacity
    sections = Section.objects.annotate(
        enrolled_count=Count('enrollment')
    ).filter(
        enrolled_count__lt=F('capacity')  # Only get sections that aren't full
    ).values('id', 'name', 'grade', 'capacity')
    
    # Add remaining capacity information
    for section in sections:
        section['capacity_left'] = section['capacity'] - section['enrolled_count']
    
    return JsonResponse(list(sections), safe=False)

@require_http_methods(["POST"])
def enroll_student(request):
    try:
        data = json.loads(request.body)
        student_id = data['student_id']
        section_id = data['section_id']

        # Check if section has capacity
        section = Section.objects.annotate(
            enrolled_count=Count('enrollment')
        ).get(id=section_id)
        
        if section.enrolled_count >= section.capacity:
            return JsonResponse({
                'message': 'Section is already full'
            }, status=400)

        # Create enrollment
        Enrollment.objects.create(
            student_id=student_id,
            section_id=section_id
        )
        
        return JsonResponse({'message': 'Enrollment successful'})
    except Exception as e:
        return JsonResponse({
            'message': str(e)
        }, status=400) 