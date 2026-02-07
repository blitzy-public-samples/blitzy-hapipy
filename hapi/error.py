"""Error hierarchy module for the hapipy HubSpot API client library.

Defines all exception classes raised during HubSpot API interactions,
providing rich diagnostic information for debugging failed requests.

Class Hierarchy::

    ValueError
    └── HapiError (base API error with full request/response diagnostics)
        ├── HapiBadRequest (HTTP 400-499, 501 — client errors)
        ├── HapiNotFound (HTTP 404, 410 — missing resources)
        ├── HapiTimeout (connection/SSL/read timeouts)
        ├── HapiUnauthorized (HTTP 401 — triggers token refresh)
        └── HapiServerError (HTTP 500+ — retryable server errors)

Additionally provides ``EmptyResult``, a Null Object sentinel that
supplies safe default values for HTTP response attributes when no
actual response is available (e.g., connection timeouts that occur
before any server response is received).

Error Mapping Flowchart (Mermaid)::

    flowchart TD
        A[HTTP Response] --> B{Status Code}
        B -->|401| C[HapiUnauthorized]
        B -->|404,410| D[HapiNotFound]
        B -->|400-499,501| E[HapiBadRequest]
        B -->|500+| F[HapiServerError]
        B -->|timeout/SSL| G[HapiTimeout]
        B -->|200 empty| H[EmptyResult Sentinel]
        B -->|200 with body| I[JSON Parse Result]

All errors are raised by ``BaseClient._execute_request_raw`` in
``hapi/base.py``, which inspects the HTTP status code and maps it
to the appropriate exception subclass.
"""


# Why: [Alternatives Considered] — The Null Object pattern (EmptyResult) is used
# instead of None checks throughout the error formatting code because HapiError's
# __unicode__ method needs to access .status, .reason, .body, and .msg attributes.
# Without EmptyResult, every attribute access would need a None guard. EmptyResult
# evaluates as falsy via __nonzero__ so existing `if result:` checks still work
# correctly.
class EmptyResult(object):
    """Null Object pattern implementation for absent HTTP responses.

    Provides safe default values for all HTTP response attributes that
    ``HapiError``'s diagnostic formatting code accesses, preventing
    NoneType attribute access errors when no actual HTTP response
    exists (e.g., connection timeouts that occur before any server
    response is received).

    Attributes:
        status (int): Default status code, always 0.
        body (str): Default response body, always empty string.
        msg (str): Default status message, always empty string.
        reason (str): Default reason phrase, always empty string.

    Note:
        Used by ``HapiError.__init__`` when the result parameter is
        None. Evaluates as falsy via ``__nonzero__`` so existing
        ``if result:`` boolean checks continue to work correctly.
    """

    def __init__(self):
        """Initialize all response attributes to safe default values.

        Sets status to 0 and body, msg, reason to empty strings,
        ensuring that ``HapiError.__unicode__`` can safely access
        these attributes without None guards.

        Returns:
            None
        """
        self.status = 0
        self.body = ''
        self.msg = ''
        self.reason = ''

    def __nonzero__(self):
        """Make EmptyResult evaluate as falsy in boolean contexts.

        Allows ``if not result:`` checks to correctly identify
        EmptyResult instances as representing the absence of an
        actual HTTP response, consistent with the convention that
        None results are falsy.

        Returns:
            bool: Always returns False.
        """
        return False


