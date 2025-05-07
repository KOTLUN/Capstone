from django import template

register = template.Library()

@register.filter
def average(grades):
    """Calculate average of grades"""
    if not grades:
        return 0
    return sum(grades) / len(grades)

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key, []) 