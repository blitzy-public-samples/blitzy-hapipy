'''
The the mixins in this file require PyCURL in order to make parallel API calls.  
On OSX and Linux machines, PyCURL can be installed via pip (run "pip install pycurl" ).  
For windows machines, pre-compiled PyCURL binaries can be downloaded 
[here for python 2.6 and 2.7](http://www.lfd.uci.edu/~gohlke/pythonlibs/#pycurl), and 
[here for python 2.5](http://www.lfd.uci.edu/~gohlke/pythonlibs/#pycurl).
'''

import pycurl, cStringIO

# Why: [Alternatives Considered] — pycurl was selected over requests-futures or
# concurrent.futures because pycurl's CurlMulti interface provides true parallel
# HTTP connections managed at the C level via libcurl, avoiding Python GIL
# limitations. This matters for high-volume API operations where connection setup
# overhead dominates. The trade-off is a platform-specific C dependency (pycurl
# requires libcurl development headers to install) vs. pure-Python alternatives
# that would be easier to install but limited by the GIL.

class HapiThreadedError(ValueError):
    """Error wrapper for threaded request failures in PyCurlMixin's parallel execution pipeline.

    Inherits from ValueError for compatibility with existing except ValueError
    handlers throughout the codebase. Captures the full pycurl.Curl handle's
    request metadata and response data at construction time, enabling detailed
    post-mortem diagnostics without retaining the live Curl object.

    Relationship:
        Used by PyCurlMixin.process_queue() when a queued HTTP request completes
        with an error status (0 or 400+).
    """

    def __init__(self, curl):
        """Construct error from a completed pycurl.Curl handle.

        Extract response body and headers from the Curl handle's cStringIO
        buffers into instance attributes for post-mortem inspection. The
        response body is also passed to the parent ValueError as the error
        message string.

        Args:
            curl (pycurl.Curl): The completed Curl handle with response data
                in body and response_headers cStringIO buffers. Must have
                body.getvalue() and response_headers.getvalue() available.

        Sets:
            self.c (pycurl.Curl): Reference to the original Curl handle.
            self.response_body (str): Raw response body from the API call.
            self.response_headers (str): Raw response headers from the API call.
        """
        super(HapiThreadedError, self).__init__(curl.body.getvalue())
        self.c = curl
        self.response_body = self.c.body.getvalue()
        self.response_headers = self.c.response_headers.getvalue()

    def __str__(self):
        """Return a multi-section diagnostic string showing the full request/response cycle.

        Format includes sections for request metadata (method, host, path,
        timeout), request body, request headers, result status code, response
        body, and response headers. Uses getattr for 'method' with empty string
        default since not all Curl handles have the method attribute set.

        Returns:
            str: Formatted multi-section diagnostic string with labeled
                request and response data for debugging failed API calls.
        """
        return "\n---- request ----\n%s %s%s [timeout=%s]\n\n---- body ----\n%s\n\n---- headers ----\n%s\n\n---- result ----\n%s\n\n---- body ----\n%s\n\n---- headers ----\n%s" % (
            getattr(self.c, 'method', ''), 
            self.c.host, 
            self.c.path, 
            self.c.timeout,
            self.c.data,
            self.c.headers,
            self.c.status,
            self.response_body,
            self.response_headers)

    def __unicode__(self):
        """Delegate to __str__ for Python 2.x unicode compatibility.

        Returns:
            unicode: Same output as __str__, ensuring consistent string
                representation in both str and unicode contexts.
        """
        return self.__str__()

