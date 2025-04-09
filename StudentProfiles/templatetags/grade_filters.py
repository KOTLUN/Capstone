from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key, [])

@register.filter
def average(grades):
    valid_grades = [float(g) for g in grades if g and g != 'N/A']
    if valid_grades:
        return sum(valid_grades) / len(valid_grades)
    return 0 