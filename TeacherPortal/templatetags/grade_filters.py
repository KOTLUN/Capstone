from django import template
from django.template.defaultfilters import floatformat
from decimal import Decimal

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Get item from dictionary with key"""
    if not dictionary:
        return None
    return dictionary.get(key)

@register.filter
def percentage(value, total):
    """Calculate percentage"""
    if not total:
        return 0
    return floatformat(float(value) / float(total) * 100, 1)

@register.filter
def avg(value_list):
    """Calculate average of a list of values"""
    if not value_list:
        return 0
    try:
        values = [float(v) for v in value_list if v is not None]
        if not values:
            return 0
        return sum(values) / len(values)
    except (ValueError, TypeError):
        return 0

@register.filter
def status_badge_class(status):
    """Return a Bootstrap badge class based on the grade status"""
    status_classes = {
        'draft': 'secondary',
        'submitted': 'primary',
        'approved': 'success',
        'rejected': 'danger',
        'pending': 'warning',
        'completed': 'info'
    }
    return status_classes.get(status.lower(), 'secondary')

@register.filter
def map(value_list, attribute):
    """Map a list of objects to a list of values by attribute name or dictionary key"""
    if not value_list:
        return []
    result = []
    
    for item in value_list:
        if hasattr(item, attribute):
            result.append(getattr(item, attribute))
        elif isinstance(item, dict) and attribute in item:
            result.append(item[attribute])
        else:
            result.append(None)
    
    return result

@register.filter
def filter(value_list, expression):
    """Filter a list based on an expression like 'attribute>=value'"""
    if not value_list:
        return []
    
    # Parse the expression
    if '>=' in expression:
        attr, val = expression.split('>=')
        comparison = lambda x, y: x >= y
    elif '<=' in expression:
        attr, val = expression.split('<=')
        comparison = lambda x, y: x <= y
    elif '>' in expression:
        attr, val = expression.split('>')
        comparison = lambda x, y: x > y
    elif '<' in expression:
        attr, val = expression.split('<')
        comparison = lambda x, y: x < y
    elif '=' in expression:
        attr, val = expression.split('=')
        comparison = lambda x, y: x == y
    elif '!=' in expression:
        attr, val = expression.split('!=')
        comparison = lambda x, y: x != y
    else:
        # Just check if attribute exists and is truthy
        attr = expression
        comparison = lambda x, _: bool(x)
        val = True
    
    # Convert value to appropriate type
    try:
        val = float(val)
    except (ValueError, TypeError):
        pass
    
    result = []
    for item in value_list:
        # Get the attribute value
        if attr and hasattr(item, attr):
            attr_val = getattr(item, attr)
        elif isinstance(item, dict) and attr in item:
            attr_val = item[attr]
        else:
            attr_val = item
        
        # Check if numeric values need to be converted
        if isinstance(attr_val, (str, Decimal)) and val is not None:
            try:
                attr_val = float(attr_val)
            except (ValueError, TypeError):
                pass
                
        # Apply the comparison
        if comparison(attr_val, val):
            result.append(item)
    
    return result 

@register.filter
def filter_by_quarter_subject(grades, params):
    """
    Filter grades by quarter and subject
    Usage: {{ grades|filter_by_quarter_subject:quarter,subject_id }}
    """
    if not grades:
        return []
    
    params_list = params.split(',')
    if len(params_list) != 2:
        return []
    
    quarter = params_list[0].strip()
    subject_id = params_list[1].strip()
    
    try:
        subject_id = int(subject_id)
    except (ValueError, TypeError):
        return []
        
    filtered_grades = []
    for grade in grades:
        # Check if quarter matches
        if str(grade.quarter) == quarter:
            # Handle different ways the course might be stored
            if hasattr(grade, 'course') and hasattr(grade.course, 'subject'):
                # If course is an object with a subject attribute
                if grade.course.subject.id == subject_id:
                    filtered_grades.append(grade)
            elif hasattr(grade, 'course') and hasattr(grade.course, 'id'):
                # If course is an object with an id
                if grade.course.id == subject_id:
                    filtered_grades.append(grade)
            else:
                # If course is a string/ID that directly matches the subject ID
                try:
                    course_id = int(grade.course)
                    if course_id == subject_id:
                        filtered_grades.append(grade)
                except (ValueError, TypeError, AttributeError):
                    pass
    
    return filtered_grades