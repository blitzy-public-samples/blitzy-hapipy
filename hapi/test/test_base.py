"""Test suite for BaseClient core HTTP engine mechanics.

Covers request preparation (URL construction, doseq parameter encoding),
retry behavior (exponential backoff on transient failures), and response
body processing (plain text passthrough, JSON parsing, gzip decompression).

These are deterministic unit tests that do NOT require live HubSpot API
credentials. They use a TestBaseClient subclass with a fixed _get_path
override and monkey-patched executors to isolate the retry and parsing
pipelines from network I/O.

Test framework: unittest2.TestCase
References:
    - BaseClient defined in hapi/base.py
    - HapiError from hapi/error.py
"""
from collections import defaultdict
import unittest2
import simplejson as json
from StringIO import StringIO
from gzip import GzipFile

from hapi.base import BaseClient
from hapi.error import HapiError


# Why: [Alternatives Considered] — A concrete subclass with a fixed _get_path
# override is used rather than mocking BaseClient directly because
# BaseClient._get_path raises an exception (it is effectively abstract).
# Subclassing provides a real inheritance chain for testing the full
# _prepare_request and _call pipelines without mocking internal method
# resolution.
class TestBaseClient(BaseClient):
    """Minimal concrete subclass of BaseClient for unit testing.

    Overrides _get_path() to return a deterministic path prefix
    ('unit_path/') so that URL construction in _prepare_request is
    predictable and testable without requiring a real domain client.
    This avoids the exception raised by BaseClient._get_path and
    provides stable URL output for assertion matching.
    """

    def _get_path(self, subpath):
        """Return a fixed test path prefix concatenated with the subpath.

        Overrides the effectively-abstract BaseClient._get_path to
        provide deterministic URL segments for test isolation.

        Args:
            subpath (str): The API-specific path segment to append.

        Returns:
            str: Path string in the form 'unit_path/{subpath}'.
        """
        return 'unit_path/%s' % (subpath,)


# Why: [Trade-offs] — TestResult uses dynamic setattr-based construction rather
# than a fixed schema because different tests need different response attributes
# (e.g., body only for _call tests). The empty getheaders() satisfies
# BaseClient._execute_request_raw's header inspection without simulating
# actual HTTP headers.
class TestResult(object):
    """Lightweight fake HTTP response object for test assertions.

    Accepts arbitrary keyword attributes via __init__ and provides a
    no-op getheaders() method. Used to simulate httplib.HTTPResponse
    in test assertions without making network calls. The dynamic
    attribute approach allows each test to specify only the response
    fields it cares about.
    """

    def __init__(self, *args, **kwargs):
        """Initialize with arbitrary keyword attributes set on the instance.

        Each keyword argument is set as an instance attribute via
        setattr, enabling flexible response simulation. For example,
        TestResult(body='SUCCESS') creates an object with a .body
        attribute returning 'SUCCESS'.

        Args:
            *args: Positional arguments (accepted but unused, for
                signature compatibility).
            **kwargs: Each key-value pair is set as an instance
                attribute via setattr.

        Returns:
            None.
        """
        for k, v in kwargs.items():
            setattr(self, k, v)

    def getheaders(self):
        """Return an empty list simulating no HTTP response headers.

        Satisfies the header inspection call in
        BaseClient._execute_request_raw without requiring real
        HTTP header data.

        Returns:
            list: Empty list, simulating a response with no headers.
        """
        return []


