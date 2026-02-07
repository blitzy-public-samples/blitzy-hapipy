"""HubSpot Prospects API v1 client for company prospect tracking and discovery.

This module provides the ProspectsClient class, a specialized wrapper around
HubSpot's Prospects API v1 that enables tracking and discovery of company
prospects visiting your website. All API interactions route through
BaseClient (defined in hapi/base.py) as the underlying HTTP engine.

The Prospects API uses a timeline-based retrieval model where prospects are
organized chronologically by visit time and grouped by organization. Pagination
is handled via a dual-offset system (timeOffset and orgOffset) rather than
traditional page-number pagination.

Public Methods:
    get_prospects: Retrieve prospect timeline with offset pagination.
    get_company: Fetch prospect data for a specific company.
    get_options_for_query: Typeahead search for prospect company names.
    search_prospects: Search prospects by geographic criteria.
    get_hidden_prospects: List prospects hidden from the UI.
    hide_prospect: Hide a prospect from the user interface.
    unhide_prospect: Restore a hidden prospect to the user interface.

Example::

    client = ProspectsClient(api_key='demo')
    prospects = client.get_prospects(limit=20)

"""
from base import BaseClient

PROSPECTS_API_VERSION = 'v1'

class ProspectsClient(BaseClient):
    """Client for the HubSpot Prospects API v1.

    Provides methods to retrieve, search, and manage website visitor
    prospect data through HubSpot's Prospects API. Inherits from
    BaseClient which handles HTTP communication, authentication
    injection, retry logic, and response parsing.

    All endpoints route through the prospects/v1/ subpath, constructed
    via the PROSPECTS_API_VERSION module constant. The API organizes
    prospect data around a timeline model where visitor activity is
    tracked chronologically and grouped by organization.

    Pagination across timeline endpoints uses a dual-offset system:
        - timeOffset: Cursor for chronological position in the timeline.
        - orgOffset: Cursor for organization position within a time window.
    Both offsets must be supplied together for correct pagination behavior.

    Attributes:
        api_key (str): HubSpot API key for authentication, inherited
            from BaseClient.
        options (dict): Client configuration including api_base and
            timeout, inherited from BaseClient.

    Questions, comments, etc: http://docs.hubapi.com/wiki/Discussion_Group.

    """
  
    def _get_path(self, method):
        """Construct the API path for a Prospects API endpoint.

        Overrides BaseClient._get_path to prefix the given method
        name with the prospects API version path segment.

        Args:
            method (str): The API method or resource path to append,
                e.g. 'timeline', 'filters', 'search/city'.

        Returns:
            str: Fully qualified API subpath in the format
                'prospects/v1/{method}'.

        """
        return 'prospects/%s/%s' % (PROSPECTS_API_VERSION, method)

    # Why: [Alternatives Considered] — Prospect retrieval uses a timeline-based
    # model with dual offsets (timeOffset and orgOffset) rather than simple
    # page/offset pagination because prospects are organized chronologically
    # by visit time and grouped by organization, requiring two-dimensional
    # cursor tracking. The 'count' parameter name in the API is mapped from
    # 'limit' to provide a more intuitive caller interface.
    def get_prospects(self, offset=None, orgoffset=None, limit=None):
        """Return prospect timeline data for the current API key.

        Retrieve a paginated list of website visitor prospects organized
        as a chronological timeline. Each prospect element contains
        organizational information such as company name and location.
        Supports dual-offset pagination for traversing large result sets.

        Endpoint Access:
            HTTP Method: GET
            URL: /prospects/v1/timeline
            Auth: API key injected as 'hapikey' query parameter by
                BaseClient._prepare_request_auth.
            Body: None (GET request).
            Response: JSON dict/list containing prospect timeline entries,
                with pagination offsets for subsequent requests.

        Args:
            offset (str or None): Time-based pagination offset from a
                previous response. When provided, orgoffset must also
                be supplied for correct cursor positioning.
            orgoffset (str or None): Organization-based pagination
                offset from a previous response. Used together with
                offset for two-dimensional cursor tracking.
            limit (int or None): Maximum number of results to return,
                sent to the API as the 'count' query parameter.

        Returns:
            dict: Parsed JSON response containing prospect timeline
                data and pagination offset values for subsequent calls.

        Raises:
            HapiError: When the HubSpot API returns a non-2xx status
                code, including authentication and server errors.

        """
        params = {}
        if limit:
            params['count'] = limit

        if offset:
            params['timeOffset'] = offset
            params['orgOffset'] = orgoffset

        return self._call('timeline', params)
        
    def get_company(self, company_slug):
        """Return prospect data for a specific named organization.

        Retrieve detailed prospect information for a single company
        identified by its URL-safe slug. The slug is appended directly
        to the timeline path segment.

        Endpoint Access:
            HTTP Method: GET
            URL: /prospects/v1/timeline/{company_slug}
            Auth: API key injected as 'hapikey' query parameter by
                BaseClient._prepare_request_auth.
            Body: None (GET request).
            Response: JSON dict with company prospect details.

        Args:
            company_slug (str): URL-safe company identifier used as
                the path segment, e.g. 'acme-corp'.

        Returns:
            dict: Parsed JSON response containing prospect data for
                the specified company.

        Raises:
            HapiError: When the HubSpot API returns a non-2xx status
                code, such as 404 if the company is not found.

        """
        return self._call('timeline/%s' % company_slug)

    def get_options_for_query(self, query):
        """Discover prospect companies via typeahead autocomplete search.

        Perform a typeahead search against known prospect company names,
        returning suggestions that match the partial query string. This
        is a discovery endpoint intended to help callers find valid
        search values for use with search_prospects.

        Endpoint Access:
            HTTP Method: GET
            URL: /prospects/v1/typeahead/?q={query}
            Auth: API key injected as 'hapikey' query parameter by
                BaseClient._prepare_request_auth.
            Body: None (GET request).
            Response: JSON list/dict of matching prospect suggestions.

        Args:
            query (str): Partial company name to search for. The API
                returns matching prospect company names suitable for
                use as input to search_prospects.

        Returns:
            list: Parsed JSON response containing matching prospect
                company name suggestions.

        Raises:
            HapiError: When the HubSpot API returns a non-2xx status
                code.

        """
        return self._call('typeahead/', {'q': query})

    # Why: [Future-proofing] — The geographic filter architecture uses a generic
    # search_type parameter ('city', 'region', 'country') rather than dedicated
    # methods per filter type, allowing new geographic search types to be
    # supported without code changes if HubSpot adds them.
    def search_prospects(self, search_type, query, offset=None, orgoffset=None):
        """Search for prospects by geographic criteria.

        Perform a filtered search for prospects by city, region, or
        country. This method is designed to be used with query values
        obtained from get_options_for_query, which provides valid
        search terms via typeahead discovery.

        Supports the same dual-offset pagination model as get_prospects
        for traversing large result sets.

        Endpoint Access:
            HTTP Method: GET
            URL: /prospects/v1/search/{search_type}?q={query}
            Auth: API key injected as 'hapikey' query parameter by
                BaseClient._prepare_request_auth.
            Body: None (GET request).
            Response: JSON dict/list of matching prospects with
                pagination offsets.

        Args:
            search_type (str): Geographic filter category, should be
                one of 'city', 'region', or 'country'.
            query (str): Search value for the given filter type,
                typically obtained from get_options_for_query results.
            offset (str or None): Time-based pagination offset from
                a previous response. Must be provided together with
                orgoffset for correct cursor positioning.
            orgoffset (str or None): Organization-based pagination
                offset from a previous response. Must be provided
                together with offset.

        Returns:
            dict: Parsed JSON response containing matching prospect
                data and pagination offset values.

        Raises:
            HapiError: When the HubSpot API returns a non-2xx status
                code.

        """
        
        params = {'q': query}
        if offset and orgoffset:
            params['orgOffset'] = orgoffset
            params['timeOffset'] = offset
          
        return self._call('search/%s' % search_type, params)
        
    def get_hidden_prospects(self):
        """Return the list of prospects hidden from the user interface.

        Retrieve all prospect filter entries that have been hidden,
        either manually by a user through the HubSpot UI or
        programmatically via the hide_prospect method.

        Endpoint Access:
            HTTP Method: GET
            URL: /prospects/v1/filters
            Auth: API key injected as 'hapikey' query parameter by
                BaseClient._prepare_request_auth.
            Body: None (GET request).
            Response: JSON list/dict of hidden prospect filter entries.

        Returns:
            list: Parsed JSON response containing hidden prospect
                filter records.

        Raises:
            HapiError: When the HubSpot API returns a non-2xx status
                code.

        """
        return self._call('filters')
        
    # Why: [Assumptions Made] — The hide_prospect method uses URL-encoded string
    # formatting ('organization=%s') rather than passing a dict like
    # unhide_prospect does. This inconsistency between hide (string-formatted
    # body) and unhide (dict body) suggests the form-encoded format was
    # required by the API endpoint for POST but the DELETE endpoint accepts
    # dict serialization.
    def hide_prospect(self, company_name):
        """Hide a prospect from the HubSpot user interface.

        Add a filter entry that hides the specified prospect company
        from the HubSpot Prospects UI. The filter can be removed later
        via unhide_prospect to restore visibility.

        Endpoint Access:
            HTTP Method: POST
            URL: /prospects/v1/filters
            Auth: API key injected as 'hapikey' query parameter by
                BaseClient._prepare_request_auth.
            Body: URL-encoded string 'organization={company_name}'
                with Content-Type 'application/x-www-form-urlencoded'.
            Response: JSON confirmation of the created filter.

        Args:
            company_name (str): The organization name of the prospect
                to hide from the user interface.

        Returns:
            dict: Parsed JSON response confirming the prospect filter
                was created.

        Raises:
            HapiError: When the HubSpot API returns a non-2xx status
                code.

        """
        return self._call('filters', data=('organization=%s' % company_name), method="POST", content_type="application/x-www-form-urlencoded")
        
    # Why: [Alternatives Considered] — DELETE with a request body
    # (data={'organization': company_name}) is used rather than encoding the
    # organization in the URL path because the filters endpoint identifies
    # prospects by organization name, not by a unique filter GUID.
    def unhide_prospect(self, company_name):
        """Restore a hidden prospect to the HubSpot user interface.

        Remove the filter entry that hides the specified prospect
        company, making it visible again in the HubSpot Prospects UI.
        This reverses the effect of a previous hide_prospect call.

        Endpoint Access:
            HTTP Method: DELETE
            URL: /prospects/v1/filters
            Auth: API key injected as 'hapikey' query parameter by
                BaseClient._prepare_request_auth.
            Body: JSON-serialized dict {'organization': company_name}.
            Response: JSON confirmation of filter removal.

        Args:
            company_name (str): The organization name of the prospect
                to restore to the user interface.

        Returns:
            dict: Parsed JSON response confirming the prospect filter
                was removed.

        Raises:
            HapiError: When the HubSpot API returns a non-2xx status
                code, such as 404 if no matching filter exists.

        """
        return self._call('filters', data={'organization': company_name}, method="DELETE")
        
