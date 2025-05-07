from django import template
import json
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Q
from django.template.defaultfilters import register

@register.filter
def get_item(dictionary, key):
    """
    Template filter to get an item from a dictionary using a key.
    Usage: {{ dictionary|get_item:key }}
    """
    if not dictionary:
        return None
    try:
        return dictionary.get(key)
    except (AttributeError, TypeError):
        return None

@register.filter(name='safe_json')
def safe_json(obj):
    """
    Safely converts a Django model instance to JSON for use in JavaScript
    """
    if hasattr(obj, '__dict__'):
        # Get sections data
        sections_data = []
        if hasattr(obj, 'sections_set'):
            sections_data = [{
                'grade_level': section.grade_level,
                'section_id': section.section_id
            } for section in obj.sections_set.all()]

        # Get schedules data
        schedules_data = []
        if hasattr(obj, 'schedules_set'):
            schedules_data = [{
                'subject': {
                    'name': schedule.subject.name
                },
                'grade_level': schedule.grade_level,
                'section': {
                    'section_id': schedule.section.section_id
                }
            } for schedule in obj.schedules_set.all()]

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
            'sections_set': sections_data,
            'schedules_set': schedules_data
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

@register.filter
def uniquify(value, arg):
    """Remove duplicates from a list based on an attribute"""
    seen = set()
    unique_items = []
    
    for item in value:
        # Get the attribute value using the arg string
        attr_value = getattr(item, arg)
        if attr_value not in seen:
            seen.add(attr_value)
            unique_items.append(item)
    
    return unique_items