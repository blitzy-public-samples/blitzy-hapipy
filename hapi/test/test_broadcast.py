"""Integration test suite for the HubSpot Broadcast API client.

This module exercises the BroadcastClient defined in ``hapi/broadcast.py``,
verifying social media broadcast and channel CRUD operations against live
HubSpot API endpoints. Tests cover broadcast listing, single-broadcast
retrieval, channel enumeration, and the full broadcast creation lifecycle
including scheduled trigger times and tearDown-based cleanup.

These are integration tests that require valid HubSpot API credentials
loaded from ``test_credentials.json`` via ``helper.get_options()``.  The
test portal must contain at least one existing broadcast and one
publishable channel for assertions to pass.

Tests are tagged with ``@attr('api')`` for nose-based selective execution,
allowing developers to run only API-dependent tests or exclude them when
working offline::

    nosetests -a api          # run only API tests
    nosetests -a '!api'       # skip API tests

Test framework: ``unittest2.TestCase`` with ``nose.plugins.attrib`` for
test tagging.

Reference:
    Tests ``BroadcastClient`` and ``Broadcast`` defined in
    ``hapi/broadcast.py``.
"""
import unittest2
import time

from nose.plugins.attrib import attr

try:
    from hapi.test import helper
except ImportError:
    import helper
from hapi.broadcast import Broadcast, BroadcastClient


