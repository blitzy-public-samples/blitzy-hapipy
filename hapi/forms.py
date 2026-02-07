"""HubSpot Form Submission client for posting data to HubSpot forms.

This module provides the FormSubmissionClient, a specialized client for
submitting form data to HubSpot's Form Submission API. Unlike all other
domain clients in the hapipy library, this client overrides the default
api_base from 'api.hubapi.com' to 'forms.hubspot.com' and transmits
payloads as URL-encoded form data (application/x-www-form-urlencoded)
rather than JSON. This architectural deviation mirrors how browsers
natively submit HTML forms to HubSpot.

The client inherits its HTTP engine, authentication injection, retry
logic, and connection management from BaseClient in hapi/base.py.

Usage example::

    client = FormSubmissionClient(api_key='demo')
    client.submit_form('portal_id', 'form_guid', {'email': 'a@b.com'})
"""
import logging
logger = logging.getLogger(__name__)

from base import BaseClient


class FormSubmissionClient(BaseClient):
    """Client for submitting data to HubSpot forms via the Forms API.

    FormSubmissionClient is the only domain client in hapipy that targets
    a different host than the standard HubSpot REST API. While all other
    clients (BlogClient, LeadsClient, KeywordsClient, etc.) communicate
    with 'api.hubapi.com', this client routes requests to
    'forms.hubspot.com' — HubSpot's dedicated form ingestion endpoint.

    Additionally, this client uses URL-encoded payloads
    (application/x-www-form-urlencoded) instead of JSON, matching the
    encoding that a browser would use when submitting an HTML form
    directly to HubSpot.

    Endpoint Access Overview:
        All requests route through:
        POST https://forms.hubspot.com/uploads/form/v2/{portal_id}/{form_guid}

    Attributes:
        options (dict): Inherited from BaseClient. The 'api_base' key is
            overridden to 'forms.hubspot.com' during initialization.

    Example::

        client = FormSubmissionClient(api_key='demo')
        response = client.submit_form(
            portal_id='12345',
            form_guid='abc-def-ghi',
            data={'email': 'user@example.com', 'firstname': 'Jane'}
        )
    """

    def __init__(self, *args, **kwargs):
        """Initialize the FormSubmissionClient with a forms-specific host.

        Invoke the parent BaseClient constructor to set up authentication,
        connection type, retry configuration, and mixin injection, then
        override the api_base option to redirect all HTTP traffic to
        HubSpot's form submission domain.

        This is the only client in the hapipy library that mutates
        api_base after BaseClient.__init__ completes.

        Args:
            *args: Positional arguments forwarded to
                BaseClient.__init__ (typically api_key).
            **kwargs: Keyword arguments forwarded to
                BaseClient.__init__ (e.g., timeout, access_token,
                refresh_token, client_id, mixins).
        """
        super(FormSubmissionClient, self).__init__(*args, **kwargs)
        # Why: [Alternatives Considered] — The FormSubmissionClient overrides
        # api_base to 'forms.hubspot.com' rather than using the default
        # 'api.hubapi.com' because HubSpot's form submission endpoints are
        # hosted on a separate domain from the REST API. An alternative would
        # be to pass the host as a constructor parameter, but hardcoding it
        # here encapsulates this domain-specific routing and prevents callers
        # from needing to know about the host difference.
        self.options['api_base'] = 'forms.hubspot.com'

    def _get_path(self, subpath):
        """Construct the URL path for a form submission request.

        Build the form submission endpoint path by prepending the
        static '/uploads/form/v2/' prefix to the given subpath. The
        subpath is expected to contain '{portal_id}/{form_guid}'
        already concatenated by the calling method.

        Args:
            subpath (str): The portal and form identifier segment,
                formatted as '{portal_id}/{form_guid}'.

        Returns:
            str: The complete URL path for the form submission
                endpoint, e.g. '/uploads/form/v2/12345/abc-def'.
        """
        return '/uploads/form/v2/%s' % subpath

    def submit_form(self, portal_id, form_guid, data, **options):
        """Submit form data to a specific HubSpot form.

        Post URL-encoded form field data to the HubSpot Form Submission
        API for a given portal and form. This method constructs the full
        submission URL from portal_id and form_guid, forces the content
        type to application/x-www-form-urlencoded, and bypasses the
        standard subpath-based URL construction by providing an explicit
        url keyword argument to BaseClient._call.

        Endpoint Access:
            HTTP Method: POST
            URL: https://forms.hubspot.com/uploads/form/v2/{portal_id}/{form_guid}
            Auth: API key injected as query parameter by BaseClient, or
                OAuth access token depending on client configuration.
            Body: URL-encoded form data
                (application/x-www-form-urlencoded), NOT JSON.
            Response: Parsed response from HubSpot confirming the
                form submission.

        Args:
            portal_id (str): The HubSpot portal (account) identifier
                that owns the target form.
            form_guid (str): The unique identifier (GUID) of the
                HubSpot form to submit data to.
            data (dict or str): The form field data to submit. If a
                dict, keys are field names and values are field values.
                If a string, it should already be URL-encoded.
            **options: Additional keyword arguments forwarded to
                BaseClient._call (e.g., timeout, number_retries).

        Returns:
            dict or str: The parsed response body from the HubSpot
                Form Submission API, processed through
                BaseClient._digest_result.

        Raises:
            HapiError: When the HubSpot API returns a non-2xx HTTP
                status code (see hapi/error.py for the full error
                hierarchy including HapiBadRequest, HapiNotFound,
                HapiUnauthorized, and HapiServerError).
        """
        subpath = '%s/%s' % (portal_id, form_guid)
        # Why: [Assumptions Made] — URL-encoded form data
        # (application/x-www-form-urlencoded) is used instead of JSON because
        # the HubSpot form submission API expects standard HTML form encoding.
        # This matches browser form submission behavior and allows the API to
        # accept the same format as direct HTML form posts.
        opts = {'content_type': 'application/x-www-form-urlencoded'}
        options.update(opts)
        # Why: [Alternatives Considered] — The submit_form method bypasses
        # the normal _call(subpath) pattern by passing subpath=None and an
        # explicit url= keyword because the form submission path includes
        # the portal_id and form_guid as path segments rather than query
        # parameters, requiring custom URL construction via _get_path.
        return self._call(
            subpath=None,
            url=self._get_path(subpath),
            method='POST',
            data=data,
            **options
        )
