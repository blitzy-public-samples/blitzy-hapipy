"""HubSpot Social Broadcast API v1 client for broadcast and channel management.

Provide CRUD operations for social media broadcasts and channel configuration
through the HubSpot Broadcast API v1. This module contains both the API client
(``BroadcastClient``) and the value-object layer for response deserialization.

Key classes:
    BroadcastClient: API client wrapping broadcast/v1/ endpoints. Inherits
        from ``BaseClient`` in ``hapi/base.py`` which supplies authentication,
        retry logic, and HTTP transport.
    BaseSocialObject: Base value-object providing bidirectional camelCase /
        snake_case field conversion and dict serialization for all social
        API response models.
    Broadcast: Value object representing a single social media broadcast
        message, with constants for remote content types.
    Channel: Value object representing a social media channel (e.g.,
        Twitter, Facebook) through which broadcasts are published.

The value-object pattern with ``BaseSocialObject`` decouples API JSON field
names from Pythonic attribute names, allowing callers to work with snake_case
attributes while the serialization layer transparently handles camelCase
conversion for outbound payloads.

Example::

    client = BroadcastClient(api_key='demo')
    broadcasts = client.get_broadcasts(type='published', limit=10)
    for b in broadcasts:
        print(b.message)
"""
try:
    from hapi.base import BaseClient
except ImportError:
    from base import BaseClient

HUBSPOT_BROADCAST_API_VERSION = '1'


# Why: [Alternatives Considered] — A mutable value object pattern with setattr-based
# deserialization was chosen over immutable namedtuples or dataclasses because the API
# response fields need bidirectional conversion between camelCase (API) and snake_case
# (Python), and the accepted_fields whitelist prevents unexpected API fields from
# polluting the object namespace.
class BaseSocialObject(object):
    """Base class for HubSpot social API value objects.

    Provide bidirectional camelCase/underscore field-name conversion and
    dict serialization/deserialization for social API response models.

    Subclasses must implement ``accepted_fields()`` to return a list of
    camelCase API field names that are permitted during deserialization.
    Fields not in the whitelist are silently discarded, preventing
    unexpected API additions from polluting the object namespace.

    Key methods:
        _camel_case_to_underscores: Convert a camelCase string to snake_case.
        _underscores_to_camel_case: Convert a snake_case string to camelCase.
        to_dict: Serialize instance attributes to a camelCase dict for API payloads.
        from_dict: Deserialize an API response dict into instance attributes
            using the accepted_fields whitelist.
    """

    def _camel_case_to_underscores(self, text):
        """Convert a camelCase string to its snake_case equivalent.

        Walk through each character in *text*, inserting an underscore before
        each uppercase letter that follows a lowercase letter or precedes a
        lowercase letter (to handle acronyms such as ``remoteContentID``
        becoming ``remote_content_i_d``).

        Args:
            text (str): A camelCase-formatted field name from the HubSpot
                API response (e.g., ``'broadcastGuid'``).

        Returns:
            str: The snake_case representation of *text*
                (e.g., ``'broadcast_guid'``).
        """
        result = []
        pos = 0
        while pos < len(text):
            if text[pos].isupper():
                if pos - 1 > 0 and text[pos - 1].islower() or pos - 1 > 0 and pos + 1 < len(text) and text[pos + 1].islower():
                    result.append("_%s" % text[pos].lower())
                else:
                    result.append(text[pos].lower())
            else:
                result.append(text[pos])
            pos += 1
        return "".join(result)

    def _underscores_to_camel_case(self, text):
        """Convert a snake_case string to its camelCase equivalent.

        Walk through each character in *text*, capitalizing the character
        immediately following every underscore and removing the underscore
        itself, producing a camelCase string suitable for HubSpot API
        payloads.

        Args:
            text (str): A snake_case-formatted Python attribute name
                (e.g., ``'broadcast_guid'``).

        Returns:
            str: The camelCase representation of *text*
                (e.g., ``'broadcastGuid'``).
        """
        result = []
        pos = 0
        while pos < len(text):
            if text[pos] == "_" and pos + 1 < len(text):
                result.append("%s" % text[pos + 1].upper())
                pos += 1
            else:
                result.append(text[pos])
            pos += 1
        return "".join(result)

    def to_dict(self):
        """Serialize instance attributes to a camelCase dict for API payloads.

        Iterate over all instance attributes set on this object, convert
        each attribute name from snake_case back to camelCase, and return
        the resulting dict.  The output is suitable for JSON serialization
        and submission to HubSpot API endpoints that expect camelCase keys.

        Returns:
            dict: A mapping of camelCase field names to their current
                attribute values on this instance.
        """
        dict_self = {}
        for key in vars(self):
            dict_self[self._underscores_to_camel_case(key)] = getattr(self, key)
        return dict_self

    def from_dict(self, data):
        """Deserialize an API response dict into instance attributes.

        Filter *data* through the ``accepted_fields()`` whitelist defined
        by the concrete subclass, convert each accepted camelCase key to
        its snake_case equivalent, and set the converted name as an
        attribute on this instance.  Keys not present in the whitelist are
        silently ignored.

        Args:
            data (dict): A dictionary of camelCase field names and values
                from a HubSpot API JSON response.
        """
        # Why: [Assumptions Made] — Uses setattr-based deserialization rather than dict
        # unpacking because each field must be individually converted from camelCase to
        # snake_case, and only fields in the accepted_fields whitelist should be set on
        # the object.  Assumes the API may return additional fields not in the whitelist
        # that should be silently ignored.
        accepted_fields = self.accepted_fields()
        for key in data:
            if key in accepted_fields:
                setattr(self, self._camel_case_to_underscores(key), data[key])