class BaseTest(unittest2.TestCase):
    """Test class for BaseClient core HTTP engine mechanics.

    Validates request URL construction with doseq parameter handling,
    retry behavior with exponential backoff on transient failures, and
    response body processing including plain text, JSON, and gzipped
    JSON decompression.

    Tests BaseClient._prepare_request(), BaseClient._call() retry
    logic, and BaseClient._process_body() defined in hapi/base.py.

    All tests use a TestBaseClient instance with a dummy API key,
    requiring no live HubSpot API credentials.
    """

    def setUp(self):
        """Initialize a TestBaseClient instance with a dummy API key.

        Creates self.client as a TestBaseClient('unit_api_key') for
        each test. No live API connection is established; the dummy
        key satisfies BaseClient.__init__'s credential requirement.

        Returns:
            None.
        """
        self.client = TestBaseClient('unit_api_key')

    def tearDown(self):
        """Clean up test resources after each test method.

        No-op placeholder for test resource teardown. Retained for
        unittest2 fixture completeness and to provide a hook for
        future cleanup if tests acquire external resources.

        Returns:
            None.
        """
        pass

    def test_prepare_request(self):
        """Verify that _prepare_request correctly URL-encodes query parameters.

        Tests BaseClient._prepare_request() defined in hapi/base.py,
        specifically the doseq parameter behavior controlling how list
        values are serialized in the query string.

        Assertions:
            - With doseq=False: array values are encoded as a single
              parameter string (duplicate=%5B%27key%27%2C+%27value%27%5D),
              treating the list as one opaque value.
            - With doseq=True: array values are split into separate
              key=value pairs (duplicate=key&duplicate=value), producing
              one query parameter per list element.

        Returns:
            None.
        """
        subpath = 'unit_sub_path'
        params = {'duplicate': ['key', 'value']}
        data = None
        opts = {}
        doseq = False

        # with doseq=False we should encode the array
        # so duplicate=[key,value]
        url, headers, data = self.client._prepare_request(subpath, params, data, opts, doseq)
        self.assertTrue('duplicate=%5B%27key%27%2C+%27value%27%5D' in url)

        # with doseq=True the values will be split and assigned their own key
        # so duplicate=key&duplicate=value
        doseq = True
        url, headers, data = self.client._prepare_request(subpath, params, data, opts, doseq)
        print url
        self.assertTrue('duplicate=key&duplicate=' in url)
        
    def test_call(self):
        """Verify that _call correctly implements retry-then-succeed and retry-then-fail behaviors.

        Tests BaseClient._call() and BaseClient._call_raw() retry logic
        defined in hapi/base.py. Creates a TestBaseClient with a fast
        sleep_multiplier and monkey-patched request executors to isolate
        the retry pipeline from network I/O.

        Test approach:
            - First scenario: Monkey-patches _execute_request_raw with a
              function that fails once (raises HapiError) then succeeds.
              Asserts exactly 2 calls and 'SUCCESS' result.
            - Second scenario: Monkey-patches _execute_request_raw with a
              function that always raises HapiError. Asserts that HapiError
              is re-raised after retries are exhausted.

        Assertions:
            - Retry count == 2 and result == 'SUCCESS' for first scenario.
            - HapiError raised for second scenario after retry exhaustion.

        Returns:
            None.
        """
        client = TestBaseClient('key', api_base='base', env='hudson')
        # Why: [Assumptions Made] — sleep_multiplier is set to 0.02 (instead of 0)
        # to retain the retry timing logic path but keep test execution fast. Setting
        # it to exactly 0 would bypass the time.sleep() call entirely, potentially
        # masking timing-related bugs in the backoff calculation.
        client.sleep_multiplier = .02
        # Why: [Trade-offs] — Monkey-patching _create_request and _execute_request_raw
        # directly on the client instance isolates the retry logic from network I/O.
        # This is a test-only concern — production code never modifies these methods.
        # The lambda returning None for _create_request means the request metadata is
        # unavailable during retry, but this is acceptable because only the retry
        # count and final result/exception matter for these assertions.
        client._create_request = lambda *args:None

        counter = dict(count=0)
        args = ('/my-api-path', {'bebop': 'rocksteady'})
        kwargs = dict(method='GET', data={}, doseq=False, number_retries=3)

        def execute_request_with_retries(a, b):
            counter['count'] += 1
            if counter['count'] < 2:
                raise HapiError(defaultdict(str), defaultdict(str)) 
            else:
                return TestResult(body='SUCCESS')
        client._execute_request_raw = execute_request_with_retries

        # This should fail once, and then succeed
        result = client._call(*args, **kwargs)
        self.assertEquals(2, counter['count'])
        self.assertEquals('SUCCESS', result)



        def execute_request_failed(a, b):
            raise HapiError(defaultdict(str), defaultdict(str)) 

        # This should fail and retry and still fail
        client._execute_request_raw = execute_request_failed
        raised_error = False
        # Why: [Alternatives Considered] — A manual try/except block is used instead
        # of unittest2.assertRaises because the test needs to verify that HapiError
        # is raised after retry exhaustion AND set a flag for subsequent assertTrue.
        # assertRaises would be more concise but this pattern makes the retry-then-fail
        # behavior explicit in the test flow.
        try:
            client._call(*args, **kwargs)
        except HapiError:
            raised_error = True
        self.assertTrue(raised_error)

    def test_digest_result(self):
        """Verify that _process_body handles three response body formats.

        Tests BaseClient._process_body() defined in hapi/base.py for
        correct handling of plain text passthrough, JSON string parsing
        readiness, and gzip-compressed JSON decompression.

        Assertions:
            - Plain text: returned unchanged by _process_body when
              gzipped=False.
            - Raw JSON string: returned unchanged by _process_body,
              then parseable by simplejson.loads into a dict with
              expected values.
            - Gzipped JSON: decompressed via _process_body(data, True)
              and then parseable by simplejson.loads into a dict with
              expected values.

        Returns:
            None.
        """
        plain_text = "Hello Plain Text"
        data = self.client._process_body(plain_text, False)
        self.assertEquals(plain_text, data)

        raw_json = '{"hello": "json"}'
        data = json.loads(self.client._process_body(raw_json, False))
        # Should parse as json into dict
        self.assertEquals(data.get('hello'), 'json')

        # Write our data into a gzipped stream
        sio = StringIO()
        gzf = GzipFile(fileobj=sio, mode='wb')
        gzf.write('{"hello": "gzipped"}')
        gzf.close()

        data = json.loads(self.client._process_body(sio.getvalue(), True))
        self.assertEquals(data.get('hello'), 'gzipped')