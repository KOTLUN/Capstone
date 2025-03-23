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