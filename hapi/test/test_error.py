"""Test module for HapiError and EmptyResult exception hierarchy.

Validates the unicode safety and graceful degradation behavior of the
hapi.error exception classes. These are standalone unit tests using
nose.tools assertions (ok_) rather than unittest2.TestCase — they are
module-level functions discovered by nose's function-based test discovery.

Tests focus on two critical behaviors:
    1. Unicode safety of error diagnostic output, ensuring that non-ASCII
       content in response bodies, request URLs, and request data does not
       cause encoding exceptions during error formatting.
    2. Graceful handling of missing HTTP context, verifying that HapiError
       can be constructed with None result and None request without raising
       AttributeError or TypeError.

A local MockResult class serves as a Null Object stand-in to simulate
HTTP responses with controlled attribute values, decoupled from the
error module's own EmptyResult implementation.

Reference:
    Tests HapiError and EmptyResult defined in hapi/error.py.
"""

from hapi.error import HapiError, EmptyResult

from nose.tools import ok_

# Why: [Assumptions Made] — In Python 3 there is no 'unicode' builtin; str is
# already unicode.  Aliasing unicode = str allows the test assertions
# (unicode(exc)) to work identically under both Python 2 and Python 3 without
# changing the test logic.
try:
    unicode
except NameError:
    unicode = str

# Why: [Alternatives Considered] — A local MockResult is used instead of
# importing EmptyResult from hapi.error because the test needs independent
# control over attribute values (e.g., setting body and reason to
# unicode-containing strings). Using EmptyResult directly would couple the
# test to the error module's default values and make it unclear whether
# the test is validating HapiError's formatting or EmptyResult's defaults.
# The interface mirrors EmptyResult's attributes (status, body, msg, reason)
# to ensure HapiError can consume it identically.
class MockResult(object):
    """Null Object implementation mirroring httplib.HTTPResponse interface.

    Provides default attribute values for constructing HapiError instances
    in tests without requiring real HTTP responses. This is functionally
    identical to EmptyResult in hapi/error.py but defined locally to
    decouple test construction from the error module's internal
    implementation.

    Tests use MockResult for controlled attribute mutation (e.g., injecting
    unicode content into body and reason) while EmptyResult is tested
    implicitly through HapiError's constructor fallback path when
    result=None is passed.

    Attributes:
        status (int): HTTP status code, default 0 simulating no HTTP status.
        body (str): Response body content, default empty string simulating
            no response body.
        msg (str): HTTP message, default empty string simulating no HTTP
            message.
        reason (str): HTTP reason phrase, default empty string simulating
            no HTTP reason phrase.
    """
    def __init__(self):
        """Initialize all HTTP response attributes to safe default values.

        Sets status, body, msg, and reason to neutral defaults that will
        not cause errors when consumed by HapiError's diagnostic
        formatting methods (__unicode__, __str__).

        Returns:
            None
        """
        self.status = 0
        self.body = ''
        self.msg = ''
        self.reason = ''


def test_unicode_error():
    """Verify HapiError handles unicode content in all diagnostic fields.

    Constructs a MockResult with unicode characters in body and reason,
    and a request dict with unicode in url, data, and headers/cookies,
    then asserts that HapiError's formatting methods produce output
    without raising encoding exceptions.

    The test specifically exercises two encoding paths:
        1. unicode(exc) — calls HapiError.__unicode__(), which must
           safely format all fields including non-ASCII characters
           (Chinese: U+8131, bullet: U+2022).
        2. str(exc) — calls HapiError.__str__(), which encodes the
           unicode output to ASCII with 'replace' error handling,
           substituting '?' for non-ASCII characters.

    Tests:
        HapiError.__init__(), HapiError.__unicode__(), and
        HapiError.__str__() defined in hapi/error.py.

    Returns:
        None
    """

    result = MockResult()
    # Why: [Assumptions Made] — The body string contains actual unicode
    # characters (Chinese U+8131 and bullet U+2022) to verify that
    # HapiError's diagnostic formatting correctly handles non-ASCII
    # content in response bodies. This simulates real-world scenarios
    # where API error responses may contain internationalized text.
    result.body = 'A HapiException with unicode \u8131 \xe2\x80\xa2\t'
    result.reason = 'Why must everything have a reason?'
    request = {}
    for key in ('method', 'host', 'url', 'timeout', 'data', 'headers'):
        request[key] = ''
    request['url'] = u'http://adomain/with-unicode-\u8131'
    # Why: [Trade-offs] — The missing 'u' modifier on the data string
    # below is intentional. This tests HapiError's robustness with byte
    # strings containing unicode byte sequences (e.g., \xe2\x80\xa2 is
    # the UTF-8 encoding of the bullet character U+2022). In Python 2.x,
    # strings without the 'u' prefix are byte strings, and HapiError's
    # _dict_vals_to_unicode must handle this conversion path without
    # raising UnicodeDecodeError.
    # Note the following line is missing the 'u' modifier on the string,
    # this is intentional to simulate poorly formatted input that should
    # still be handled without an exception
    request['data'] = "A HapiException with unicode \u8131 \xe2\x80\xa2"
    request['headers'] = {'Cookie': "with unicode \u8131 \xe2\x80\xa2"}

    exc = HapiError(result, request)
    ok_(request['url'] in unicode(exc))
    ok_(result.reason in str(exc))

# Why: [Alternatives Considered] — Testing with both result=None and
# request=None exercises the most defensive path through HapiError: the
# constructor must replace None with EmptyResult for result, and
# __unicode__ must handle None request (replaced with empty dict) without
# AttributeError. A third parameter ('a silly error') is passed as err=
# to ensure the error message propagates even when all HTTP context is
# missing. This validates the EmptyResult Null Object fallback in
# HapiError.__init__ where result=None triggers EmptyResult() creation.
def test_error_with_no_result_or_request():
    """Verify HapiError handles None result and None request gracefully.

    Constructs a HapiError with result=None and request=None, passing
    only an error message string. This exercises the EmptyResult Null
    Object fallback path in HapiError.__init__ where result=None is
    replaced with EmptyResult(), and request=None is replaced with an
    empty dict.

    Tests:
        HapiError.__init__() and HapiError.__unicode__() with None
        result (triggers EmptyResult fallback) and None request defined
        in hapi/error.py.

    Returns:
        None
    """
    exc = HapiError(None, None, 'a silly error')
    ok_('a silly error' in unicode(exc))