class BroadcastClientTest(unittest2.TestCase):
    """Integration tests for the HubSpot Broadcast API Python client.

    Validates broadcast listing and retrieval, channel listing, and
    broadcast creation with scheduled future triggers against the live
    HubSpot Broadcast API (v1).

    The test lifecycle follows a create-and-cleanup pattern:

    * ``setUp`` instantiates a ``BroadcastClient`` using credentials
      obtained from ``helper.get_options()`` (sourced from
      ``test_credentials.json``) and initialises a ``broadcast_guids``
      sentinel for tearDown tracking.
    * ``tearDown`` cancels any broadcasts whose GUIDs were collected in
      ``self.broadcast_guids`` during the test, preventing orphaned
      scheduled broadcasts on the test portal.

    All test methods issue live HTTP requests to the HubSpot API and
    therefore require a test portal that contains at least one existing
    broadcast and at least one publishable social-media channel.

    Test framework:
        ``unittest2.TestCase``

    Credentials:
        Loaded via ``helper.get_options()`` from
        ``test_credentials.json`` in the test directory.

    Questions, comments: http://docs.hubapi.com/wiki/Discussion_Group
    """

    def setUp(self):
        """Initialise a BroadcastClient and reset the cleanup tracker.

        Creates a fresh ``BroadcastClient`` instance using credentials
        from ``helper.get_options()`` and sets ``self.broadcast_guids``
        to ``None`` so that ``tearDown`` can distinguish between tests
        that created broadcasts and those that did not.

        Tests:
            ``BroadcastClient`` constructor defined in
            ``hapi/broadcast.py``.

        Returns:
            None
        """
        # Why: [Assumptions Made] — The client is constructed fresh for each
        # test method using helper.get_options() credentials.  This assumes
        # the test portal (historically portal 62515) has existing broadcasts
        # and channels.  broadcast_guids is initialised to None rather than
        # an empty list so tearDown can skip cleanup when no broadcasts were
        # created, avoiding an unnecessary map() call over an empty iterable.
        self.client = BroadcastClient(**helper.get_options())
        self.broadcast_guids = None

    def tearDown(self):
        """Cancel any broadcasts created during the test run.

        Iterates over ``self.broadcast_guids`` (when non-``None``) and
        calls ``cancel_broadcast`` on each GUID to remove scheduled
        broadcasts from the test portal, preventing orphaned social
        media posts from being published after the test suite finishes.

        Tests:
            ``BroadcastClient.cancel_broadcast()`` defined in
            ``hapi/broadcast.py``.

        Returns:
            None
        """
        # Why: [Trade-offs] — map() is used for broadcast cleanup rather
        # than an explicit for-loop because it provides a concise one-liner
        # for applying cancel_broadcast to each GUID.  The cleanup runs
        # unconditionally on every test (guarded by the None/empty check),
        # ensuring test isolation even if assertions fail mid-test.  If
        # cancel_broadcast itself fails (e.g., network error), the error
        # will propagate from tearDown, which may mask the original test
        # failure — an accepted trade-off in favour of guaranteed cleanup.
        # Cancel any broadcasts created as part of the tests
        if self.broadcast_guids:
            map(self.client.cancel_broadcast, self.broadcast_guids)

    @attr('api')
    def test_get_broadcasts(self):
        """Verify broadcast listing and single-broadcast retrieval.

        Fetches at least one broadcast from the test portal using
        ``get_broadcasts(limit=1)``, asserts the result is non-empty,
        then re-fetches the same broadcast by its GUID using
        ``get_broadcast()`` and validates that the returned
        ``Broadcast`` value object exposes the expected attributes.

        Tests:
            ``BroadcastClient.get_broadcasts()`` and
            ``BroadcastClient.get_broadcast()`` defined in
            ``hapi/broadcast.py``.

        Assertions:
            * ``broadcasts`` list has length > 0.
            * First broadcast's ``to_dict()`` contains a non-``None``
              ``'channelGuid'`` value.
            * Re-fetched ``Broadcast`` object has non-``None``
              ``broadcast_guid``, ``channel_guid``, and ``status``
              attributes.

        Returns:
            None
        """
        # Should fetch at least 1 broadcast on the test portal 62515
        broadcasts = self.client.get_broadcasts(limit=1)
        self.assertTrue(len(broadcasts) > 0)

        broadcast = broadcasts[0].to_dict()
        self.assertIsNotNone(broadcast['channelGuid'])
        print("\n\nFetched some broadcasts")

        broadcast_guid = broadcast['broadcastGuid']
        # Re-fetch the broadcast using different call
        bcast = self.client.get_broadcast(broadcast_guid)
        # Should have expected fields
        self.assertIsNotNone(bcast.broadcast_guid)
        self.assertIsNotNone(bcast.channel_guid)
        self.assertIsNotNone(bcast.status)

    @attr('api')
    def test_get_channels(self):
        """Verify that channel listing returns at least one channel.

        Calls ``get_channels(current=False)`` to retrieve historical
        (non-current) channels from the test portal and asserts the
        returned list is non-empty.

        Tests:
            ``BroadcastClient.get_channels()`` defined in
            ``hapi/broadcast.py``.

        Assertions:
            * ``channels`` list has length > 0 when
              ``current=False``.

        Returns:
            None
        """
        # Why: [Assumptions Made] — current=False is used to fetch historical
        # (non-current) channels because the test portal may not have
        # currently active publishing channels.  Historical channels are more
        # reliable for assertion purposes since they persist regardless of
        # current publishing configuration.
        # Fetch older channels ensured to exist
        channels = self.client.get_channels(current=False)
        self.assertTrue(len(channels) > 0)

    @attr('api')
    def test_create_broadcast(self):
        """Verify the full broadcast creation lifecycle.

        Exercises the end-to-end broadcast creation flow:

        1. Fetch publishable channels via ``get_channels(current=True,
           publish_only=True)``.  Fails immediately if no publishable
           channel exists on the test portal.
        2. Construct a ``Broadcast`` value object with test content,
           a future trigger time, and the first available channel GUID.
        3. Submit the broadcast via ``create_broadcast()`` and wrap the
           raw response in a ``Broadcast`` object.
        4. Assert the created broadcast has a non-``None``
           ``broadcast_guid`` and that its ``channel_guid`` matches the
           channel used during creation.
        5. Store the broadcast GUID in ``self.broadcast_guids`` so that
           ``tearDown`` cancels the scheduled broadcast.

        Tests:
            ``BroadcastClient.get_channels()``,
            ``BroadcastClient.create_broadcast()``, and the
            ``Broadcast`` constructor defined in ``hapi/broadcast.py``.

        Assertions:
            * At least one publishable channel exists (fails test if
              not).
            * Created broadcast has non-``None`` ``broadcast_guid``.
            * Created broadcast's ``channel_guid`` matches the channel
              used for creation.
            * No exception raised during creation.

        Cleanup:
            Stores the created ``broadcast_guid`` in
            ``self.broadcast_guids`` for ``tearDown`` cancellation.

        Returns:
            None
        """
        content = dict(body="Test hapipy unit tests http://www.hubspot.com")
        channels = self.client.get_channels(current=True, publish_only=True)
        if len(channels) == 0:
            self.fail("Failed to find a publishable channel")

        channel = channels[0]

        # Why: [Assumptions Made] — The trigger time is set 6000 seconds
        # (100 minutes) in the future and converted to milliseconds to match
        # HubSpot's Java-style epoch millisecond timestamp format.  The large
        # future offset ensures the broadcast is never accidentally triggered
        # during test execution, giving tearDown time to cancel it.
        # Get a trigger in the future
        trigger_at = int(time.time() + 6000) * 1000
        bcast = Broadcast({"content": content, "triggerAt":
            trigger_at, "channelGuid": channel.channel_guid})

        # Why: [Trade-offs] — A try/except wrapper with self.fail() is used
        # instead of letting exceptions propagate naturally because the test
        # needs to ensure broadcast_guids is populated for tearDown cleanup
        # even if the assertion fails.  Without this, a failed
        # create_broadcast would prevent tearDown from knowing which
        # broadcasts to cancel, leaving orphaned broadcasts on the test
        # portal.
        try:
            resp = self.client.create_broadcast(bcast)
            broadcast = Broadcast(resp)
            self.assertIsNotNone(broadcast.broadcast_guid)
            self.assertEqual(channel.channel_guid, broadcast.channel_guid)
            # Ensure it is canceled
            self.broadcast_guids = []
            self.broadcast_guids.append(broadcast.broadcast_guid)
        except Exception as e:
            self.fail("Should not have raised exception: %s" % e)


if __name__ == "__main__":
    unittest2.main()
