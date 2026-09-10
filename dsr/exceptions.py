class InvalidStatusTransition(Exception):
    """Raised when a requested DSR status change violates the status state machine."""
