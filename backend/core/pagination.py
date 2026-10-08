from collections import OrderedDict

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class StandardPagination(PageNumberPagination):
    """Page-number pagination whose size can be tuned by the client.

    Adds ``num_pages`` / ``current_page`` / ``page_size`` on top of DRF's default
    ``count`` / ``next`` / ``previous`` / ``results`` envelope — the frontend uses
    ``num_pages`` to decide whether to render pagination controls at all.
    """

    page_size = 9
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response_payload(self, data):
        return OrderedDict([
            ('count', self.page.paginator.count),
            ('num_pages', self.page.paginator.num_pages),
            ('current_page', self.page.number),
            ('page_size', self.get_page_size(self.request)),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('results', data),
        ])

    def get_paginated_response(self, data):
        return Response(self.get_paginated_response_payload(data))