class Broadcast(BaseSocialObject):
    """Value object representing a HubSpot social media broadcast message.

    Wrap a single broadcast record returned by the Broadcast API v1 and
    expose its fields as snake_case Python attributes.  Deserialization is
    handled by the ``BaseSocialObject.from_dict`` pipeline, which filters
    the API response through ``accepted_fields()``.

    Class constants for ``remoteContentType`` values:

    Attributes:
        COS_LP (str): ``'coslp'`` — COS landing-page content source.
        COS_BLOG (str): ``'cosblog'`` — COS blog-post content source.
        LEGACY_LP (str): ``'cmslp'`` — Legacy (CMS) landing-page source.
        LEGACY_BLOG (str): ``'cmsblog'`` — Legacy (CMS) blog-post source.

    The accepted_fields whitelist includes identifiers (broadcastGuid,
    channelGuid, groupGuid, linkGuid, campaignGuid), content fields
    (message, content, messageUrl), scheduling/status fields (status,
    triggerAt, createdAt, finishedAt), engagement metrics (clicks,
    interactions, interactionCounts), and metadata (portalId, createdBy,
    updatedBy, clientTag, remoteContentId, remoteContentType, channel).
    """

    # Constants for remote content type
    COS_LP = "coslp"
    COS_BLOG = "cosblog"
    LEGACY_LP = "cmslp"
    LEGACY_BLOG = "cmsblog"

    def __init__(self, broadcast_data):
        """Construct a Broadcast from an API response dict.

        Delegate to ``data_parse`` which in turn calls the
        ``BaseSocialObject.from_dict`` pipeline to convert camelCase
        API keys into snake_case attributes filtered by the
        ``accepted_fields`` whitelist.

        Args:
            broadcast_data (dict): A single broadcast record from the
                HubSpot Broadcast API response JSON.
        """
        self.data_parse(broadcast_data)

    def accepted_fields(self):
        """Return the whitelist of camelCase API field names accepted during deserialization.

        Only fields listed here will be converted to snake_case attributes
        when ``from_dict`` processes an API response.  Any additional keys
        present in the response dict are silently discarded.

        Returns:
            list: A list of str camelCase field names corresponding to
                the Broadcast API response schema.
        """
        return [
            'broadcastGuid',
            'campaignGuid',
            'channel',
            'channelGuid',
            'clicks',
            'clientTag',
            'content',
            'createdAt',
            'createdBy',
            'finishedAt',
            'groupGuid',
            'interactions',
            'interactionCounts',
            'linkGuid',
            'message',
            'messageUrl',
            'portalId',
            'remoteContentId',
            'remoteContentType',
            'status',
            'triggerAt',
            'updatedBy'
        ]

    def data_parse(self, broadcast_data):
        """Delegate to ``from_dict`` for field extraction and attribute assignment.

        Provide a convenience entry point that forwards *broadcast_data*
        to the ``BaseSocialObject.from_dict`` deserialization pipeline.

        Args:
            broadcast_data (dict): A single broadcast record dict from
                the HubSpot Broadcast API response.
        """
        self.from_dict(broadcast_data)


