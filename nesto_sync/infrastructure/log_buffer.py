"""
Log Buffer - Buffer en memoria para almacenar logs del módulo

Permite consultar los últimos logs vía API sin necesidad de acceder a journalctl
"""
import logging
from collections import deque
from datetime import datetime
from threading import Lock


class InMemoryLogHandler(logging.Handler):
    """
    Handler de logging que almacena logs en memoria

    Thread-safe mediante Lock
    """

    _instance = None
    _lock = Lock()

    def __new__(cls, max_logs=200):
        """Singleton pattern para compartir buffer entre todos los loggers"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, max_logs=200):
        """
        Inicializa el handler

        Args:
            max_logs: Número máximo de logs a mantener en memoria
        """
        if self._initialized:
            return

        super().__init__()
        self.max_logs = max_logs
        self.logs = deque(maxlen=max_logs)
        self._initialized = True

        # Configurar formato
        formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S.%f'
        )
        self.setFormatter(formatter)

    def emit(self, record):
        """
        Guarda el log en el buffer

        Args:
            record: LogRecord de Python
        """
        try:
            # Formatear el log
            log_entry = self.format(record)

            # Añadir al buffer (thread-safe gracias a deque)
            with self._lock:
                self.logs.append({
                    'timestamp': datetime.now().isoformat(),
                    'level': record.levelname,
                    'logger': record.name,
                    'message': log_entry
                })
        except Exception:
            self.handleError(record)

    def get_logs(self, limit=None):
        """
        Obtiene los últimos logs

        Args:
            limit: Número máximo de logs a retornar (None = todos)

        Returns:
            List[dict]: Lista de logs
        """
        with self._lock:
            all_logs = list(self.logs)

        # Retornar en orden inverso (más recientes primero)
        logs = list(reversed(all_logs))

        if limit:
            logs = logs[:limit]

        return logs

    def clear(self):
        """Limpia todos los logs del buffer"""
        with self._lock:
            self.logs.clear()


def setup_log_buffer():
    """
    Configura el log buffer para el módulo nesto_sync

    Debe llamarse al iniciar el módulo
    """
    # Crear handler
    handler = InMemoryLogHandler(max_logs=200)
    handler.setLevel(logging.DEBUG)

    # Añadir a todos los loggers del módulo nesto_sync
    loggers_to_capture = [
        'odoo.addons.nesto_sync',
        'odoo.addons.nesto_sync.core',
        'odoo.addons.nesto_sync.core.odoo_publisher',
        'odoo.addons.nesto_sync.core.generic_service',
        'odoo.addons.nesto_sync.infrastructure',
        'odoo.addons.nesto_sync.models',
        'odoo.addons.nesto_sync.controllers',
    ]

    for logger_name in loggers_to_capture:
        logger = logging.getLogger(logger_name)

        # Evitar duplicados
        if handler not in logger.handlers:
            logger.addHandler(handler)
            logger.setLevel(logging.DEBUG)

    return handler
