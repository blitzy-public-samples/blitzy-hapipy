"""Core HTTP engine module providing BaseClient for the hapipy library.

This module defines ``BaseClient``, the abstract base class from which all
HubSpot API domain clients inherit (BlogClient, BroadcastClient,
FormSubmissionClient, KeywordsClient, LeadsClient, ProspectsClient).
BaseClient encapsulates the complete HTTP request lifecycle, from URL
construction through response parsing and error handling.

Request Lifecycle::

    Domain client method (e.g., get_blogs())
        -> _call(subpath, params) or _call_raw(subpath, params)
            -> _prepare_request_auth(subpath, params, data, opts)
            -> _prepare_request(subpath, params, data, opts)
                -> _get_path(subpath)  [overridden by each domain client]
            -> _create_request(conn, method, url, headers, data)
            -> _execute_request_raw(conn, request)
                -> _process_body(data, gzipped)
            -> _digest_result(data)  [JSON parsing]

Key Responsibilities:
    - Authentication injection: API key as ``hapikey`` query parameter,
      or OAuth ``access_token`` as query parameter.
    - Retry with exponential backoff: Configurable retries (max 6) with
      backoff sequence 0, 1, 3, 7, 15, 31 seconds.
    - Gzip decompression: Manual zlib decompression of API responses
      via ``_gunzip_body()`` since httplib does not auto-decompress.
    - Response parsing: JSON deserialization with graceful fallback to
      raw string for non-JSON responses.
    - Error mapping: HTTP status codes mapped to the ``HapiError``
      hierarchy (``HapiBadRequest``, ``HapiNotFound``, ``HapiTimeout``,
      ``HapiUnauthorized``, ``HapiServerError``).

All domain clients inherit from BaseClient and override ``_get_path()``
to provide their API-versioned endpoint path prefix.

Sequence Diagram (Mermaid)::

    Caller -> DomainClient: client.get_blogs()
    DomainClient -> BaseClient: _call(subpath, params)
    BaseClient -> BaseClient: _prepare_request_auth()
    BaseClient -> BaseClient: _prepare_request()
    BaseClient -> HubSpotAPI: HTTP GET with auth
    HubSpotAPI --> BaseClient: Response (possibly gzipped)
    BaseClient -> BaseClient: Decompress if gzip
    BaseClient --> DomainClient: Parsed JSON result
    DomainClient --> Caller: Python dict/list
"""
import urllib
import httplib
import simplejson as json
import utils
import logging
import sys
import time
import traceback
import gzip
import StringIO

from error import HapiError, HapiBadRequest, HapiNotFound, HapiTimeout, HapiServerError, HapiUnauthorized


_PYTHON25 = sys.version_info < (2, 6)

