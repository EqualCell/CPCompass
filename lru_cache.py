"""Thread-safe O(1) LRU cache using a dictionary and doubly linked list."""

from threading import RLock


class _Node:
    def __init__(self, key=None, value=None):
        self.key = key
        self.value = value
        self.prev = None
        self.next = None


class LRUCache:
    def __init__(self, capacity=10):
        if not isinstance(capacity, int) or isinstance(capacity, bool) or capacity < 1:
            raise ValueError("capacity must be a positive integer")
        self.capacity = capacity
        self._nodes = {}
        self._head = _Node()
        self._tail = _Node()
        self._head.next = self._tail
        self._tail.prev = self._head
        self._hits = 0
        self._misses = 0
        self._lock = RLock()

    def _unlink(self, node):
        node.prev.next = node.next
        node.next.prev = node.prev

    def _make_recent(self, node):
        node.prev = self._tail.prev
        node.next = self._tail
        node.prev.next = node
        self._tail.prev = node

    def get(self, key):
        with self._lock:
            node = self._nodes.get(key)
            if node is None:
                self._misses += 1
                return None
            self._hits += 1
            self._unlink(node)
            self._make_recent(node)
            return node.value

    def put(self, key, value):
        with self._lock:
            node = self._nodes.get(key)
            if node is not None:
                node.value = value
                self._unlink(node)
            else:
                node = _Node(key, value)
                self._nodes[key] = node
            self._make_recent(node)
            if len(self._nodes) > self.capacity:
                oldest = self._head.next
                self._unlink(oldest)
                del self._nodes[oldest.key]

    def stats(self):
        with self._lock:
            total = self._hits + self._misses
            return {
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(100 * self._hits / total, 2) if total else 0.0,
                "size": len(self._nodes),
                "capacity": self.capacity,
            }
