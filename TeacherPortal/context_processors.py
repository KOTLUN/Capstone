from dashboard.models import Teachers, Registrar, SchoolYear

def teacher_context(request):
    """Context processor to add teacher-related context variables"""
    context = {}
    
    if request.user.is_authenticated:
        try:
            teacher = Teachers.objects.get(user=request.user)
            active_school_year = SchoolYear.get_active()
            
            # Check if teacher is a registrar for the active school year
            is_registrar = False
            if active_school_year:
                is_registrar = Registrar.objects.filter(
                    teacher=teacher,
                    school_year=active_school_year,
                    is_active=True
                ).exists()
            
            context['is_registrar'] = is_registrar
            context['teacher'] = teacher
            context['active_school_year'] = active_school_year
            
        except Teachers.DoesNotExist:
            pass
    
    return context 