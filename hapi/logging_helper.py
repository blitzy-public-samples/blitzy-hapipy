"""Logging configuration helper module for the hapi package.

Provides a no-op log handler setup (NullHandler) and a logger factory
function (get_log) that ensures loggers are safe to use even when the
consuming application has not configured logging.

This module participates in a dual-module logging pattern within hapi:
both hapi/logging_helper.py and hapi/utils.py contain identical
NullHandler and get_log implementations. This module is imported by
hapi/leads.py (via 'import logging_helper'), while hapi/utils.py
serves the same logging purpose for other modules in the package.

The NullHandler prevents 'No handlers could be found for logger X'
warnings that Python's logging module emits when a logger has no
handlers attached and the consuming application does not configure
logging.

Key Exports:
    NullHandler: A no-op logging handler discarding all log records.
    get_log: Factory function returning a logger with NullHandler attached.

Usage::

    from hapi.logging_helper import get_log
    logger = get_log('hapi.leads')
    logger.debug('This will be silently discarded if no handlers configured.')
"""
import logging

# Why: [Assumptions Made] — A custom NullHandler is implemented rather than
# using logging.NullHandler because this codebase targets Python 2.x where
# logging.NullHandler was only added in Python 2.7. This ensures compatibility
# with Python 2.6 and earlier versions.
class NullHandler(logging.Handler):
    """A no-op logging handler that discards all log records.

    Prevents 'No handlers could be found for logger' warnings in
    Python 2.x by serving as a silent sink for log output. Python 2.7+
    includes logging.NullHandler natively, but this custom implementation
    provides backward compatibility with Python 2.6 and earlier.

    Inherits from:
        logging.Handler: The base handler class in Python's logging module.
    """

    def emit(self, record):
        """Discard the log record without producing any output.

        This is a no-op implementation that silently drops every log
        record routed to this handler, preventing unintended stderr
        output when no application-level logging configuration exists.

        Args:
            record (logging.LogRecord): The log record to handle.
                Ignored entirely by this implementation.

        Returns:
            None
        """
        pass

# Why: [Alternatives Considered] — A dedicated get_log factory function is used
# rather than having each module call logging.getLogger() directly because it
# ensures every logger has a NullHandler attached. Without this, modules that
# use logging would emit 'No handlers could be found' warnings when the
# consuming application doesn't configure logging. The dual existence of this
# function in both logging_helper.py and utils.py is a known duplication —
# logging_helper.py is used by hapi/leads.py while utils.py serves other
# modules. Consolidating into a single module was not done to avoid import
# cycle risks between base.py and utils.py.
def get_log(name):
    """Create and return a named logger with a NullHandler attached.

    Factory function that ensures the returned logger is safe to use
    even when no application-level logging configuration exists. Each
    call attaches a fresh NullHandler instance to the logger, which
    silently discards log output that would otherwise trigger warnings.

    Args:
        name (str): The logger name, typically a dotted module path
            such as 'hapi.leads'. Passed directly to
            logging.getLogger() to retrieve or create the logger.

    Returns:
        logging.Logger: A configured logger instance with a
            NullHandler attached, ready for use by calling code.
    """
    logger = logging.getLogger(name)
    logger.addHandler(NullHandler())
    return logger
