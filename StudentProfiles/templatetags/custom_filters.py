from django import template

register = template.Library()

@register.filter
def split(value, delimiter=','):
    """
    Returns a list of strings, split by delimiter
    """
    return value.split(delimiter) 