from django import template

from apps.catalog.public_visibility import text_contains_removed_terms

register = template.Library()


@register.filter(name="publicly_hidden_term")
def publicly_hidden_term(value):
    return text_contains_removed_terms(value)
