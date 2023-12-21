class UndoStack():
    STACK_SIZE = 10

    def __init__(self):
        self.clear()

    def push(self, obj):
        self._cur_pos += 1
        self._undo_stack.append(obj)
        if len(self._undo_stack) > self.STACK_SIZE:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def push_undo(self, obj):
        self._cur_pos += 1
        self._undo_stack.append(obj)

    def push_redo(self, obj):
        self._cur_pos -= 1
        self._redo_stack.append(obj)

    def can_undo(self):
        return bool(self._undo_stack)

    def undo(self):
        if not self.can_undo():
            raise LookupError

        return self._undo_stack.pop()

    def can_redo(self):
        return bool(self._redo_stack)

    def redo(self):
        if not self.can_redo():
            raise LookupError

        return self._redo_stack.pop()

    def clear(self):
        self.is_overflow = False
        self._undo_stack = []
        self._redo_stack = []
        self._cur_pos = 0
        self._pos = 0

    def store_pos(self):
        self._cur_pos = 0
        self._pos = 0
#        self._pos = self._cur_pos

    def is_pos_changed(self):
        return self._pos != self._cur_pos
