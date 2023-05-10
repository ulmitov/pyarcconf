"""Arcconf Task class"""


class Task():
    """Object which represents a task."""

    def __init__(self):
        """Initialize a new Task object."""
        self.logical_device = None
        self.task_id = None
        self.current_operation = None
        self.status = None
        self.priority = None
        self.percentage_complete = None

    def __str__(self):
        """Build a string formatted object representation."""
        return '{}|{} for {}: {} ({}%)'.format(self.task_id, self.current_operation,
                                               self.logical_drive, self.status,
                                               self.percentage_complete)
