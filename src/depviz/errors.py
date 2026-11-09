"""Исключения инструмента depviz."""


class DepvizError(Exception):
    """Базовое исключение: сообщение предназначено для пользователя."""


class ConfigError(DepvizError):
    """Ошибка в конфигурационном файле или в значении параметра."""


class RepositoryError(DepvizError):
    """Ошибка получения или разбора данных репозитория пакетов."""


class RenderError(DepvizError):
    """Ошибка построения изображения графа."""
