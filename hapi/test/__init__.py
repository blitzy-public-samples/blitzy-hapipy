"""Test suite package for the hapipy HubSpot API wrapper library.

This ``__init__.py`` serves as the Python package marker for ``hapi.test``,
enabling import of test modules (e.g., ``from hapi.test import helper``) and
providing a discoverable namespace for the nose and unittest2 test runners.
The file contains no executable code; its sole purpose is package registration
and developer orientation through this docstring.

Test Suite Structure
--------------------
The package contains five test modules covering the hapipy client surface:

**test_base**
    Unit tests for the ``BaseClient`` core HTTP engine mechanics.  Validates
    request preparation (URL encoding with ``doseq``), retry-with-backoff
    behaviour, and response body parsing (plain text, JSON, gzip-compressed
    JSON).  Does *not* require live HubSpot API credentials — exercises
    ``BaseClient`` through a mock subclass (``TestBaseClient``) and
    monkey-patched request executors, keeping tests fully self-contained.

**test_broadcast**
    Integration tests for ``BroadcastClient`` social-media broadcast and
    channel CRUD operations.  Exercises ``get_broadcasts``,
    ``get_broadcast``, ``get_channels``, and ``create_broadcast`` against the
    live HubSpot Broadcast API v1.  Requires valid API credentials.  Every
    test method is decorated with ``@attr('api')`` so that integration tests
    can be selected or excluded via ``nosetests -a api``.

**test_error**
    Unit tests for the ``HapiError`` exception hierarchy, focusing on
    unicode safety of the ``__str__`` / ``__unicode__`` rendering pipeline
    and graceful handling of missing HTTP result or request context
    (``None`` arguments).  Uses nose.tools function-based test discovery
    (``test_unicode_error``, ``test_error_with_no_result_or_request``) with
    ``ok_`` assertions rather than a ``unittest2.TestCase`` subclass.

**test_keywords**
    Integration tests for ``KeywordsClient`` keyword CRUD operations and
    UTF-8 round-trip fidelity.  Covers ``get_keywords``, ``get_keyword``,
    ``add_keyword`` (single), ``add_keywords`` (batch), ``delete_keyword``,
    and ``test_utf8_keywords`` (validates non-ASCII characters survive the
    create-then-fetch cycle).  Requires live API credentials.  Tests are
    ``@attr('api')`` tagged.

**test_leads**
    Unit tests for ``LeadsClient.camelcase_search_options`` parameter
    conversion logic.  Verifies that snake_case option keys and values are
    correctly transformed to the camelCase format expected by the HubSpot
    Leads API v2.  Constructs a ``LeadsClient`` with credentials but only
    exercises local conversion logic — no live API calls are made.

Test Infrastructure
-------------------
Two helper modules support test execution:

**helper**
    Credential loading utility.  ``get_options()`` attempts to read API
    credentials from an optional ``test_credentials.json`` file co-located
    with the test package.  When the file is absent (the common case for
    open-source contributors), it falls back to ``{'api_key': 'demo'}`` —
    the HubSpot public demo portal key.  When the file is present, it must
    contain valid JSON with at least an ``api_key`` or ``hapikey`` field;
    malformed or empty credential files raise descriptive exceptions.

**logger**
    Test logging configuration.  Defines ``configure_log()`` which attaches
    a dual-handler setup to the ``'hapi'`` logger: a ``FileHandler``
    writing ``DEBUG``-level messages to ``test_run.log`` and a
    ``StreamHandler`` emitting ``INFO``-level messages to ``sys.stdout``.
    The function executes at import time (module-level
    ``configure_log()`` call), so importing any test module that
    transitively imports ``logger`` activates tracing automatically.

Testing Philosophy
------------------
The suite employs two complementary strategies:

*   **Integration tests** (``test_broadcast``, ``test_keywords``) perform
    live HTTP round-trips against the HubSpot API using real credentials.
    This provides end-to-end validation of the full request pipeline —
    authentication injection, URL construction, payload serialization, retry
    logic, and response deserialization — at the cost of requiring network
    access and a valid API key.  Each integration test class manages its own
    lifecycle cleanup in ``tearDown`` (e.g., deleting created keywords via
    ``delete_keyword``, canceling created broadcasts via
    ``cancel_broadcast``) to leave the test portal in a clean state.

*   **Unit tests** (``test_base``, ``test_error``, ``test_leads``) are
    entirely self-contained with no external service dependencies.  They
    validate internal logic (request encoding, error formatting, parameter
    conversion) through mock objects and direct function invocation,
    enabling fast, deterministic execution in any environment.

Test Framework
--------------
Most test classes inherit from ``unittest2.TestCase``, which provides
enhanced assertion methods (``assertEquals``, ``assertIsNotNone``,
``assertTrue``, ``assertRaises``) back-ported from Python 2.7+ to earlier
Python 2.x releases.  Integration tests are additionally decorated with
``nose.plugins.attrib.attr('api')`` for selective execution — run all
tests with ``nosetests``, or restrict to integration tests with
``nosetests -a api``.  The ``test_error`` module is an exception: it uses
nose.tools function-based test discovery (plain module-level functions
prefixed with ``test_``) and ``ok_`` assertions, forgoing a ``TestCase``
class entirely.

Credential Management
---------------------
Credentials are centralized through ``helper.get_options()``, which returns
a dict suitable for ``**kwargs`` expansion into any client constructor.
The ``test_credentials.json`` file is **optional** — when absent, the
``'demo'`` API key is used, granting read-only access to HubSpot's public
demo portal (portal ID 62515).  To run integration tests with write access,
create the JSON file alongside this package with at minimum::

    {"api_key": "your-hubspot-api-key"}

or equivalently::

    {"hapikey": "your-hubspot-api-key"}

OAuth credentials (``access_token``, ``refresh_token``, ``client_id``)
are also supported by the helper but are commented out in the default
configuration.

Test Execution
--------------
Three test modules support standalone execution via a module-level
``unittest2.main()`` call: ``test_broadcast.py``, ``test_keywords.py``,
and ``test_leads.py``.  These can be run directly as scripts::

    python hapi/test/test_keywords.py

For full suite execution, use nose from the repository root::

    nosetests hapi/test/

To run only integration tests that require live credentials::

    nosetests -a api hapi/test/

To run only fast unit tests (no network required)::

    nosetests hapi/test/test_base.py hapi/test/test_error.py hapi/test/test_leads.py
"""
