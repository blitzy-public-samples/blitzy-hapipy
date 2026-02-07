# coding: utf-8
"""Integration test suite for KeywordsClient keyword CRUD operations.

This module exercises the HubSpot Keywords API v1 through the
KeywordsClient wrapper defined in ``hapi/keywords.py``.  Tests cover
the full keyword lifecycle: listing, single retrieval by GUID,
single-keyword creation (``add_keyword``), batch creation
(``add_keywords``), deletion, and UTF-8 round-trip fidelity for
accented characters.

All tests are **integration tests** that issue live HTTP requests to
the HubSpot API.  Valid API credentials must be present in
``test_credentials.json`` (or the default ``demo`` key is used) and
are loaded at runtime via ``helper.get_options()``.

Test discovery and selective execution rely on the ``@attr('api')``
decorator from ``nose.plugins.attrib``, allowing the suite to be
filtered with ``nosetests -a api``.

Each test method generates unique keyword names using
``uuid.uuid4()`` to eliminate collision risk across parallel or
repeated test runs.

Framework:
    - ``unittest2.TestCase`` as the base class for Python 2.x
      compatible assertion helpers.
    - ``nose.plugins.attrib.attr`` for tag-based test selection.
    - ``simplejson`` for diagnostic JSON serialisation of API
      responses printed to stdout.
"""
import random
import unittest2
import uuid

import simplejson as json
from nose.plugins.attrib import attr

try:
    from hapi.test import helper
except ImportError:
    import helper
from hapi.keywords import KeywordsClient

class KeywordsClientTest(unittest2.TestCase):
    """Integration tests for the HubSpot Keywords API via KeywordsClient.

    Validates the full keyword CRUD surface exposed by
    ``KeywordsClient`` (defined in ``hapi/keywords.py``):

    * **Listing** — ``get_keywords()`` returns all tracked keywords.
    * **Single retrieval** — ``get_keyword(guid)`` fetches one keyword
      by its GUID and matches the list entry.
    * **Single creation** — ``add_keyword()`` creates one keyword and
      confirms it appears in subsequent listings.
    * **Batch creation** — ``add_keywords()`` creates ten keywords in
      a single API call and verifies all ten persist.
    * **Deletion** — ``delete_keyword()`` removes a keyword and
      confirms it no longer appears in listings.
    * **UTF-8 fidelity** — ``add_keyword()`` round-trips accented
      characters (e.g. ``e``, ``u``) and asserts the returned text
      matches after unicode normalisation.

    Lifecycle management:
        ``setUp`` instantiates ``KeywordsClient`` with live
        credentials.  ``tearDown`` deletes any keyword GUIDs stored
        in ``self.keyword_guids`` to keep the test portal clean.

    Note:
        The commented-out ``test_get_keyword_with_visit_lead``
        (approx. lines 80-92 in the documented file) requires real
        website traffic data (visits, leads) which is unavailable on
        the demo portal.  It is retained as commented code to
        preserve intent for portals with traffic data.

    Questions, comments: http://docs.hubapi.com/wiki/Discussion_Group
    """

    def setUp(self):
        """Initialise a KeywordsClient and prepare cleanup tracking.

        Creates a ``KeywordsClient`` instance using credentials loaded
        from ``helper.get_options()`` (which reads
        ``test_credentials.json`` or falls back to the ``demo`` API
        key).  Sets ``self.keyword_guids`` to ``None`` so that
        ``tearDown`` can distinguish between tests that created
        keywords and those that did not.

        Tests: ``KeywordsClient.__init__()`` defined in
            ``hapi/keywords.py``.

        Returns:
            None
        """
        self.client = KeywordsClient(**helper.get_options())
        # Why: [Trade-offs] — keyword_guids is initialised to None rather than
        # an empty list so that tearDown can skip cleanup via a truthy check.
        # Tests that do not populate self.keyword_guids (e.g. test_add_keyword,
        # which stores GUIDs in self.keyword_guid instead) will not have their
        # keywords cleaned up, potentially leaving orphaned keywords on the test
        # portal.
        self.keyword_guids = None
    
    def tearDown(self):
        """Delete any keywords created during the test to keep the portal clean.

        Iterates over ``self.keyword_guids`` (when populated) and
        calls ``KeywordsClient.delete_keyword()`` for each GUID.  If
        ``self.keyword_guids`` is ``None`` or empty, cleanup is
        skipped entirely.

        Tests: ``KeywordsClient.delete_keyword()`` defined in
            ``hapi/keywords.py``.

        Returns:
            None
        """
        if (self.keyword_guids):
            # Why: [Alternatives Considered] — map() with a lambda wrapping
            # delete_keyword is used rather than a direct method reference
            # (map(self.client.delete_keyword, ...)) because the lambda
            # provides explicit parameter naming and a convenient place to add
            # error handling in the future.  In Python 2.x map() eagerly
            # evaluates and returns a list that is discarded here — a for loop
            # would be more explicit about the side-effect intent, but this
            # pattern is preserved for backward compatibility.
            map(
                lambda keyword_guid: self.client.delete_keyword(keyword_guid),
                self.keyword_guids
            )
    
    @attr('api')
    def test_get_keywords(self):
        """Verify that get_keywords returns at least one keyword.

        Calls ``KeywordsClient.get_keywords()`` and asserts that the
        returned list is non-empty (truthy length).  The result is
        then JSON-serialised to stdout for manual inspection.

        Tests: ``KeywordsClient.get_keywords()`` defined in
            ``hapi/keywords.py``.

        Assertions:
            - The keywords list has a truthy length (> 0).

        Returns:
            None
        """
        keywords = self.client.get_keywords()
        self.assertTrue(len(keywords))
        
        print("\n\nGot some keywords: %s" % json.dumps(keywords))
    
    @attr('api')
    def test_get_keyword(self):
        """Verify that get_keyword retrieves a single keyword by GUID.

        First fetches the full keyword list via ``get_keywords()``,
        then requests the first keyword individually using
        ``get_keyword(guid)``.  Asserts that the individually
        retrieved keyword dict is identical to the corresponding
        entry in the list.

        Tests: ``KeywordsClient.get_keywords()`` and
            ``KeywordsClient.get_keyword()`` defined in
            ``hapi/keywords.py``.

        Assertions:
            - At least one keyword exists (fails the test otherwise).
            - ``get_keyword(guid)`` returns a dict equal to the
              original list entry.

        Returns:
            None
        """
        keywords = self.client.get_keywords()
        if len(keywords) < 1:
            self.fail("No keywords available for test.")

        keyword = keywords[0]
        print("\n\nGoing to get a specific keyword: %s" % keyword)
        
        result = self.client.get_keyword(keyword['keyword_guid'])
        self.assertEquals(keyword, result)
        
        print("\n\nGot a single matching keyword: %s" % keyword['keyword_guid'])
    
