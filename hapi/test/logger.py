"""Test logging configuration utility for the hapipy test suite.

Sets up dual-handler logging for the 'hapi' logger used during test
execution. The logging pipeline consists of:

    - A DEBUG-level ``logging.FileHandler`` writing to ``test_run.log``
      (overwritten each run via ``mode='w'``) for comprehensive
      request/response tracing.
    - An INFO-level ``logging.StreamHandler`` writing to ``sys.stdout``
      with an abbreviated minute:second timestamp format for concise
      console output.

This module executes ``configure_log()`` at import time as a side effect,
so importing this module from any test file automatically configures the
test logging pipeline without requiring explicit setup.

The 'hapi' logger configured here captures all logging from hapi domain
clients (which use ``utils.get_log('hapipy')`` or
``logging_helper.get_log()``) during integration test execution, providing
visibility into HTTP request construction, retry behavior, and error
handling.

Reference:
    Used by ``hapi/test/test_leads.py`` (imported at module level) and
    potentially other test modules that need diagnostic logging during
    integration test runs.
"""
import logging
import sys
import os


# Why: [Alternatives Considered] — Logging configuration is encapsulated in a
# function rather than bare module-level statements because it allows the
# configuration to be re-invoked if needed and makes the setup logic testable.
# However, the module-level call at the bottom of this module means this
# function effectively runs as a side effect of import, combining the
# flexibility of a function with the convenience of automatic configuration.
def configure_log():
    """Configure the 'hapi' logger with dual handlers for test execution diagnostics.

    Set up a two-channel logging pipeline that captures all log output from
    hapi domain clients during integration test runs. A FileHandler provides
    comprehensive DEBUG-level log capture to a file, while a StreamHandler
    provides filtered INFO-level output for interactive test sessions.

    Handler configuration:
        - **FileHandler**: Writes to ``test_run.log`` in the same directory
          as this module, using ``mode='w'`` to overwrite previous test run
          logs. Set to DEBUG level to capture all log messages including
          internal client request/response tracing.
        - **StreamHandler**: Writes to ``sys.stdout`` with INFO level,
          showing only informational messages and above during test console
          output. Uses abbreviated ``datefmt='%M:%S'`` (minutes:seconds
          only) to reduce console noise.
        - Both handlers use format:
          ``'%(asctime)s %(levelname)-5s %(name)s === %(message)s'``

    Returns:
        logging.Logger: The configured 'hapi' logger instance. The return
            value is typically ignored since the module-level call at the
            bottom of this module relies on the side effect of mutating
            the global logging state.

    Note:
        Handlers are added unconditionally without checking for duplicates.
        If this module were imported multiple times (which Python's import
        system prevents for the same module path), handlers would be
        duplicated. The module-level invocation ensures ``configure_log()``
        runs exactly once at first import.
    """

    log = logging.getLogger("hapi")
    log.setLevel(logging.DEBUG)

    # Why: [Trade-offs] — mode='w' overwrites the previous test_run.log on each
    # import (i.e., each test session). This means only the most recent test
    # run's logs are preserved. An alternative would be mode='a' to append across
    # runs, but overwriting keeps the log file small and relevant to the current
    # debugging session. The file is placed adjacent to this module
    # (os.path.dirname(__file__)) to keep test artifacts co-located with test code.
    file_handler = logging.FileHandler(os.path.join(os.path.dirname(__file__), 'test_run.log'), mode="w")
    file_handler.setLevel(logging.DEBUG)

    # Why: [Alternatives Considered] — sys.stdout is used instead of the default
    # sys.stderr because nose and unittest2 test runners capture stdout for test
    # output, making INFO-level messages visible in test results. stderr would
    # bypass test runner capture and appear mixed with test framework output.
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s %(levelname)-5s %(name)s === %(message)s')
    file_handler.setFormatter(formatter)

    # Why: [Trade-offs] — The console handler uses abbreviated minute:second
    # timestamps rather than full datetime because test runs are typically short
    # (seconds to minutes) and full timestamps add visual noise to console output.
    # The FileHandler retains the default full timestamp format for post-mortem
    # log analysis.
    formatter = logging.Formatter('%(asctime)s %(levelname)-5s %(name)s === %(message)s', datefmt='%M:%S')
    console_handler.setFormatter(formatter)

    log.addHandler(file_handler)
    log.addHandler(console_handler)

    return log

# Why: [Assumptions Made] — configure_log() is called at module scope so that
# any test file importing this module (e.g., 'import logger' in test_leads.py)
# automatically gets the logging pipeline configured as a side effect. This
# relies on Python's import-once semantics to prevent duplicate handler
# attachment. The return value is discarded because the logger is retrieved
# via logging.getLogger('hapi') wherever needed.
configure_log()
