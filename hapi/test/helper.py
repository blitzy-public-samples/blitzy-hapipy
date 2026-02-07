"""Test credential loading and configuration utility for the hapipy integration test suite.

This module provides centralized credential management for all hapipy
integration tests. It loads API credentials from an optional
``test_credentials.json`` file located adjacent to this module. If the file
does not exist, it defaults to ``{'api_key': 'demo'}`` which uses HubSpot's
demo portal for testing.

Credential Validation Chain:
    1. File existence check (``os.path.exists``)
    2. File readability (``open().read()`` with ``IOError`` handling)
    3. JSON parse validity (``json.loads`` with ``ValueError`` handling)
    4. ``api_key`` or ``hapikey`` field presence check
    5. Key normalization (``hapikey`` mapped to ``api_key``)

This module is imported by all integration test modules
(``test_broadcast.py``, ``test_keywords.py``, ``test_leads.py``) via
``import helper`` and provides the ``get_options()`` function as the single
entry point for credential retrieval.

Note:
    The commented-out line in ``get_options`` shows the alternative OAuth
    credential format (``access_token``, ``refresh_token``, ``client_id``)
    that can be used instead of ``api_key``.
"""
import os
import json
try:
    from hapi.test import logger
except ImportError:
    import logger


def get_options():
    """Load and return a dict of HubSpot API credentials for integration test authentication.

    Attempt to read credentials from ``test_credentials.json``; fall back
    to the demo API key if the file does not exist.

    Credential Loading Flow:
        1. Construct path to ``test_credentials.json`` adjacent to this
           module file.
        2. Set default options to ``{'api_key': 'demo'}`` (HubSpot demo
           portal).
        3. If ``test_credentials.json`` exists:
           a. Read the file content (raise ``Exception`` with descriptive
              message on ``IOError``).
           b. Parse as JSON (raise ``Exception`` with descriptive message
              on ``ValueError``).
           c. Validate that either ``api_key`` or ``hapikey`` key is
              present (raise ``Exception`` if neither).
           d. Normalize: set ``options['api_key']`` to the value of
              ``options.get('api_key') or options.get('hapikey')``.
        4. Return the credentials dict.

    Returns:
        dict: Credential options dict containing at minimum ``api_key``
            (str). May also contain ``access_token``, ``refresh_token``,
            ``client_id`` and other credential fields if specified in
            ``test_credentials.json``. The dict is passed as ``**kwargs``
            to client constructors
            (e.g., ``BroadcastClient(**helper.get_options())``).

    Raises:
        Exception: If ``test_credentials.json`` exists but cannot be read
            (``IOError`` during open/read).
        Exception: If ``test_credentials.json`` exists but contains invalid
            JSON (``ValueError`` from ``json.loads``).
        Exception: If ``test_credentials.json`` exists but contains neither
            ``api_key`` nor ``hapikey`` field.

    Note:
        Uses Python 2.x raise syntax (``raise Exception, message``) which
        is not compatible with Python 3.x.
    """
    # Why: [Alternatives Considered] — JSON file credential loading from a file adjacent
    # to the module (os.path.dirname(__file__)) is used rather than environment variables
    # because the test suite was designed for local development workflows where a developer
    # places their credentials in a gitignored JSON file. Environment variables would be
    # more CI-friendly but require additional setup and are harder to manage for multiple
    # credential fields (api_key, access_token, refresh_token, client_id). The file-based
    # approach also allows developers to easily switch between API key and OAuth credentials
    # by editing a single JSON file.
    filename = 'test_credentials.json'
    path = os.path.join(os.path.dirname(__file__), filename)
    # Why: [Trade-offs] — The 'demo' API key provides a fallback that allows tests to run
    # against HubSpot's public demo portal without any developer configuration. This makes
    # the test suite immediately runnable for new developers, but the demo portal has limited
    # data and rate limits that may cause some integration tests to fail or behave
    # unexpectedly. The trade-off favors developer experience (works out of the box) over
    # test reliability.
    options = {'api_key':'demo'}
    # Why: [Alternatives Considered] — The commented-out OAuth credential format shows that
    # the test suite supports three authentication modes (API key, access_token,
    # refresh_token+client_id) matching BaseClient's constructor parameters. It is left as a
    # comment rather than documentation because it serves as a copy-paste template for
    # developers who want to use OAuth credentials.
    #options = {'access_token':'your_access_token', 'refresh_token':'clients_refresh_token', 'client_id':'your_app_client_ID'}
    # Why: [Trade-offs] — The three-stage validation (file readable -> valid JSON -> has
    # credentials) with descriptive Exception messages is designed to fail fast with clear
    # diagnostics when credentials are misconfigured. Each Exception message explains both
    # what went wrong AND what the developer should do to fix it. This is more verbose than
    # a simple 'invalid config' error but significantly reduces debugging time for new
    # contributors. The Python 2.x raise syntax (comma-separated) is used because this
    # codebase targets Python 2.x.
    if os.path.exists(path):
        try:
            raw_text = open(path).read()
        except IOError:
            raise Exception("""
                Unable to open '%s' for integration tests.\n
                If this file exists, then you are indicating you want to override the standard 'demo' creds with your own.\n
                However, it is currently inaccessible so that is a problem.""" % filename)
        try:
            options = json.loads(raw_text)
        except ValueError:
            raise Exception("""
                '%s' doesn't appear to be valid json!\n
                If this file exists, then you are indicating you want to override the standard 'demo' creds with your own.\n
                However, if I can't understand the json inside of it, then that is a problem.""" % filename)

        if not options.get('api_key') and not options.get('hapikey'):
            raise Exception("""
                '%s' seems to have no 'api_key' or 'access_token' specified!\n
                If this file exists, then you are indicating you want to override the standard 'demo' creds with your own.\n
                However, I'll need at least an API key to work with, or it definitely won't work.""" % filename)
        # Why: [Assumptions Made] — The normalization options['api_key'] = options.get('api_key')
        # or options.get('hapikey') handles the fact that HubSpot's API uses 'hapikey' as the
        # query parameter name while the Python client uses 'api_key' as the constructor
        # parameter. This allows test_credentials.json to use either key name, reducing
        # configuration friction. The 'or' expression means api_key takes precedence over
        # hapikey when both are present.
        options['api_key'] = options.get('api_key') or options.get('hapikey')

    return options