class Channel(BaseSocialObject):
    """Value object representing a social media channel in the broadcast system.

    Wrap a single channel record (e.g., a Twitter account, Facebook page)
    returned by the Broadcast API v1 and expose its fields as snake_case
    Python attributes.  Channels are the publishing targets to which
    ``Broadcast`` messages are dispatched.

    Accepted fields include identifiers (channelGuid, accountGuid),
    descriptive metadata (account, type, name), configuration
    (dataMap, settings), and timestamps (createdAt).
    """

    def __init__(self, channel_data):
        """Construct a Channel from an API response dict.

        Delegate to ``data_parse`` which forwards to the
        ``BaseSocialObject.from_dict`` pipeline for camelCase-to-snake_case
        conversion filtered by ``accepted_fields``.

        Args:
            channel_data (dict): A single channel record from the
                HubSpot Broadcast API response JSON.
        """
        self.data_parse(channel_data)

    def accepted_fields(self):
        """Return the whitelist of camelCase API field names accepted during deserialization.

        Only the fields listed here will be converted to snake_case
        attributes when ``from_dict`` processes an API response for
        this channel.

        Returns:
            list: A list of str camelCase field names corresponding to
                the Channel API response schema.
        """
        return ['channelGuid', 'accountGuid', 'account',
            'type', 'name', 'dataMap', 'createdAt', 'settings']

    def data_parse(self, channel_data):
        """Delegate to ``from_dict`` for field extraction and attribute assignment.

        Provide a convenience entry point that forwards *channel_data*
        to the ``BaseSocialObject.from_dict`` deserialization pipeline.

        Args:
            channel_data (dict): A single channel record dict from
                the HubSpot Broadcast API response.
        """
        self.from_dict(channel_data)


