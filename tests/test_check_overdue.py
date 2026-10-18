import json
from decimal import Decimal

import pytest

PAST = '2000-01-01T00:00:00'
FUTURE = '2099-01-01T00:00:00'


class FakeSNS:
    """Stands in for the real SNS and remembers every alert it was asked to send."""
    def __init__(self):
        self.sent = []

    def publish(self, **kwargs):
        self.sent.append(kwargs)


@pytest.fixture
def overdue(load):
    module = load('checkOverdueTrips')
    module.sns = FakeSNS()
    return module


def run(module):
    return json.loads(module.lambda_handler({}, None)['body'])


def status_of(table, trip_id):
    return table.get_item(Key={'tripId': trip_id})['Item']['status']


def test_a_late_trip_gets_an_alert_and_is_marked_alert_sent(overdue, add_trip, table):
    add_trip('late', expected=PAST)
    result = run(overdue)

    assert result['overdueCount'] == 1
    assert len(overdue.sns.sent) == 1
    assert overdue.sns.sent[0]['Subject'] == 'TripPulse Safety Alert'
    assert 'Nhlanhla has not checked in' in overdue.sns.sent[0]['Message']
    assert status_of(table, 'late') == 'alert_sent'


def test_a_trip_that_is_not_late_yet_is_left_alone(overdue, add_trip, table):
    add_trip('fine', expected=FUTURE)
    result = run(overdue)

    assert result['overdueCount'] == 0
    assert overdue.sns.sent == []
    assert status_of(table, 'fine') == 'in_progress'


def test_a_trip_that_already_arrived_is_ignored_even_if_its_time_passed(overdue, add_trip):
    add_trip('safe', status='arrived', expected=PAST)
    assert run(overdue)['overdueCount'] == 0
    assert overdue.sns.sent == []


def test_the_same_trip_is_never_alerted_twice(overdue, add_trip):
    add_trip('late', expected=PAST)
    run(overdue)
    run(overdue)                                  # the timer fires again 5 minutes later
    assert len(overdue.sns.sent) == 1


def test_only_the_late_trips_are_alerted(overdue, add_trip, table):
    add_trip('late-1', expected=PAST)
    add_trip('late-2', expected=PAST)
    add_trip('fine', expected=FUTURE)
    result = run(overdue)

    assert result['overdueCount'] == 2
    assert len(overdue.sns.sent) == 2
    assert status_of(table, 'fine') == 'in_progress'


def test_the_alert_includes_a_map_link_when_a_location_was_shared(overdue, add_trip):
    add_trip('late', expected=PAST, lastLocation={
        'lat': Decimal('-26.2041'), 'lng': Decimal('28.0473'),
        'accuracy': Decimal('10'), 'at': '2026-10-17T09:00:00',
    })
    run(overdue)

    message = overdue.sns.sent[0]['Message']
    assert 'https://www.google.com/maps?q=-26.2041,28.0473' in message
    assert 'Location updated at: 2026-10-17T09:00:00' in message


def test_the_alert_says_so_when_no_location_was_shared(overdue, add_trip):
    add_trip('late', expected=PAST)
    run(overdue)
    assert 'No location was shared for this trip.' in overdue.sns.sent[0]['Message']