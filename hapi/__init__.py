"""Top-level package for hapipy, a Python wrapper library around HubSpot's REST APIs.

hapipy (version 2.10.6) provides a set of domain-specific client classes that
simplify interaction with HubSpot's HTTP-based service endpoints.  Each client
handles URL construction, authentication injection, request serialization,
response deserialization, gzip decompression, and automatic retry with
exponential back-off so that callers can work with plain Python objects instead
of raw HTTP.

Available Domain Clients
------------------------

    hapi.blog.BlogClient
        Blog Content API v1 -- publish, retrieve, update, and delete blog
        posts; list blogs, comments, and topics.

    hapi.broadcast.BroadcastClient
        Social Broadcast API v1 -- schedule, list, and cancel social-media
        broadcasts; query publishing channels.

    hapi.forms.FormSubmissionClient
        Form Submission API -- submit URL-encoded form data to the HubSpot
        Forms service (note: this client targets the forms.hubspot.com host
        rather than the standard api.hubapi.com endpoint).

    hapi.keywords.KeywordsClient
        Keywords API v1 -- manage SEO keywords: create single or batch
        keywords, retrieve, and delete.

    hapi.leads.LeadsClient
        Leads API v1 -- full lead life-cycle management including CRUD
        operations, free-text search, and lead closure.

    hapi.prospects.ProspectsClient
        Prospects API v1 -- track anonymous company visitors across the
        timeline, filterable by company, city, state, region, or country.

Core Architecture
-----------------
Every domain client inherits from ``hapi.base.BaseClient``, the shared HTTP
engine that owns the request/response life-cycle.  BaseClient provides:

*   Retry logic with exponential back-off (up to 6 retries, emergency brake
    at 10 consecutive calls).
*   Three authentication strategies -- API key, OAuth access token, and OAuth
    refresh token -- injected transparently into every outbound request.
*   Automatic gzip decompression of response bodies.
*   Unified error mapping from HTTP status codes to the ``hapi.error.HapiError``
    exception hierarchy.

Domain clients specialise BaseClient by overriding ``_get_path(subpath)`` to
prepend the API-version-specific URL prefix for their endpoint family.  All
HTTP dispatch ultimately flows through ``BaseClient._call_raw()``.

Authentication
--------------
Three mutually exclusive authentication modes are supported:

1.  **API key** -- passed as the ``hapikey`` query-string parameter.
2.  **OAuth access token** -- sent in the ``Authorization: Bearer`` header.
3.  **OAuth refresh token** -- the client transparently refreshes the access
    token before each call when a refresh token, client ID, and client secret
    are provided.

See ``docs/intro.md`` for detailed authentication setup and examples.

Mixin System
------------
The ``hapi.mixins`` package provides optional run-time capabilities that can
be injected into any client instance via ``client.mixin(MixinClass)``.  The
primary mixin is ``hapi.mixins.threading.PyCurlMixin``, which replaces the
default sequential HTTP dispatch with PyCURL-powered parallel execution,
returning results as a list in call order.

Error Handling
--------------
All API errors surface as subclasses of ``hapi.error.HapiError``, which
captures the HTTP status code, response body, request URL, and headers for
diagnostic inspection.  ``hapi.error.EmptyResult`` serves as a Null-Object
sentinel when the API returns a successful but empty response.

Class Hierarchy
---------------
The inheritance tree for the public client surface is shown below (Mermaid
notation)::

    classDiagram
        BaseClient <|-- BlogClient
        BaseClient <|-- BroadcastClient
        BaseClient <|-- FormSubmissionClient
        BaseClient <|-- KeywordsClient
        BaseClient <|-- LeadsClient
        BaseClient <|-- ProspectsClient
        BaseClient <|-- PyCurlMixin

Quick Start
-----------
::

    from hapi.blog import BlogClient
    client = BlogClient(api_key='your-api-key')
    blogs = client.get_blogs()
"""
