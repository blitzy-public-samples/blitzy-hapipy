"""HubSpot Keywords API v1 client module for managing SEO keywords.

Provides the KeywordsClient class for CRUD operations on SEO keywords
tracked in a HubSpot portal. Supports retrieving individual or batch
keywords, adding single or multiple keywords, and deleting keywords.

Public methods:
    - get_keywords_info: Retrieve keywords with full response metadata.
    - get_keywords: Retrieve keyword list only (convenience wrapper).
    - get_keyword: Retrieve a single keyword by GUID.
    - add_keyword: Add a single keyword via PUT.
    - add_keywords: Add multiple keywords in batch via PUT.
    - delete_keyword: Delete a keyword by GUID.

All API calls route through BaseClient (hapi/base.py) for authentication,
request construction, retry logic, and response parsing.

Example:
    client = KeywordsClient(api_key='demo')
    keywords = client.get_keywords()
"""
try:
    from hapi.base import BaseClient
except ImportError:
    from base import BaseClient

KEYWORDS_API_VERSION = 'v1'

class KeywordsClient(BaseClient):
    """Client for HubSpot Keywords API v1 providing CRUD operations on SEO keywords.

    Wraps the HubSpot Keywords API v1 endpoints for creating, reading,
    and deleting SEO keywords tracked in a HubSpot portal. All endpoints
    route through the keywords/v1/ subpath prefix, constructed by the
    overridden _get_path method.

    Inherits from BaseClient which provides the HTTP engine, retry logic,
    authentication injection, and response parsing pipeline. See
    hapi.base.BaseClient for the full request lifecycle.

    Attributes:
        KEYWORDS_API_VERSION (str): Module-level constant set to 'v1',
            used by _get_path to construct versioned endpoint URLs.
    """

    def _get_path(self, subpath):
        """Construct the fully qualified Keywords API path.

        Prepend the keywords API version prefix to the given subpath,
        producing paths like 'keywords/v1/keywords' or
        'keywords/v1/keywords/{guid}'.

        Args:
            subpath (str): The resource-specific path segment to append
                after the versioned keywords prefix.

        Returns:
            str: Fully qualified keywords API path in the format
                'keywords/{version}/{subpath}'.
        """
        return 'keywords/%s/%s' % (KEYWORDS_API_VERSION, subpath)

    # Why: [Alternatives Considered] — get_keywords_info returns the complete API
    # response including metadata (e.g., total count, offset) alongside the keyword
    # list, whereas get_keywords extracts only the 'keywords' list for convenience.
    # Both methods exist to serve different caller needs without requiring separate
    # API endpoints.
    def get_keywords_info(self, **options):
        """Retrieve all keywords with full response metadata.

        Fetch the complete keyword listing from HubSpot including both
        the keyword entries and any response-level metadata such as
        total count and pagination offsets.

        Endpoint Access:
            HTTP Method: GET
            URL: /keywords/v1/keywords
            Auth: API key injected as query parameter or OAuth access token.
            Body: None.
            Response: JSON dict containing a 'keywords' list and metadata.

        Args:
            **options: Optional keyword arguments passed through to
                BaseClient._call() for request customization (e.g.,
                hub_id, portal_id, number_retries).

        Returns:
            dict: Full API response including the 'keywords' list and
                any additional metadata fields.

        Raises:
            HapiError: When the API returns a non-2xx status code.
        """
        return self._call('keywords', **options)

    def get_keywords(self, **options):
        """Retrieve only the list of keyword entries.

        Convenience wrapper around get_keywords_info that extracts the
        'keywords' key from the full API response, returning only the
        keyword entries without response-level metadata.

        Endpoint Access:
            HTTP Method: GET
            URL: /keywords/v1/keywords
            Auth: API key injected as query parameter or OAuth access token.
            Body: None.
            Response: JSON dict from which the 'keywords' list is extracted.

        Args:
            **options: Optional keyword arguments passed through to
                BaseClient._call() for request customization (e.g.,
                hub_id, portal_id, number_retries).

        Returns:
            list: Keyword entries extracted from the API response's
                'keywords' key.

        Raises:
            HapiError: When the API returns a non-2xx status code.
        """
        return self._call('keywords', **options)['keywords']

    def get_keyword(self, keyword_guid, **options):
        """Retrieve a single keyword by its GUID.

        Fetch detailed information about a specific keyword identified
        by its unique GUID from the HubSpot Keywords API.

        Endpoint Access:
            HTTP Method: GET
            URL: /keywords/v1/keywords/{keyword_guid}
            Auth: API key injected as query parameter or OAuth access token.
            Body: None.
            Response: JSON dict containing the keyword data.

        Args:
            keyword_guid (str): The unique identifier of the keyword
                to retrieve.
            **options: Optional keyword arguments passed through to
                BaseClient._call() for request customization.

        Returns:
            dict: Keyword data for the specified GUID.

        Raises:
            HapiError: When the API returns a non-2xx status code.
        """
        return self._call('keywords/%s' % keyword_guid, **options)

    # Why: [Alternatives Considered] — The HubSpot Keywords API uses PUT for both
    # single keyword creation (add_keyword) and batch keyword creation (add_keywords),
    # rather than POST. This is a HubSpot API design choice where PUT is used for
    # idempotent keyword registration, and the distinction between single vs. batch
    # is determined by whether data is a dict or list.
    def add_keyword(self, keyword, **options):
        """Add a single keyword to the HubSpot portal.

        Register a new SEO keyword by sending a PUT request with a dict
        body containing the keyword string. The keyword value is coerced
        to a string via str() before submission.

        Endpoint Access:
            HTTP Method: PUT
            URL: /keywords/v1/keywords
            Auth: API key injected as query parameter or OAuth access token.
            Body: JSON-encoded dict with format {'keyword': '<keyword_string>'}.
            Response: JSON dict containing the created keyword data.

        Args:
            keyword (str): The keyword string to add. Coerced to str
                via str(keyword) before wrapping in the request payload
                as data=dict(keyword=str(keyword)).
            **options: Optional keyword arguments passed through to
                BaseClient._call() for request customization.

        Returns:
            dict: API response containing the created keyword data.

        Raises:
            HapiError: When the API returns a non-2xx status code.
        """
        return self._call('keywords', data=dict(keyword=str(keyword)), method='PUT', **options)

    # Why: [Trade-offs] — The input normalization loop accepts mixed types (str and
    # dict) in the keywords list for caller convenience, but this means the method
    # must perform type checking per-element. Empty strings are silently skipped
    # rather than raising an error, which prevents batch failures from whitespace or
    # empty entries at the cost of silent data loss if a caller accidentally passes
    # empty strings.
    def add_keywords(self, keywords, **options):
        """Add multiple keywords to the HubSpot portal in batch.

        Register multiple SEO keywords in a single PUT request. The input
        list is normalized before submission: empty strings are skipped,
        dict entries are passed through as-is, and string entries are
        wrapped in {'keyword': '<string>'} format.

        Endpoint Access:
            HTTP Method: PUT
            URL: /keywords/v1/keywords
            Auth: API key injected as query parameter or OAuth access token.
            Body: JSON-encoded list of keyword dicts, each containing
                at minimum a 'keyword' key.
            Response: JSON dict from which the 'keywords' list is extracted.

        Args:
            keywords (list): List of keywords to add. Each element may be
                a str (wrapped in dict(keyword=str(value))) or a dict
                (passed through directly). Empty strings are silently
                skipped during normalization.
            **options: Optional keyword arguments passed through to
                BaseClient._call() for request customization.

        Returns:
            list: Keyword entries from the API response's 'keywords' key,
                representing the successfully created keywords.

        Raises:
            HapiError: When the API returns a non-2xx status code.
        """
        data = []
        for keyword in keywords:
            if keyword != '':
                if type(keyword) is dict:
                    data.append(keyword)
                elif type(keyword) is str:
                    data.append(dict(keyword=str(keyword)))
        return self._call('keywords', data=data, method='PUT', **options)['keywords']

    def delete_keyword(self, keyword_guid, **options):
        """Delete a keyword from the HubSpot portal by its GUID.

        Remove a tracked SEO keyword identified by its unique GUID
        from the HubSpot portal via a DELETE request.

        Endpoint Access:
            HTTP Method: DELETE
            URL: /keywords/v1/keywords/{keyword_guid}
            Auth: API key injected as query parameter or OAuth access token.
            Body: None.
            Response: API confirmation of deletion.

        Args:
            keyword_guid (str): The unique identifier of the keyword
                to delete.
            **options: Optional keyword arguments passed through to
                BaseClient._call() for request customization.

        Returns:
            Response data from the API confirming deletion.

        Raises:
            HapiError: When the API returns a non-2xx status code.
        """
        return self._call('keywords/%s' % keyword_guid, method='DELETE', **options)