class PyCurlMixin(object):
    """Mixin that replaces BaseClient's synchronous _call with queue-and-batch parallel execution.

    PyCurlMixin relies on PyCurl, which is a library around libcurl which enables efficient
    multi-threaded requests.  Use this mixin when you want to be able to execute multiple
    API calls at once, instead of in sequence.

    Enable by calling client.mixin(PyCurlMixin) after importing PyCurlMixin and instantiating
    the client of your choice.

    Once enabled, use like so:
        client.my_api_call()
        client.my_other_api_call()
        results = client.process_queue()

    The results object will then return a list of dicts, containing the response to your calls
    in the order they were called. Dicts have keys: data, code, and (if something went wrong) exception.

    Relationship to BaseClient:
        Injected at runtime via BaseClient.__init__'s mixins parameter, which
        prepends PyCurlMixin to __class__.__bases__. This makes PyCurlMixin._call
        override BaseClient._call in the MRO, redirecting all API calls into the
        internal queue instead of executing them immediately.

    Key Methods:
        _call: Queues a single HTTP request for later parallel execution.
        _enqueue: Internal queue append (lazily initializes the queue).
        _create_curl: Builds a fully configured pycurl.Curl handle.
        process_queue: Executes all queued requests in parallel and returns results.

    Attributes:
        _queue (list of tuple): Lazily initialized internal queue storing
            (url, headers, data) tuples produced by BaseClient._prepare_request.

    Dependencies:
        pycurl: C-level libcurl bindings for parallel HTTP via CurlMulti.
        cStringIO: C-level string buffers for efficient response collection.
    """
    # Why: [Trade-offs] — The queue-and-batch execution model (queue requests via
    # _call, execute all via process_queue) was chosen over immediate-async-with-
    # callback because it simplifies error handling and result collection. Callers
    # get all results at once in a single list rather than managing individual
    # callbacks or futures, but this means no results are available until ALL queued
    # requests complete.
    def _call(self, subpath, params=None, method='GET', data=None, doseq=False, **options):
        """Override BaseClient._call to queue a request for later parallel execution.

        Instead of executing the HTTP request immediately, merge per-call options
        with client defaults, delegate URL/header/body construction to
        BaseClient._prepare_request, and enqueue the resulting tuple for batch
        execution via process_queue().

        Args:
            subpath (str): API endpoint subpath passed to _prepare_request
                for URL construction via _get_path.
            params (dict or None): Query parameters to include in the request
                URL. Defaults to None.
            method (str): HTTP method for the request. Defaults to 'GET'.
                Note: method is passed through options but not directly used
                by _prepare_request in the queue path.
            data (str or dict or None): Request body payload. Defaults to None.
            doseq (bool): Whether to use doseq in urllib.urlencode for
                multi-valued query parameters. Defaults to False.
            **options: Per-call option overrides merged with self.options.
                Common keys include 'content_type' and 'hub_id'.

        Returns:
            None: The request is queued, not executed. Call process_queue()
                to execute all queued requests and retrieve results.
        """
        opts = self.options.copy()
        opts.update(options)

        request_parts = self._prepare_request(subpath, params, data, opts, doseq=doseq)
        self._enqueue(request_parts)

    def _enqueue(self, parts):
        """Append a prepared request tuple to the internal _queue list.

        Lazily initializes the _queue list on first call since PyCurlMixin
        is injected at runtime and its __init__ is never invoked.

        Args:
            parts (tuple): The (url, headers, data) tuple produced by
                BaseClient._prepare_request.

        Returns:
            None.
        """
        # Why: [Assumptions Made] — The _queue list is lazily initialized via hasattr
        # check rather than in __init__ because PyCurlMixin is injected at runtime via
        # __class__.__bases__ modification, so its __init__ is never called. The mixin
        # cannot rely on constructor-based initialization.
        if not hasattr(self, "_queue"):
            self._queue = []

        self._queue.append(parts)

    def _create_curl(self, url, headers, data):
        """Create and configure a pycurl.Curl handle from prepared request parts.

        Build a fully configured Curl handle by constructing the full URL from
        protocol + api_base + url path, setting up cStringIO buffers for
        response body and response headers collection, and caching request
        metadata on the handle itself for diagnostic use by HapiThreadedError.

        Configures WRITEFUNCTION and HEADERFUNCTION callbacks to direct response
        data into the cStringIO buffers. Optionally sets HTTPHEADER for custom
        request headers and READFUNCTION for request body data when present.

        Args:
            url (str): The URL path portion (protocol and host are prepended
                from self.options['protocol'] and self.options['api_base']).
            headers (dict or None): HTTP headers as key-value pairs. When
                truthy, converted to 'Key: Value' format for HTTPHEADER.
            data (str or None): Request body payload. When truthy, a
                cStringIO buffer is created and READFUNCTION is configured.

        Returns:
            pycurl.Curl: Fully configured Curl handle ready for CurlMulti
                scheduling, with body and response_headers cStringIO buffers
                attached for response collection.
        """
        c = pycurl.Curl()

        full_url = "%s://%s%s" % (self.options['protocol'], self.options['api_base'], url)
        
        c.timeout = self.options['timeout']
        c.protocol = self.options['protocol']
        c.host = self.options['api_base']
        c.path = url
        c.full_url = full_url
        c.headers = headers
        c.data = data

        # Why: [Assumptions Made] — The initial status is set to -1 as a sentinel
        # indicating "not yet executed." This distinguishes handles that failed before
        # receiving any HTTP response from those that received a 0-status response.
        c.status = -1
        c.body = cStringIO.StringIO()
        c.response_headers = cStringIO.StringIO()

        c.setopt(c.URL, c.full_url)
        c.setopt(c.TIMEOUT, self.options['timeout'])
        c.setopt(c.WRITEFUNCTION, c.body.write)
        c.setopt(c.HEADERFUNCTION, c.response_headers.write)

        if headers:
            c.setopt(c.HTTPHEADER, [ "%s: %s" % (x, y) for x, y in headers.items() ])

        if data:
            c.data_out = cStringIO.StringIO(data)
            c.setopt(c.READFUNCTION, c.data_out.getvalue)

        return c

    def process_queue(self):
        """Execute all queued HTTP requests in parallel and return collected results.

        Batch execution counterpart to _call's queue operation. Processes all
        API calls queued since the last invocation (or since client creation)
        using pycurl's CurlMulti interface for true parallel HTTP connections.

        Three-phase execution:
            1. Create CurlMulti manager and add all queued Curl handles via
               _create_curl, which builds handles from the (url, headers, data)
               tuples stored in _queue.
            2. CurlMulti perform/select loop: repeatedly call m.perform() until
               all handles complete, using m.select(1.0) to avoid busy-waiting.
            3. Result collection: extract HTTP status codes, decompress gzip
               responses via _gunzip_body, parse response bodies via
               _digest_result, wrap failed requests in HapiThreadedError, and
               perform deterministic cleanup of all C-level resources.

        Returns:
            list of dict: Each dict contains:
                - 'data': Parsed JSON (dict/list) or raw response string,
                  produced by BaseClient._digest_result.
                - 'code' (int): HTTP status code from the response.
                - 'exception' (HapiThreadedError): Present only when status
                  is 0 (connection failure) or >= 400 (HTTP error). Contains
                  full request/response diagnostics.
                Results are ordered to match the order requests were queued.

        Raises:
            No exceptions are raised directly. Errors on individual requests
            are captured as 'exception' entries in result dicts rather than
            raised, so that successful requests are not lost due to individual
            failures in the batch.
        """
        m = pycurl.CurlMulti()
        m.handles = []

        # Loop the queue and create Curl objects for processing
        for item in self._queue:
            c = self._create_curl(*item)
            m.add_handle(c)
            m.handles.append(c)

        # Process the collected Curl handles
        num_handles = len(m.handles)
        while num_handles:
            while 1:
                # Perform the calls
                ret, num_handles = m.perform()
                if ret != pycurl.E_CALL_MULTI_PERFORM:
                    break
            m.select(1.0)

        # Collect data
        results = []
        for c in m.handles:
            c.status = c.getinfo(c.HTTP_CODE)
            if 'Content-Encoding: gzip' in c.response_headers.getvalue():
                c.body = cStringIO.StringIO(self._gunzip_body(c.body.getvalue()))
            result = { "data" : self._digest_result(c.body.getvalue()), "code": c.status }
            # Why: [Trade-offs] — Failed requests (status 0 or >= 400) are captured as
            # HapiThreadedError entries in the result dict rather than raised as exceptions
            # because raising would abort result collection for ALL queued requests. Since
            # the batch may contain both successful and failed requests, preserving all
            # results lets callers handle failures individually.
            if not c.status or c.status >= 400:
                result['exception'] = HapiThreadedError(c)

            results.append(result)

            
        # Why: [Future-proofing] — Deterministic cleanup (closing all cStringIO buffers,
        # detaching and closing Curl handles, closing the CurlMulti manager, and clearing
        # the queue) is performed explicitly rather than relying on Python's garbage
        # collector because pycurl wraps C-level resources that may not be freed promptly
        # by Python's reference-counting GC, especially in long-running processes.
        for c in m.handles:
            if hasattr(c, "data_out"):
                c.data_out.close()

            c.body.close()
            c.response_headers.close()
            c.close()
            m.remove_handle(c)

        m.close()
        del m.handles
        self._queue = []

        return results 
