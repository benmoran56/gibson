import threading

# TODO: finish this


class Database:
    def __init__(self, filename='db.json'):
        self._lock = threading.Lock()
        self._db = {}

    def update(self, key, value):
        with self._lock:
            self._db[key] = value

    def get(self, key):
        with self._lock:
            return self._db.get([key], None)

