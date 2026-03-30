# -*- coding: utf-8 -*-
from django.views.generic import TemplateView

from apps.catalog.search_escape import build_escape_queryset


class EscapeSearchView(TemplateView):
    template_name = "catalog/escape_search.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        q = (self.request.GET.get("q") or "").strip()

        parsed = None
        results = []
        total = 0

        if q:
            parsed, qs = build_escape_queryset(q)
            results = list(qs[:48])
            total = qs.count()

        context.update({
            "q": q,
            "parsed": parsed,
            "results": results,
            "total": total,
        })
        return context
