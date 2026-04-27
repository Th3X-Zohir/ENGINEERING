from rest_framework.pagination import CursorPagination, PageNumberPagination


class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class TaskCursorPagination(CursorPagination):
    """
    Cursor pagination for large task datasets (100k+ tasks).
    More efficient than page number pagination — uses a pointer
    instead of OFFSET which slows down on large tables.
    """
    page_size = 20
    ordering = '-created_at'
    cursor_query_param = 'cursor'