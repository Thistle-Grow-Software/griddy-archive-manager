from rest_framework.pagination import CursorPagination


class DefaultCursorPagination(CursorPagination):
    page_size = 50
    ordering = "-pk"


class GamePagination(CursorPagination):
    page_size = 50
    ordering = "-date_local"


class PlayPagination(CursorPagination):
    page_size = 100
    ordering = "sequence"
