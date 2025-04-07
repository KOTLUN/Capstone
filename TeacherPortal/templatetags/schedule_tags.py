from django import template

register = template.Library()

@register.filter
def split(value, delimiter=','):
    """Split a string into a list using the given delimiter"""
    return [x.strip() for x in value.split(delimiter)]

@register.filter
def subtract(value, arg):
    """Subtract the arg from the value"""
    return value - len(arg)

@register.filter
def get_range(value):
    """Return a range of numbers from 0 to value"""
    return range(value) 