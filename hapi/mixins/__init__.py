"""Optional runtime mixin classes that extend BaseClient functionality.

The ``hapi.mixins`` package provides mixin classes that augment any
:class:`~hapi.base.BaseClient` subclass with additional capabilities
without requiring separate subclass hierarchies for every mixin
combination.  Mixins are designed to be composed at construction time
so that a single client instance can gain new behaviour transparently.

Available Mixins
----------------
PyCurlMixin (hapi.mixins.threading)
    Provides parallel HTTP execution using pycurl's CurlMulti
    interface for batching multiple HubSpot API calls into a single
    network round-trip.  When mixed in, the standard ``_call`` method
    is overridden so that each API invocation is enqueued rather than
    executed immediately.  A subsequent call to ``process_queue()``
    flushes the queue and returns results for every enqueued request
    in the order they were submitted.  Requires the ``pycurl``
    external package (C-level libcurl bindings).

Mixin Injection Mechanism
-------------------------
Mixins are passed as classes in the ``mixins=[]`` constructor
parameter of any :class:`~hapi.base.BaseClient` subclass.  At
construction time, :meth:`BaseClient.__init__` (``hapi/base.py``,
lines 27-30) prepends each mixin class to ``__class__.__bases__``,
dynamically inserting the mixin into the class hierarchy *above*
``BaseClient`` in Python's Method Resolution Order (MRO).  This means
that a mixin method such as :meth:`PyCurlMixin._call` takes
precedence over :meth:`BaseClient._call`, enabling the queue-and-batch
execution model without the caller changing any domain-client method
calls.

The list is reversed before injection so that the first mixin supplied
by the caller ends up as the first parent class, giving it the highest
priority in the MRO.

Usage Example
-------------
::

    from hapi.blog import BlogClient
    from hapi.mixins.threading import PyCurlMixin

    client = BlogClient(api_key='demo', mixins=[PyCurlMixin])

    # Each call is enqueued, not executed immediately.
    client.get_blogs()
    client.get_blog_info('blog-guid')

    # Execute all queued requests in parallel via pycurl.CurlMulti.
    results = client.process_queue()

    # *results* is a list of dicts (one per enqueued call) with keys:
    #   "data"  — parsed response body
    #   "code"  — HTTP status code
    #   "exception" — HapiThreadedError instance (only on failure)

Note
----
This ``__init__.py`` file exists solely to make ``hapi/mixins/`` a
proper Python package so that statements such as
``from hapi.mixins.threading import PyCurlMixin`` resolve correctly.
No classes or functions are exported from the package root; each mixin
must be imported directly from its own module.
"""