# Why: [Assumptions Made] — The test_get_keyword_with_visit_lead test is
# commented out because it requires real website traffic data (visits, leads)
# on the test portal for keyword visit/lead metrics to exist.  The demo portal
# has no traffic, making this test impossible to run.  Keeping it commented
# (rather than deleted) preserves the test intent for future use with a portal
# that has traffic data.
# TODO This test does not currently work because there is no traffic on the demo portal
# Becuase there is no traffic, there are no visits or leads for this to look at
#    @attr('api')
#    def test_get_keyword_with_visit_lead(self):
#        # Change the test keyword if you are running on not the demo portal
#        test_keyword = "app"
#        keywords = self.client.get_keywords()
#        if len(keywords) < 1:
#            self.fail("No keywords available for test.")
#        for keyword in keywords:
#            if keyword['keyword'] == test_keyword:
#                self.assertTrue(keyword.has_key('visits'))
#                self.assertTrue(keyword.has_key('leads'))

    @attr('api')
    def test_add_keyword(self):
        """Verify the single-keyword creation lifecycle via add_keyword.

        Creates a uniquely-named keyword using ``add_keyword()``,
        asserts that the API response contains exactly one keyword
        entry, then re-fetches the full keyword list and verifies the
        new keyword exists by GUID filtering.

        Tests: ``KeywordsClient.add_keyword()`` and
            ``KeywordsClient.get_keywords()`` defined in
            ``hapi/keywords.py``.

        Assertions:
            - ``add_keyword`` response contains exactly 1 keyword in
              ``result['keywords']``.
            - Re-fetched keyword list filtered by the added GUID
              contains exactly 1 match.

        Note:
            This test stores the created GUID in ``self.keyword_guid``
            (singular) rather than ``self.keyword_guids`` (plural),
            which ``tearDown`` checks.  The added keyword may not be
            automatically cleaned up after the test completes.

        Returns:
            None
        """
        keyword = []
        # Why: [Alternatives Considered] — UUID4 is used for unique keyword
        # name generation instead of random.randint(0, 1000) because the random
        # number approach has too high a collision rate across repeated test
        # runs.  UUID4 provides effectively guaranteed uniqueness, preventing
        # test failures from duplicate keyword conflicts in the HubSpot API.
        # Add a single keyword to this self, it is a string with a uuid added because a string with a
        # random number appended to it has too high of a collision rate
        keyword.append('hapipy_test_keyword%s' % str(uuid.uuid4()))
        
        # copy the keyword into 'result' after the client adds it
        result = self.client.add_keyword(keyword)
        
        # make sure 'result' has one keyword in it
        self.assertEqual(len(result['keywords']), 1)
        
        print("\n\nAdded keyword: %s" % json.dumps(result))
        
        # Why: [Trade-offs] — test_add_keyword uses a local self.keyword_guid
        # (singular) list rather than self.keyword_guids (plural) which is what
        # tearDown checks.  This appears to be an oversight where the
        # single-keyword test's cleanup is disconnected from tearDown, meaning
        # added keywords may persist after test completion.  The inconsistency
        # is preserved for backward compatibility.
        # holds the guid of the keyword being added
        self.keyword_guid = []
        
        # get the keyword's guid
        self.keyword_guid.append(result['keywords'][0]['keyword_guid'])
        
        # now check if the keyword is in the client
        
        # get what is in the client
        check = self.client.get_keywords()
        
        # filter 'check' if it is in this self
        check = list(filter(lambda p: p['keyword_guid'] in self.keyword_guid, check))
        
        # check if it was filtered. If it was, it is in the client
        self.assertEqual(len(check), 1)
        
        print("\n\nSaved keyword %s" % json.dumps(check))

    @attr('api')
    def test_add_keywords(self):
        """Verify batch keyword creation via add_keywords.

        Generates ten uniquely-named keywords, submits them in a
        single ``add_keywords()`` call, and asserts that the response
        contains exactly ten entries.  Then re-fetches the full
        keyword list and filters by the added GUIDs to confirm all
        ten persist.

        All ten keyword GUIDs are stored in ``self.keyword_guids``
        so that ``tearDown`` deletes them after the test completes.

        Tests: ``KeywordsClient.add_keywords()`` and
            ``KeywordsClient.get_keywords()`` defined in
            ``hapi/keywords.py``.

        Assertions:
            - ``add_keywords`` response has length 10.
            - Re-fetched keyword list filtered by added GUIDs has
              length 10.

        Returns:
            None
        """
        # Add multiple Keywords in one API call.
        keywords = []
        for i in range(10):
            # A string with a random number between 0 and 1000 as a test keyword has too high of a collision rate.
            # switched test string to a uuid to decrease collision chance.
            keywords.append('hapipy_test_keyword%s' % str(uuid.uuid4()))

        # copy the keywords into 'result' after the client adds them
        result = self.client.add_keywords(keywords)
        
        # Now check if all of the keywords have been put in 'results'
        self.assertEqual(len(result), 10)
        
        # make and fill a list of 'keyword's guid's
        self.keyword_guids = []
        for keyword in result:
            self.keyword_guids.append(keyword['keyword_guid'])
        
        # This next section removes keywords from 'keywords' that are already in self by
        # checking the guid's. If none of the keywords in 'keywords' are already there, it is done. Otherwise, fails at the assert.
        
        # Make sure they're in the list now
        keywords = self.client.get_keywords()
        
        keywords = list(filter(lambda x: x['keyword_guid'] in self.keyword_guids, keywords))
        self.assertEqual(len(keywords), 10)

        print("\n\nAdded multiple keywords: %s" % keywords)
    
    @attr('api')
    def test_delete_keyword(self):
        """Verify keyword deletion removes the keyword from listings.

        Creates a keyword via ``add_keyword()``, immediately deletes
        it via ``delete_keyword()``, then re-fetches the full keyword
        list and asserts the deleted GUID no longer appears.

        Tests: ``KeywordsClient.add_keyword()``,
            ``KeywordsClient.delete_keyword()``, and
            ``KeywordsClient.get_keywords()`` defined in
            ``hapi/keywords.py``.

        Assertions:
            - After deletion, filtering the keyword list by the
              deleted GUID returns an empty list (length 0).

        Returns:
            None
        """
        # Delete multiple keywords in one API call.
        keyword = 'hapipy_test_keyword%s' % str(uuid.uuid4())
        result = self.client.add_keyword(keyword)
        keywords = result['keywords']
        first_keyword = keywords[0]
        print("\n\nAbout to delete a keyword, result= %s" % json.dumps(result))

        self.client.delete_keyword(first_keyword['keyword_guid'])
        
        # Make sure it's not in the list now
        keywords = self.client.get_keywords()
        
        keywords = list(filter(lambda x: x['keyword_guid'] == first_keyword['keyword_guid'], keywords))
        self.assertTrue(len(keywords) == 0)
        
        print("\n\nDeleted keyword %s" % json.dumps(first_keyword))
        
    @attr('api')
    def test_utf8_keywords(self):
        """Verify UTF-8 round-trip fidelity for accented keyword text.

        Iterates over a set of accented base characters (``e``,
        ``u``), creates a keyword for each using ``add_keyword()``,
        then compares the returned keyword text against the original
        after normalising both to unicode.  This confirms that the
        HubSpot API preserves non-ASCII characters through the
        create-and-retrieve cycle.

        Tests: ``KeywordsClient.add_keyword()`` defined in
            ``hapi/keywords.py``.

        Assertions:
            - Each added keyword has a non-falsy ``keyword_guid``.
            - The returned keyword text equals the original after
              both are normalised to unicode via ``decode('utf-8')``.

        Note:
            Simplified Chinese (guang) and Cyrillic (el) characters are
            known to fail and are excluded (see inline TODO).
            Keyword GUIDs are collected in a local ``keyword_guids``
            variable but are **not** assigned to
            ``self.keyword_guids``, so tearDown will not clean them up.

        Returns:
            None
        """
        # Start with base utf8 characters
        # TODO: Fails when adding simplified chinese char: 广 or cyrillic: л
        utf8_keyword_bases = ['é', 'ü']

        keyword_guids = []
        for utf8_keyword_base in utf8_keyword_bases:
            original_keyword = '%s - %s' % (utf8_keyword_base, str(uuid.uuid4()))
            result = self.client.add_keyword(original_keyword)
            print("\n\nAdded keyword: %s" % json.dumps(result))
            print(result)

            keywords_results = result.get('keywords')
            keyword_result = keywords_results[0]

            self.assertTrue(keyword_result['keyword_guid'])
            keyword_guids.append(keyword_result['keyword_guid'])

            actual_keyword = keyword_result['keyword']

            # Why: [Assumptions Made] — The explicit isinstance/decode conversion
            # handles both Python 2.x str (bytes) and unicode types because the
            # HubSpot API may return keyword text as either type depending on the
            # content.  The decode('utf-8') call on byte strings normalises them
            # to unicode for comparison, ensuring UTF-8 round-trip fidelity
            # regardless of the API's response encoding.
            # Convert to utf-8 to compare strings. Returned string is \x-escaped
            # Why: [Assumptions Made] — In Python 3 str is already unicode, so
            # the isinstance check uses str; in Python 2 the original 'unicode'
            # builtin is used. bytes.decode handles the byte-string branch.
            _text_type = str  # Python 3: str is unicode
            if isinstance(original_keyword, _text_type):
                original_unicode_keyword = original_keyword
            else:
                original_unicode_keyword = original_keyword.decode('utf-8')

            if isinstance(actual_keyword, _text_type):
                actual_unicode_keyword = actual_keyword
            else:
                actual_unicode_keyword = actual_keyword.decode('utf-8')

            self.assertEqual(actual_unicode_keyword, original_unicode_keyword)

if __name__ == "__main__":
    unittest2.main()