# Why: [Assumptions Made] — HapiError inherits from ValueError rather than
# Exception or IOError because the original library design treated API errors as
# value-related errors. This allows callers who catch ValueError to also catch
# HapiError, though it is an unconventional choice for HTTP errors.
class HapiError(ValueError):
    """Base exception class for all HubSpot API errors.

    Provides rich diagnostic information including the original HTTP
    request metadata, response attributes, and any triggering errors.
    All HubSpot API wrapper methods route through
    ``BaseClient._call_raw`` in ``hapi/base.py``, which raises
    the appropriate HapiError subclass based on HTTP status codes.

    The diagnostic output format (defined by ``as_str_template``)
    includes these sections::

        ---- request ----
        {method} {host}{url}, [timeout={timeout}]
        ---- body ----
        {body}
        ---- headers ----
        {headers}
        ---- result ----
        {result_status}
        ---- body -----
        {result_body}
        ---- headers -----
        {result_headers}
        ---- reason ----
        {result_reason}
        ---- trigger error ----
        {error}

    Attributes:
        result (httplib.HTTPResponse or EmptyResult): The HTTP response
            object, or EmptyResult if no response was received.
        request (dict): Request metadata with keys 'method', 'host',
            'url', 'data', 'headers', 'timeout'.
        err (str or Exception or None): The triggering error or
            traceback string.
        as_str_template (unicode): Format string template for
            diagnostic output.
    """

    as_str_template = u'''
---- request ----
{method} {host}{url}, [timeout={timeout}]

---- body ----
{body}

---- headers ----
{headers}

---- result ----
{result_status}

---- body -----
{result_body}

---- headers -----
{result_headers}

---- reason ----
{result_reason}

---- trigger error ----
{error}
        '''


    def __init__(self, result, request, err=None):
        """Construct the error with optional HTTP response, request metadata, and triggering error.

        Initialize the exception by extracting the reason phrase from
        the HTTP response (or defaulting to 'Unknown Reason' if no
        response is available), and store the full request and response
        objects for diagnostic formatting.

        Args:
            result (httplib.HTTPResponse or None): The HTTP response
                object from the failed request. If None, replaced with
                an EmptyResult instance to prevent NoneType attribute
                access errors during diagnostic formatting.
            request (dict or None): Request metadata dictionary with
                keys 'method', 'host', 'url', 'data', 'headers',
                'timeout'. If None, replaced with an empty dict.
            err (str or Exception or None): The triggering error or
                traceback string from the underlying connection failure.
                Defaults to None when the error is derived purely from
                the HTTP status code.

        Returns:
            None
        """
        # Why: [Trade-offs] — The short-circuit expression `result and result.reason
        # or "Unknown Reason"` handles both None results and results without a reason
        # attribute in a single expression, but relies on Python's truthy evaluation
        # which could mask a result with an empty-string reason.
        super(HapiError,self).__init__(result and result.reason or "Unknown Reason")
        if result == None:
            self.result = EmptyResult()
        else:
            self.result = result
        if request == None:
            request = {}
        self.request = request
        self.err = err

    def __str__(self):
        """Return ASCII-safe string representation of the error diagnostic.

        Encode the full unicode diagnostic output to ASCII with
        non-ASCII characters replaced by '?' placeholders, ensuring
        the error message is always printable in Python 2.x contexts
        where print statements and string concatenation may fail on
        unicode characters.

        Returns:
            str: ASCII-encoded diagnostic string with non-ASCII
                characters replaced by '?'.
        """
        # Why: [Assumptions Made] — The __str__ method encodes unicode to ASCII with
        # 'replace' error handling because Python 2.x print and string concatenation
        # operations may fail on unicode characters. The 'replace' strategy substitutes
        # non-ASCII chars with '?' to ensure the error message is always printable.
        return self.__unicode__().encode('ascii', 'replace')


    def __unicode__(self):
        """Build comprehensive diagnostic unicode string from request and result metadata.

        Extract request metadata (method, host, url, data, headers,
        timeout, body) from the stored request dict and response
        attributes (status, reason, msg, body, headers) from the
        stored result object, then format them into the
        ``as_str_template`` diagnostic template.

        All extracted values are converted to unicode strings via
        ``_dict_vals_to_unicode`` before template substitution to
        prevent format string encoding errors.

        Returns:
            unicode: Formatted diagnostic string containing the full
                request and response details for debugging.
        """
        params = {}
        request_keys = ('method', 'host', 'url', 'data', 'headers', 'timeout', 'body')
        result_attrs = ('status', 'reason', 'msg', 'body', 'headers')
        params['error'] = self.err
        for key in request_keys:
            params[key] = self.request.get(key)
        for attr in result_attrs:
            params['result_%s' % attr] = getattr(self.result, attr, '')

        params = self._dict_vals_to_unicode(params)
        return self.as_str_template.format(**params)

    def _dict_vals_to_unicode(self, data):
        """Convert all dictionary values to unicode strings for safe template formatting.

        Handle the three value types encountered in request/response
        metadata using type-specific conversion paths:

        - Non-string values (int, None, list): converted via ``unicode()``.
        - Byte strings (str in Python 2): decoded as UTF-8 with
          malformed bytes silently ignored.
        - Unicode strings: passed through unchanged.

        Args:
            data (dict): Dictionary with string keys and mixed-type
                values from request metadata and response attributes.

        Returns:
            dict: New dictionary with all values converted to unicode
                strings, safe for use with ``unicode.format()``.
        """
        # Why: [Trade-offs] — Three-branch type checking (non-string → unicode(),
        # bytes → unicode(val, 'utf8', 'ignore'), unicode → passthrough) is used because
        # Python 2.x has distinct str (bytes) and unicode types. The 'ignore' error
        # handler on UTF-8 decode silently drops malformed bytes rather than raising
        # UnicodeDecodeError, prioritizing diagnostic message availability over data
        # fidelity.
        unicode_data = {}
        for key, val in data.items():
            if not isinstance(val, basestring):
                unicode_data[key] = unicode(val)
            elif not isinstance(val, unicode):
                unicode_data[key] = unicode(val, 'utf8', 'ignore')
            else:
                unicode_data[key] = val
        return unicode_data



