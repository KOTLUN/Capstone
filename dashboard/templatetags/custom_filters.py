from django import template
import json
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Q

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

@register.filter(name='safe_json')
def safe_json(obj):
    """
    Safely converts a Django model instance to JSON for use in JavaScript
    """
    if hasattr(obj, '__dict__'):
        data = {
            'teacher_id': obj.teacher_id,
            'first_name': obj.first_name,
            'middle_name': obj.middle_name,
            'last_name': obj.last_name,
            'gender': obj.gender,
            'religion': obj.religion,
            'date_of_birth': obj.date_of_birth.isoformat() if obj.date_of_birth else None,
            'email': obj.email,
            'mobile_number': obj.mobile_number,
            'address': obj.address,
            'img_url': obj.teacher_photo.url if obj.teacher_photo else None,
        }
        return json.dumps(data, cls=DjangoJSONEncoder)
    return '{}'

@register.filter
def get_current_grade(student, subject):
    """Get the current grade for a student in a subject"""
    try:
        grade = Grades.objects.filter(
            student=student,
            subject=subject
        ).order_by('-date_updated').first()
        
        if grade:
            # Return the most recent quarter grade that exists
            for quarter in ['q4_grade', 'q3_grade', 'q2_grade', 'q1_grade']:
                if getattr(grade, quarter) is not None:
                    return getattr(grade, quarter)
        return None
    except:
        return None