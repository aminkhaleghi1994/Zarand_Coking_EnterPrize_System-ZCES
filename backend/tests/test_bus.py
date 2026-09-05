import asyncio

from app.common.bus import BusMessage, NotificationBus, encode_sse


def test_publish_reaches_subscriber_via_running_loop() -> None:
    bus = NotificationBus()
    received: list[BusMessage] = []

    async def scenario() -> None:
        loop = asyncio.get_running_loop()
        bus.attach_loop(loop)
        queue = bus.subscribe("user-1")
        await asyncio.sleep(0)  # let attach_loop settle
        bus.publish_threadsafe("user-1", {"id": "n1"})
        message = await bus.wait_for_message(queue, timeout=2.0)
        assert message is not None
        received.append(message)

    asyncio.run(scenario())
    assert received[0].user_id == "user-1"
    assert received[0].payload == {"id": "n1"}


def test_subscriber_filters_by_user() -> None:
    bus = NotificationBus()

    async def scenario() -> None:
        loop = asyncio.get_running_loop()
        bus.attach_loop(loop)
        queue = bus.subscribe("user-a")
        bus.publish_threadsafe("user-b", {"id": "n2"})
        # nothing for user-a within the window
        message = await bus.wait_for_message(queue, timeout=0.3)
        assert message is None
        bus.publish_threadsafe("user-a", {"id": "n3"})
        message = await bus.wait_for_message(queue, timeout=2.0)
        assert message is not None and message.payload["id"] == "n3"

    asyncio.run(scenario())


def test_unsubscribe_stops_delivery() -> None:
    bus = NotificationBus()

    async def scenario() -> None:
        loop = asyncio.get_running_loop()
        bus.attach_loop(loop)
        queue = bus.subscribe("user-c")
        bus.unsubscribe("user-c", queue)
        assert bus.subscriber_count("user-c") == 0
        bus.publish_threadsafe("user-c", {"id": "n4"})
        message = await bus.wait_for_message(queue, timeout=0.3)
        assert message is None

    asyncio.run(scenario())


def test_publish_without_loop_is_silent() -> None:
    bus = NotificationBus()  # never attached
    bus.publish_threadsafe("user-x", {"id": "n5"})  # must not raise


def test_encode_sse_frame_shape() -> None:
    frame = encode_sse("notification", {"id": "n6", "event_type": "LoanRequestActivated"})
    assert frame.startswith("event: notification\n")
    assert '"id": "n6"' in frame
    assert frame.endswith("\n\n")