# Why: [Alternatives Considered] — HTTP-status-specific error subclasses (HapiBadRequest,
# HapiNotFound, etc.) are used instead of a single HapiError with a status_code attribute
# because isinstance-based error filtering in except clauses is more Pythonic than checking
# status codes in a catch-all handler. This also enables BaseClient._call_raw to have
# specific retry behavior per error type (e.g., only retrying on HapiServerError).
class HapiBadRequest(HapiError):
    """Error for HTTP 400-499 range (client errors) and 501 Not Implemented.

    Raised by ``BaseClient._execute_request_raw`` in ``hapi/base.py``
    for invalid requests, permission issues, rate limiting, and
    unsupported operations. Covers all client-error status codes
    except 401 (handled by ``HapiUnauthorized``) and 404/410
    (handled by ``HapiNotFound``).
    """

class HapiNotFound(HapiError):
    """Error for HTTP 404 Not Found and 410 Gone responses.

    Raised when the requested HubSpot resource does not exist or
    has been permanently removed. Separated from ``HapiBadRequest``
    to allow callers to distinguish missing-resource errors from
    other client errors without inspecting status codes.
    """

class HapiTimeout(HapiError):
    """Error for connection timeouts, SSL errors, and read timeouts.

    Raised when a network-level failure prevents receiving any HTTP
    response from the HubSpot API. The ``err`` attribute contains
    the traceback string from the underlying connection failure
    (e.g., socket.timeout, ssl.SSLError). The ``result`` attribute
    will be an ``EmptyResult`` instance since no server response was
    received.
    """

class HapiUnauthorized(HapiError):
    """Error for HTTP 401 Unauthorized responses.

    Raised when the provided API key or OAuth access token is invalid,
    expired, or lacks sufficient permissions. In
    ``BaseClient._call_raw``, catching this error triggers the OAuth
    token refresh logic when ``refresh_token`` and ``client_id`` are
    configured on the client.
    """

class HapiServerError(HapiError):
    """Error for HTTP 500+ range (server errors).

    Raised for HubSpot server-side failures including internal server
    errors and service unavailability. These errors are retryable in
    ``BaseClient._call_raw``'s retry loop, which applies exponential
    backoff before re-attempting the request.
    """
