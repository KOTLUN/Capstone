from django import template

register = template.Library()

@register.filter(name='get_current_grade')
def get_current_grade(student, subject=None):
    """
    Template filter to get a student's current grade for a subject
    """
    try:
        # Get the most recent grade for the student and subject
        grade = student.grades.filter(subject=subject).first()
        if grade:
            return grade.final_grade or grade.q4_grade or grade.q3_grade or grade.q2_grade or grade.q1_grade
        return None
    except Exception:
        return None

@register.filter
def get_quarter_grade(grade_obj, quarter):
    """
    Get the grade for a specific quarter
    Usage: {{ grade|get_quarter_grade:1 }} for first quarter
    """
    quarter_map = {
        '1': 'q1_grade',
        '2': 'q2_grade',
        '3': 'q3_grade',
        '4': 'q4_grade'
    }
    
    try:
        quarter_field = quarter_map.get(str(quarter))
        if quarter_field:
            return getattr(grade_obj, quarter_field, None)
        return None
    except (AttributeError, ValueError):
        return None 