"""Test module for LeadsClient parameter conversion utilities.

Provides unit tests for the LeadsClient.camelcase_search_options() method,
which transforms Python-style snake_case search parameters into the
camelCase format expected by the HubSpot Leads API. This is a unit test
module that constructs a LeadsClient with test credentials but only tests
the local camelcase_search_options method — no live API calls are made by
the test assertions.

Tests:
    LeadsClient.camelcase_search_options() defined in hapi/leads.py.

Test Framework:
    unittest2.TestCase — used for backward-compatible assertion methods
    and test discovery via the nose test runner.

Note:
    Unlike other test modules in this package, test_leads.py imports the
    logger module at module level to configure the 'hapi' logger for any
    diagnostic output during test execution.
"""
import unittest2
try:
    from hapi.test import helper
except ImportError:
    import helper
from hapi.leads import LeadsClient
# Why: [Assumptions Made] — The logger module is imported at module level to trigger
# configure_log() side effect, which sets up the 'hapi' logger with file and console
# handlers. This ensures any internal logging from LeadsClient construction or method
# calls is captured in test_run.log. The import occurs before test execution and
# configures logging for the entire test session.
try:
    from hapi.test import logger
except ImportError:
    import logger
import time

class LeadsClientTest(unittest2.TestCase):
    """Test class verifying LeadsClient parameter conversion utilities.

    Exercises the camelcase_search_options method that transforms Python-style
    snake_case search parameters to the HubSpot API-expected camelCase format.
    Tests cover sort value conversion, passthrough for unmapped keys, key and
    value conversion for mapped option names, and boolean-to-string coercion.

    Test Approach:
        Unit tests using a real LeadsClient instance constructed with demo
        credentials from helper.get_options(), but testing only the local
        camelcase_search_options transformation logic — no HTTP calls are made.

    Test Framework:
        unittest2.TestCase

    Source Under Test:
        LeadsClient defined in hapi/leads.py
    """

    def setUp(self):
        """Initialize a LeadsClient instance for parameter conversion testing.

        Construct a LeadsClient with credentials obtained from
        helper.get_options() (defaults to api_key='demo' unless overridden
        by test_credentials.json). The client instance is stored as
        self.client for use across all test methods in this class.

        Tests:
            LeadsClient constructor defined in hapi/leads.py.

        Returns:
            None
        """
        self.client = LeadsClient(**helper.get_options())
    
    def tearDown(self):
        """Perform no-op cleanup after each test method.

        Placeholder teardown method for test resource cleanup. Currently
        no resources require explicit teardown since the LeadsClient
        instance does not hold open connections or temporary state that
        persists between tests.

        Returns:
            None
        """
        pass

    # Why: [Assumptions Made] — The test covers the four main conversion paths in
    # camelcase_search_options: sort value conversion (via SORT_OPTIONS_DICT),
    # passthrough for non-mapped keys ('search'), key+value conversion for mapped
    # option names ('time_pivot' -> 'timePivot'), and boolean-to-lowercase-string
    # coercion (True -> 'true'). This single test method exercises the most critical
    # conversion paths. Additional test methods for lead CRUD operations (get_leads,
    # search_leads, etc.) are not present in this module — those operations would
    # require live API calls and a test portal with existing lead data.
    def test_camelcased_params(self):
        """Verify camelcase_search_options converts snake_case params to camelCase.

        Construct an input dict with four representative parameter types and
        verify that camelcase_search_options produces the exact expected
        camelCase output dict. The four conversion paths tested are:

        - 'sort' with dotted snake_case value ('fce.convert_date') — converts
          the value portion to camelCase ('fce.convertDate') via SORT_OPTIONS_DICT.
        - 'search' with plain string value — passes through unchanged as an
          unmapped key.
        - 'time_pivot' with snake_case key AND value — converts key to camelCase
          ('timePivot') and value to camelCase ('lastModifiedAt') via
          TIME_PIVOT_OPTIONS_DICT.
        - 'is_not_imported' with boolean True — converts key to camelCase
          ('isNotImported') and coerces boolean value to lowercase string ('true').

        Tests:
            LeadsClient.camelcase_search_options() defined in hapi/leads.py.

        Assertions:
            Output dict exactly matches the expected camelCase-formatted dict
            with all key and value conversions applied.

        Returns:
            None
        """
        # Why: [Trade-offs] — The test uses hardcoded input/output dictionaries rather
        # than parameterized test cases because the camelcase_search_options method's
        # conversion rules are deterministic and the four test cases cover all conversion
        # branches. Parameterized tests would add complexity without improving coverage.
        # The assertEquals against the full expected dict verifies all conversions in a
        # single assertion, trading individual failure diagnostics for test brevity.
        in_options = { 
                'sort': 'fce.convert_date', 
                'search': 'BlahBlah', 
                'time_pivot': 'last_modified_at', 
                'is_not_imported': True }
        out_options = { 
                'sort': 'fce.convertDate', 
                'search': 'BlahBlah', 
                'timePivot': 'lastModifiedAt', 
                'isNotImported': 'true' }
        self.assertEquals(out_options, self.client.camelcase_search_options(in_options))
 

if __name__ == "__main__":
    unittest2.main()