class BaseClient(object):
    """Abstract base client providing the shared HTTP engine for all HubSpot API interactions.

    BaseClient is the foundation of the hapipy library. Every domain-specific
    client (BlogClient, BroadcastClient, FormSubmissionClient, KeywordsClient,
    LeadsClient, ProspectsClient) inherits from BaseClient and gains its HTTP
    request execution, authentication, retry, and response-parsing capabilities.

    Endpoint Access Lifecycle:
        1. Domain client calls ``_call(subpath)`` or ``_call_raw(subpath)``.
        2. ``_call_raw()`` orchestrates the full request:
           a. ``_prepare_request_auth()`` injects API key or OAuth token.
           b. ``_prepare_request()`` assembles URL, headers, and serialized body.
           c. ``_create_request()`` dispatches the HTTP request via httplib.
           d. ``_execute_request_raw()`` reads the response and maps errors.
        3. ``_call()`` additionally passes the response through
           ``_digest_result()`` for JSON parsing.

    Attributes:
        sleep_multiplier (int): Multiplier applied to exponential backoff
            sleep durations. Class-level attribute to allow test overrides.
        api_key (str or None): HubSpot API key for authentication.
        access_token (str or None): OAuth access token for authentication.
        refresh_token (str or None): OAuth refresh token for token renewal.
        client_id (str or None): OAuth client ID for token renewal.
        log (logging.Logger): Logger instance for request diagnostics.
        options (dict): Configuration dict containing:
            - api_base (str): API hostname, default ``'api.hubapi.com'``.
            - protocol (str): ``'http'`` or ``'https'``, parsed from api_base.
            - connection_type (class): ``httplib.HTTPConnection`` or
              ``httplib.HTTPSConnection``, determined by protocol.
            - timeout (int): Request timeout in seconds (excluded on
              Python 2.5 where httplib lacks timeout support).

    Note:
        The ``__init__`` method supports runtime mixin injection via
        ``__class__.__bases__`` modification, enabling callers to compose
        client behavior (e.g., adding PyCurlMixin for parallel execution)
        without separate subclass hierarchies.

    Request Lifecycle Sequence Diagram (Mermaid)::

        Caller -> DomainClient: client.method()
        DomainClient -> BaseClient: _call(subpath, params)
        BaseClient -> BaseClient: _prepare_request_auth()
        BaseClient -> BaseClient: _prepare_request()
        BaseClient -> HubSpotAPI: HTTP request with auth
        HubSpotAPI --> BaseClient: Response (possibly gzipped)
        BaseClient -> BaseClient: _execute_request_raw() + decompress
        BaseClient --> DomainClient: Parsed JSON result
    """

    # Why: [Trade-offs] — sleep_multiplier is a class attribute rather than an
    # instance attribute so that unit tests can override it to 0 for fast test
    # execution without waiting for exponential backoff delays. This is a
    # test-friendliness trade-off at the cost of global state.
    # Controls how long we sleep for during retries, overridden by unittests
    # so tests run faster
    sleep_multiplier = 1

    def __init__(self, api_key=None, timeout=10, mixins=[], access_token=None, refresh_token=None, client_id=None,  **extra_options):
        """Initialize the BaseClient with credentials, timeout, and optional mixins.

        Configure a new client instance with one of three supported
        authentication modes: API key, OAuth access token, or OAuth
        refresh token. Optionally inject mixin classes to extend client
        behavior at runtime (e.g., PyCurlMixin for parallel execution).

        Args:
            api_key (str or None): HubSpot API key. Mutually exclusive
                with access_token.
            timeout (int): HTTP request timeout in seconds. Default is 10.
                Ignored on Python 2.5 where httplib lacks timeout support.
            mixins (list): List of mixin classes to inject into the class
                hierarchy at runtime. Mixins are prepended to
                ``__class__.__bases__`` in reverse order so the first
                mixin in the caller's list has highest MRO priority.
            access_token (str or None): OAuth access token. Mutually
                exclusive with api_key.
            refresh_token (str or None): OAuth refresh token for
                automatic token renewal on 401 responses.
            client_id (str or None): OAuth client ID required for
                token refresh flow.
            **extra_options: Additional configuration options merged into
                the options dict. Supports 'api_base', 'hub_id',
                'portal_id', and any domain-specific options.

        Raises:
            Exception: If both api_key and access_token are provided,
                since they are mutually exclusive authentication modes.
            Exception: If none of api_key, access_token, or refresh_token
                are provided, since at least one credential is required.
        """
        super(BaseClient, self).__init__()
        # Why: [Trade-offs] — Dynamic mixin injection via __class__.__bases__
        # modification is used instead of standard multiple inheritance because
        # it allows callers to compose client behavior at runtime (e.g., adding
        # PyCurlMixin for parallel execution) without requiring separate
        # subclass hierarchies for every mixin combination. The reverse() call
        # ensures the first mixin in the caller's list becomes the first parent
        # in MRO, matching intuitive left-to-right priority. This modifies the
        # class itself (not just the instance), which means all instances of the
        # same subclass share the modified bases — a deliberate trade-off for
        # simplicity.
        # reverse so that the first one in the list because the first parent
        mixins.reverse()
        for mixin_class in mixins:
            if mixin_class not in self.__class__.__bases__:
                self.__class__.__bases__ = (mixin_class,) + self.__class__.__bases__

        self.api_key = api_key or extra_options.get('api_key')
        self.access_token = access_token or extra_options.get('access_token')
        self.refresh_token = refresh_token or extra_options.get('refresh_token')
        self.client_id = client_id or extra_options.get('client_id')
        self.log = utils.get_log('hapipy')
        # Why: [Alternatives Considered] — Mutual exclusion between api_key and
        # access_token is enforced at construction time rather than at request
        # time because failing fast prevents confusing authentication errors
        # later. The 'or' chain (api_key or access_token or refresh_token)
        # allows any single credential type to be sufficient, supporting three
        # distinct auth modes.
        if self.api_key and self.access_token:
            raise Exception("Cannot use both api_key and access_token.")
        if not (self.api_key or self.access_token or self.refresh_token):
            raise Exception("Missing required credentials.")
        self.options = {'api_base': 'api.hubapi.com'}
        # Why: [Assumptions Made] — The timeout parameter is conditionally
        # excluded for Python 2.5 because httplib in Python 2.5 does not
        # support the timeout keyword argument. The _PYTHON25 sentinel is
        # computed once at module load for efficiency.
        if not _PYTHON25:
            self.options['timeout'] = timeout
        self.options.update(extra_options)
        self._prepare_connection_type()

    def _prepare_connection_type(self):
        """Parse api_base to extract protocol and set connection_type.

        Inspect the ``api_base`` option to determine whether the API uses
        HTTP or HTTPS, then store the appropriate httplib connection class
        and strip the protocol prefix from api_base.

        Modifies ``self.options`` in-place, setting:
            - ``connection_type``: ``httplib.HTTPConnection`` or
              ``httplib.HTTPSConnection``.
            - ``protocol``: ``'http'`` or ``'https'``.
            - ``api_base``: Hostname without protocol prefix.

        Returns:
            None: Modifies self.options in-place.
        """
        connection_types = {'http': httplib.HTTPConnection, 'https': httplib.HTTPSConnection}
        parts = self.options['api_base'].split('://')
        protocol = (parts[0:-1]+['https'])[0]
        self.options['connection_type'] = connection_types[protocol]
        self.options['protocol'] = protocol
        self.options['api_base'] = parts[-1]

    def _get_path(self, subpath):
        """Return the API-versioned path prefix for this client.

        Abstract method that each domain client subclass must override to
        provide its specific API endpoint path. For example, BlogClient
        returns ``'content/api/v2/blogs'`` and KeywordsClient returns
        ``'keywords/v1/keywords'``.

        Args:
            subpath (str): The resource-specific path segment to append
                to the base API path.

        Raises:
            Exception: Always raised in BaseClient because this is an
                abstract method. Subclasses must provide an implementation.
        """
        raise Exception("Unimplemented get_path for BaseClient subclass!")

    def _prepare_request_auth(self, subpath, params, data, opts):
        """Inject authentication credentials into the request parameters.

        Apply the appropriate authentication strategy based on the
        configured credential type. For API key authentication, the key
        is added as the ``hapikey`` query parameter. For OAuth, the
        access_token is added as a query parameter.

        Endpoint Access:
            Auth Strategy: API key injected as ``hapikey`` query param,
                or OAuth token injected as ``access_token`` query param.
            Injection Point: Query string parameters (not HTTP headers),
                as required by the HubSpot API convention.

        Args:
            subpath (str): The API subpath for the request.
            params (dict): Mutable request parameters dict. Auth
                credentials are injected directly into this dict.
            data (str or dict or None): Request body data. Not modified
                by this method but included for signature consistency.
            opts (dict): Request options dict. Not modified by this
                method but included for signature consistency.

        Returns:
            None: Modifies params dict in-place.
        """
        # Why: [Alternatives Considered] — API key is injected as a query
        # parameter (hapikey) rather than an HTTP header because the HubSpot
        # API expects API keys in the URL. OAuth tokens are also passed as
        # query parameters (access_token) for the same reason. The fallback
        # logic below persists a method-invocation access_token to
        # self.access_token, enabling token caching across multiple calls.
        if self.api_key:
            params['hapikey'] = params.get('hapikey') or self.api_key
        else:
            # Be sure that we're consistent about what access_token is being used
            # If one was provided at instantiation, that is always used.  If it was not
            # but one was provided as part of the method invocation, we persist it
            if params.get('access_token') and not self.access_token:
                self.access_token = params.get('access_token')
            params['access_token'] = self.access_token

    def _prepare_request(self, subpath, params, data, opts, doseq=False, query=''):
        """Assemble the full request URL, headers, and serialized body.

        Construct the complete HTTP request components by combining the
        API path from ``_get_path()``, URL-encoded parameters, optional
        query string, standard headers (gzip, content type), and
        JSON-serialized body data.

        Args:
            subpath (str): The resource-specific API path segment.
            params (dict or None): Query parameters to URL-encode.
                Defaults to empty dict if None.
            data (str or dict or None): Request body. If a dict and
                Content-Type is ``'application/json'``, it will be
                JSON-serialized via simplejson.
            opts (dict): Request options containing overrides for
                ``'hub_id'``, ``'portal_id'``, ``'url'``, ``'headers'``,
                and ``'content_type'``.
            doseq (bool): If True, ``urllib.urlencode`` will encode
                sequence values as separate parameters. Default False.
            query (str): Additional raw query string to append to the
                URL. Leading ``'?'`` is stripped; leading ``'&'`` is
                added if missing.

        Returns:
            tuple: A 3-tuple of ``(url, headers, data)`` where:
                - url (str): Complete request URL path with query string.
                - headers (dict): HTTP headers including Accept-Encoding
                  and Content-Type.
                - data (str or None): Serialized request body, or None.
        """
        params = params or {}
        self._prepare_request_auth(subpath, params, data, opts)

        if opts.get('hub_id') or opts.get('portal_id'):
            params['portalId'] = opts.get('hub_id') or opts.get('portal_id')
        if query == None:
            query = ''
        if query and query.startswith('?'):
            query = query[1:]
        if query and not query.startswith('&'):
            query = '&' + query
        url = opts.get('url') or '/%s?%s%s' % (self._get_path(subpath), urllib.urlencode(params, doseq), query)
        headers = opts.get('headers') or {}
        # Why: [Assumptions Made] — Gzip encoding is always requested via the
        # Accept-Encoding header because HubSpot API responses can be large
        # (especially blog posts and lead lists). Manual decompression via
        # _gunzip_body is required because httplib does not automatically
        # decompress gzip responses (unlike the requests library). This is a
        # deliberate choice to use httplib for minimal dependencies.
        headers.update({
            'Accept-Encoding': 'gzip',
            'Content-Type': opts.get('content_type') or 'application/json'})

        # Why: [Assumptions Made] — Data is only JSON-serialized if it's not
        # already a string AND the Content-Type is application/json. This
        # allows callers to pass pre-serialized JSON strings or URL-encoded
        # form data (as in FormSubmissionClient) without double-encoding.
        if data and not isinstance(data, basestring) and headers['Content-Type']=='application/json':
            data = json.dumps(data)

        return url, headers, data

    def _create_request(self, conn, method, url, headers, data):
        """Execute the HTTP request on the connection and return request metadata.

        Dispatch the HTTP request via the httplib connection object and
        collect request metadata into a dict for use in error diagnostics
        and retry logging.

        Args:
            conn (httplib.HTTPConnection or httplib.HTTPSConnection):
                The active HTTP connection to the API host.
            method (str): HTTP method (e.g., ``'GET'``, ``'POST'``,
                ``'PUT'``, ``'DELETE'``, ``'PATCH'``).
            url (str): Complete request URL path with query string.
            headers (dict): HTTP request headers.
            data (str or None): Serialized request body.

        Returns:
            dict: Request metadata containing ``'method'``, ``'url'``,
                ``'data'``, ``'headers'``, ``'host'``, and ``'timeout'``
                (if not Python 2.5). Used by ``HapiError`` constructors
                for diagnostic reporting.
        """
        conn.request(method, url, data, headers)
        params = {'method':method, 'url':url, 'data':data, 'headers':headers, 'host':conn.host}
        if not _PYTHON25:
            params['timeout'] = conn.timeout
        return params

    def _gunzip_body(self, body):
        """Decompress a gzip-encoded response body.

        Use ``StringIO`` and ``GzipFile`` to decompress gzip-encoded bytes
        returned by the HubSpot API when the ``Accept-Encoding: gzip``
        header was sent in the request.

        Args:
            body (str): Gzip-compressed response body bytes.

        Returns:
            str: Decompressed response body content.
        """
        sio = StringIO.StringIO(body)
        gf = gzip.GzipFile(fileobj=sio, mode="rb")
        return gf.read()

    def _process_body(self, data, gzipped):
        """Conditionally decompress the response body based on encoding.

        Route the response body through gzip decompression if the
        response was gzip-encoded, otherwise return it unchanged.

        Args:
            data (str): Raw response body bytes from the HTTP response.
            gzipped (bool): True if the response Content-Encoding header
                indicated gzip compression.

        Returns:
            str: Decompressed body if gzipped was True, otherwise the
                original data unchanged.
        """
        if gzipped:
            return self._gunzip_body(data)
        return data

    def _execute_request_raw(self, conn, request):
        """Read HTTP response, decompress if gzipped, and map status codes to exceptions.

        Read the response from the httplib connection, check for gzip
        encoding and decompress if needed, then map non-success HTTP
        status codes to the appropriate ``HapiError`` subclass.

        Status-to-Exception Mapping:
            - 404, 410 -> ``HapiNotFound``
            - 401 -> ``HapiUnauthorized``
            - 400-499 (excl. 401/404/410), 501 -> ``HapiBadRequest``
            - 500+ (excl. 501) -> ``HapiServerError``
            - Connection/read failure -> ``HapiTimeout``
            - 200-299 -> Success (no exception raised)

        Args:
            conn (httplib.HTTPConnection or httplib.HTTPSConnection):
                The active HTTP connection with a pending response.
            request (dict): Request metadata dict from ``_create_request``,
                passed to ``HapiError`` constructors for diagnostic
                reporting.

        Returns:
            httplib.HTTPResponse: The HTTP response object with an
                additional ``.body`` attribute containing the
                (decompressed) response body string.

        Raises:
            HapiTimeout: On any connection or response read failure,
                with the traceback captured in the error message.
            HapiNotFound: When the API returns HTTP 404 or 410.
            HapiUnauthorized: When the API returns HTTP 401.
            HapiBadRequest: When the API returns HTTP 400-499 (except
                401, 404, 410) or 501.
            HapiServerError: When the API returns HTTP 500 or above
                (except 501).
        """
        try:
            result = conn.getresponse()
        except:
            raise HapiTimeout(None, request, traceback.format_exc())

        encoding = [i[1] for i in result.getheaders() if i[0] == 'content-encoding']
        result.body = self._process_body(result.read(), len(encoding) and encoding[0] == 'gzip')

        conn.close()
        if result.status in (404, 410):
            raise HapiNotFound(result, request)
        elif result.status == 401:
            raise HapiUnauthorized(result, request)
        elif result.status >= 400 and result.status < 500 or result.status == 501:
            raise HapiBadRequest(result, request)
        elif result.status >= 500:
            raise HapiServerError(result, request)

        return result

    def _execute_request(self, conn, request):
        """Execute the HTTP request and return only the response body.

        Convenience wrapper around ``_execute_request_raw`` that discards
        the response metadata and returns just the body content.

        Args:
            conn (httplib.HTTPConnection or httplib.HTTPSConnection):
                The active HTTP connection to the API host.
            request (dict): Request metadata dict from ``_create_request``.

        Returns:
            str: The (possibly decompressed) response body string.

        Raises:
            HapiError: Any subclass, propagated from
                ``_execute_request_raw``.
        """
        result = self._execute_request_raw(conn, request)
        return result.body

    def _digest_result(self, data):
        """Parse JSON response body, falling back to raw string if parsing fails.

        Attempt to deserialize the response body as JSON using simplejson.
        If the body is not valid JSON (e.g., empty responses, HTML error
        pages), silently catch the ValueError and return the raw data.

        Args:
            data (str or None): Response body string to parse, or None
                if no response body was received.

        Returns:
            dict, list, str, or None: Parsed JSON as a Python dict or
                list if parsing succeeded, the original string if JSON
                parsing failed, or None if the input was None or empty.
        """
        if data and isinstance(data, basestring):
            try:
                data = json.loads(data)
            except ValueError:
                pass

        return data

    def _prepare_request_retry(self, method, url, headers, data):
        """Provide a hook for subclasses to perform setup before a retry attempt.

        No-op in the base implementation. Subclasses (such as PyCurlMixin)
        can override this method to reset connection state or modify
        request parameters before the next retry iteration.

        Args:
            method (str): HTTP method of the request being retried.
            url (str): Full URL of the request being retried.
            headers (dict): HTTP headers of the request being retried.
            data (str or None): Request body of the request being retried.

        Returns:
            None: Base implementation performs no action.
        """
        pass

    def _call_raw(self, subpath, params=None, method='GET', data=None, doseq=False, query='', retried=False, **options):
        """Execute an HTTP request with retry logic, exponential backoff, and OAuth token refresh.

        This is the core request execution engine of BaseClient. It
        orchestrates the complete request lifecycle including URL and
        header preparation, connection creation, request dispatch, retry
        on transient failures, exponential backoff between retries, and
        automatic OAuth token refresh on 401 responses.

        Retry Behavior:
            - Maximum retries: 6 (hard cap regardless of number_retries
              option value).
            - Emergency brake: Loop terminates after 10 iterations
              regardless of retry counter, as a safety net against
              infinite loops.
            - Non-idempotent methods: POST, PUT, and DELETE are never
              retried unless ``retry_on_post=True`` is passed in options.
            - Exponential backoff: Sleep duration is computed as
              ``(2^(try_count-1) - 1) * sleep_multiplier``, producing
              the sequence 0, 1, 3, 7, 15, 31 seconds.
            - Client errors (300-499): Never retried, as these indicate
              request problems that will not be resolved by retrying.
            - OAuth refresh: On 401 with refresh_token and client_id
              available, attempts a single token refresh then retries
              once. Uses the ``retried`` flag to prevent infinite refresh
              loops.

        Args:
            subpath (str): Resource-specific API path segment passed to
                ``_get_path()``.
            params (dict or None): Query parameters for the request.
                Default None (converted to empty dict internally).
            method (str): HTTP method. Default ``'GET'``. Also accepts
                ``'POST'``, ``'PUT'``, ``'DELETE'``, ``'PATCH'``.
            data (str or dict or None): Request body. Dicts are
                JSON-serialized if Content-Type is application/json.
            doseq (bool): If True, sequence parameter values are encoded
                as separate query parameters. Default False.
            query (str): Additional raw query string appended to the URL.
                Default empty string.
            retried (bool): Internal flag indicating this is a retry
                after OAuth token refresh. Prevents infinite refresh
                loops. Default False. Callers should not set this.
            **options: Additional options merged with self.options.
                Supports ``'number_retries'`` (int),
                ``'retry_on_post'`` (bool), ``'content_type'`` (str),
                ``'url'`` (str), ``'headers'`` (dict).

        Returns:
            httplib.HTTPResponse: The HTTP response object with ``.body``
                attribute containing the (decompressed) response body.

        Raises:
            HapiUnauthorized: When 401 received and token refresh is not
                possible or has already been attempted.
            HapiNotFound: When the API returns HTTP 404 or 410.
            HapiBadRequest: When the API returns HTTP 400-499 or 501.
            HapiServerError: When the API returns HTTP 500+.
            HapiTimeout: On connection or read failures.
            HapiError: After exhausting all retry attempts on server
                errors or transient failures.
        """
        opts = self.options.copy()
        opts.update(options)
        url, headers, data = self._prepare_request(subpath, params, data, opts, doseq, query)
        kwargs = {}
        if not _PYTHON25:
            kwargs['timeout'] = opts['timeout']

        num_retries = opts.get('number_retries', 0)
        # Why: [Trade-offs] — POST, PUT, and DELETE requests are never retried
        # by default because these methods are not idempotent — retrying could
        # create duplicate resources or trigger duplicate side effects. The
        # retry_on_post option exists as an escape hatch for callers who know
        # their specific endpoint is safe to retry.
        # Never retry a POST, PUT, or DELETE unless explicitly told to
        if method != 'GET' and not opts.get('retry_on_post'):
            num_retries = 0
        # Why: [Trade-offs] — The retry cap at 6 prevents excessive retry
        # storms against the HubSpot API while still allowing recovery from
        # transient network issues. With exponential backoff (0, 1, 3, 7, 15,
        # 31 seconds), 6 retries spans approximately 57 seconds of total wait
        # time, balancing recovery probability against caller patience.
        if num_retries > 6:
            num_retries = 6
        # Why: [Future-proofing] — The emergency brake at 10 iterations is a
        # safety net independent of the retry counter, protecting against bugs
        # in the while-loop logic that could cause infinite loops. This is
        # defensive programming — even if num_retries logic has a bug, the
        # loop will always terminate within 10 iterations.
        emergency_brake = 10
        try_count = 0
        while True:
            emergency_brake -= 1
            # avoid getting burned by any mistakes in While loop logic
            if emergency_brake < 1:
                break
            try:
                try_count += 1
                connection = opts['connection_type'](opts['api_base'], **kwargs)
                request_info = self._create_request(connection, method, url, headers, data)
                result = self._execute_request_raw(connection, request_info)
                break
            except HapiUnauthorized, e:
                # Why: [Alternatives Considered] — Token refresh is handled
                # inside _call_raw rather than as a separate middleware layer
                # because it needs access to the retry context (retried flag)
                # to prevent infinite refresh loops. The single-retry approach
                # (retried=True on recursive call) ensures that if the
                # refreshed token is also rejected, we fail loudly rather than
                # entering a refresh loop.
                self.log.warning("401 Unauthorized response to API request.")
                if self.access_token and self.refresh_token and self.client_id and not retried:
                    self.log.info("Refreshing access token")
                    try:
                        token_response = utils.refresh_access_token(self.refresh_token, self.client_id)
                        decoded = json.loads(token_response)
                        self.access_token = decoded['access_token']
                        self.log.info('Retrying with new token %' % (self.access_token))
                    except Exception, e:
                        self.log.error("Unable to refresh access_token: %s" % (e))
                        raise
                    return self._call_raw(subpath, params=params, method=method, data=data, doseq=doseq, query=query, retried=True, **options)
                else:
                    if self.access_token and self.refresh_token and self.client_id and retried:
                        self.log.error("Refreshed token, but request still was not authorized.  You may need to grant additional permissions.")
                    elif self.access_token and not self.refresh_token:
                        self.log.error("In order to enable automated refreshing of your access token, please provide a refresh token as well.")
                    elif self.access_token and not self.client_id:
                        self.log.error("In order to enable automated refreshing of your access token, please provide a client_id in addition to a refresh token.")
                    raise
            except HapiError, e:
                if try_count > num_retries:
                    logging.warning("Too many retries for %s", url)
                    raise
                # Why: [Assumptions Made] — Client errors (300-499) are never
                # retried because they typically indicate a problem with the
                # request itself (bad parameters, missing permissions, not
                # found) that won't be resolved by retrying. Only server errors
                # (500+) and transient failures are retried.
                # Don't retry errors from 300 to 499
                if e.result and e.result.status >= 300 and e.result.status < 500:
                    raise
                self._prepare_request_retry(method, url, headers, data)
                self.log.warning('HapiError %s calling %s, retrying' % (e, url))
            # Why: [Alternatives Considered] — The formula (2^(try_count-1) - 1)
            # produces a backoff sequence of 0, 1, 3, 7, 15, 31 seconds.
            # Starting at 0 allows the first retry to be immediate (useful for
            # transient network blips), while subsequent retries grow
            # exponentially. The sleep_multiplier allows test-time override
            # without changing the backoff curve shape.
            # exponential back off - wait 0 seconds, 1 second, 3 seconds, 7 seconds, 15 seconds, etc.
            time.sleep((pow(2, try_count - 1) - 1) * self.sleep_multiplier)
        return result

    def _call(self, subpath, params=None, method='GET', data=None, doseq=False, query='', **options):
        """Execute an HTTP call and parse the JSON response.

        High-level convenience method used by most domain client methods.
        Delegates to ``_call_raw()`` for request execution with
        ``retried=False``, then passes the response body through
        ``_digest_result()`` for JSON parsing.

        Args:
            subpath (str): Resource-specific API path segment.
            params (dict or None): Query parameters for the request.
            method (str): HTTP method. Default ``'GET'``.
            data (str or dict or None): Request body data.
            doseq (bool): Encode sequence values as separate params.
                Default False.
            query (str): Additional raw query string. Default empty.
            **options: Additional options passed through to ``_call_raw``.

        Returns:
            dict, list, str, or None: Parsed JSON response as a Python
                dict or list, raw string if JSON parsing failed, or
                None if the response body was empty.

        Raises:
            HapiError: Any subclass, propagated from ``_call_raw``.
        """
        result = self._call_raw(subpath, params=params, method=method, data=data, doseq=doseq, query=query, retried=False, **options)
        return self._digest_result(result.body)