class BroadcastClient(BaseClient):
    """Client for HubSpot Broadcast API v1 providing CRUD for social media broadcasts and channel management.

    Inherit from ``BaseClient`` (``hapi/base.py``) which supplies
    authentication injection, retry logic with exponential back-off,
    and HTTP transport via the ``requests`` session layer.

    Endpoint access overview:
        All endpoints are routed through the ``broadcast/v1/`` subpath.
        URL construction is handled by ``_get_path`` which prepends the
        versioned broadcast prefix to every method-specific subpath.
        Authentication is injected automatically by
        ``BaseClient._prepare_request_auth`` (API key as query parameter
        or OAuth access token).

    Typical usage::

        client = BroadcastClient(api_key='demo')
        broadcasts = client.get_broadcasts(type='published')
        channel = client.get_channel(channel_guid='abc-123')
    """

    def _get_path(self, method):
        """Build the fully qualified Broadcast API path for a given subpath.

        Prepend the versioned broadcast API prefix (``broadcast/v1/``) to
        the supplied *method* subpath, producing a path suitable for
        ``BaseClient._prepare_request``.

        Args:
            method (str): The endpoint-specific subpath (e.g.,
                ``'broadcasts'``, ``'channels/current'``).

        Returns:
            str: The complete API path such as
                ``'broadcast/v1/broadcasts'``.
        """
        return 'broadcast/v%s/%s' % (HUBSPOT_BROADCAST_API_VERSION, method)

    def get_broadcast(self, broadcast_guid, **kwargs):
        """Retrieve a single broadcast by its unique identifier.

        Endpoint Access:
            HTTP Method: GET
            URL: broadcast/v1/broadcasts/{broadcast_guid}
            Auth: API key or OAuth token injected by BaseClient.
            Body: None.
            Response: JSON dict representing a single broadcast record,
                wrapped in a ``Broadcast`` value object.

        Args:
            broadcast_guid (str): The unique identifier of the broadcast
                to retrieve.
            **kwargs: Additional query parameters forwarded to the API
                request (e.g., custom filters).

        Returns:
            Broadcast: A ``Broadcast`` value object populated with the
                deserialized API response fields.

        Raises:
            HapiError: When the API returns a non-2xx status code.
        """
        params = kwargs
        broadcast = self._call('broadcasts/%s' % broadcast_guid,
            params=params, content_type='application/json')
        return Broadcast(broadcast)

    def get_broadcasts(self, type="", page=None,
            remote_content_id=None, limit=None, **kwargs):
        """Retrieve broadcasts with optional filtering, paging, and limits.

        When *remote_content_id* is provided, delegation is forwarded to
        ``get_broadcasts_by_remote`` and all other parameters are ignored.
        Otherwise, a standard broadcast listing request is made with
        optional type filtering, pagination, and client-side result
        limiting.

        Endpoint Access:
            HTTP Method: GET
            URL: broadcast/v1/broadcasts
            Auth: API key or OAuth token injected by BaseClient.
            Query Params: type (str), page (int) — sent when provided.
                Additional kwargs are merged into query params.
            Body: None.
            Response: JSON list of broadcast record dicts, each wrapped
                in a ``Broadcast`` value object.

        Args:
            type (str): Status filter — ``'scheduled'``, ``'published'``,
                or ``'failed'``.  Defaults to ``""`` (no filter).
            page (int or None): Page number for server-side pagination.
                Omitted from the request when ``None``.
            remote_content_id (str or None): When provided, delegates to
                ``get_broadcasts_by_remote`` instead of the standard
                listing endpoint.
            limit (int or None): Client-side cap on the number of
                ``Broadcast`` objects returned.  Applied after the full
                result set is retrieved from the API.
            **kwargs: Additional query parameters merged into the request.

        Returns:
            list: A list of ``Broadcast`` value objects deserialized from
                the API response.

        Raises:
            HapiError: When the API returns a non-2xx status code.
        """
        if remote_content_id:
            return self.get_broadcasts_by_remote(remote_content_id)

        params = {'type': type}
        if page:
            params['page'] = page

        params.update(kwargs)

        result = self._call('broadcasts', params=params,
            content_type='application/json')
        broadcasts = [Broadcast(b) for b in result]

        if limit:
            return broadcasts[:limit]
        return broadcasts

    def create_broadcast(self, broadcast):
        """Create a new social media broadcast message.

        Accept either a ``Broadcast`` value object or a raw dict.  When a
        ``Broadcast`` is supplied, ``to_dict()`` is called to serialize it
        into the camelCase format expected by the API.  When a plain dict
        is supplied, it is sent as-is, allowing callers who already have
        correctly formatted data to skip the value-object layer.

        Endpoint Access:
            HTTP Method: POST
            URL: broadcast/v1/broadcasts
            Auth: API key or OAuth token injected by BaseClient.
            Body: JSON-encoded dict of broadcast fields.
            Response: JSON dict of the created broadcast record.

        Args:
            broadcast (Broadcast or dict): The broadcast payload.  If a
                ``Broadcast`` instance, ``to_dict()`` is used to produce
                the request body.  If a ``dict``, it is submitted directly.

        Returns:
            dict: The raw API response dict for the newly created
                broadcast record.

        Raises:
            HapiError: When the API returns a non-2xx status code.
        """
        # Why: [Trade-offs] — Accepts both dict and Broadcast object via isinstance check
        # rather than requiring a single type.  This provides flexibility for callers who
        # may have raw dicts from other sources but adds a type-checking branch.
        if not isinstance(broadcast, dict):
            return self._call('broadcasts', data=broadcast.to_dict(),
                method='POST', content_type='application/json')
        else:
            return self._call('broadcasts', data=broadcast,
                method='POST', content_type='application/json')

    def cancel_broadcast(self, broadcast_guid):
        """Cancel a scheduled broadcast by updating its status to CANCELED.

        Rather than deleting the broadcast record, this method issues a
        POST to the broadcast's update endpoint with a status payload of
        ``'CANCELED'``, preserving the broadcast in HubSpot's history for
        audit purposes.

        Endpoint Access:
            HTTP Method: POST
            URL: broadcast/v1/broadcasts/{broadcast_guid}/update
            Auth: API key or OAuth token injected by BaseClient.
            Body: JSON ``{"status": "CANCELED"}``.
            Response: JSON dict of the updated broadcast record.

        Args:
            broadcast_guid (str): The unique identifier of the broadcast
                to cancel.

        Returns:
            dict: The raw API response dict reflecting the canceled
                broadcast state.

        Raises:
            HapiError: When the API returns a non-2xx status code.
        """
        # Why: [Alternatives Considered] — Cancel is implemented as a POST status update
        # to 'CANCELED' rather than a DELETE because the HubSpot API preserves broadcast
        # history; deleting would remove the record entirely whereas status change
        # maintains audit trail.
        subpath = 'broadcasts/%s/update' % broadcast_guid
        broadcast = {'status': 'CANCELED'}
        bcast_dict = self._call(subpath, method='POST', data=broadcast,
            content_type='application/json')
        return bcast_dict

    def get_channel(self, channel_guid):
        """Retrieve a single channel by its unique identifier.

        Endpoint Access:
            HTTP Method: GET
            URL: broadcast/v1/channels/{channel_guid}
            Auth: API key or OAuth token injected by BaseClient.
            Body: None.
            Response: JSON dict representing a single channel record,
                wrapped in a ``Channel`` value object.

        Args:
            channel_guid (str): The unique identifier of the social
                media channel to retrieve.

        Returns:
            Channel: A ``Channel`` value object populated with the
                deserialized API response fields.

        Raises:
            HapiError: When the API returns a non-2xx status code.
        """
        channel = self._call('channels/%s' % channel_guid,
            content_type='application/json')
        return Channel(channel)

    def get_channels(self, current=True, publish_only=False, settings=False):
        """Retrieve social media channels with configurable endpoint selection.

        Build the correct channel endpoint path based on the combination
        of *current* and *publish_only* flags, then fetch the channel list
        from the API.  Four endpoint variations are supported:

        +--------------+--------------+-------------------------------------------+
        | current      | publish_only | Endpoint                                  |
        +==============+==============+===========================================+
        | ``True``     | ``True``     | channels/setting/publish/current          |
        +--------------+--------------+-------------------------------------------+
        | ``False``    | ``True``     | channels/setting/publish                  |
        +--------------+--------------+-------------------------------------------+
        | ``True``     | ``False``    | channels/current                          |
        +--------------+--------------+-------------------------------------------+
        | ``False``    | ``False``    | channels                                  |
        +--------------+--------------+-------------------------------------------+

        Endpoint Access:
            HTTP Method: GET
            URL: broadcast/v1/channels/[setting/publish/][current]
                (varies by flag combination as shown above).
            Auth: API key or OAuth token injected by BaseClient.
            Query Params: settings (bool) — when ``True`` the API makes
                extra queries to include per-channel settings.
            Body: None.
            Response: JSON list of channel record dicts, each wrapped
                in a ``Channel`` value object.

        Args:
            current (bool): When ``True`` (default), return only channels
                currently configured for the account.  When ``False``,
                return all channels the user has ever published to.
            publish_only (bool): When ``True``, restrict results to
                channels that are currently publishable.  Defaults to
                ``False``.
            settings (bool): When ``True``, the API performs additional
                queries to populate per-channel settings in the response.
                Defaults to ``False``.

        Returns:
            list: A list of ``Channel`` value objects deserialized from
                the API response.

        Raises:
            HapiError: When the API returns a non-2xx status code.
        """
        if publish_only:
            if current:
                endpoint = 'channels/setting/publish/current'
            else:
                endpoint = 'channels/setting/publish'
        else:
            if current:
                endpoint = 'channels/current'
            else:
                endpoint = 'channels'

        result = self._call(endpoint, content_type='application/json', params=dict(settings=settings))
        return [Channel(c) for c in result]
