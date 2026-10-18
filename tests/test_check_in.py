import json
from decimal import Decimal


def check_in(module, trip_id):
    return module.lambda_handler({'pathParameters': {'tripId': trip_id}}, None)


def test_check_in_marks_the_trip_as_arrived(load, add_trip, table):
    add_trip('trip-1')
    response = check_in(load('checkIn'), 'trip-1')

    assert response['statusCode'] == 200
    assert json.loads(response['body'])['message'] == 'Checked in successfully'
    assert table.get_item(Key={'tripId': 'trip-1'})['Item']['status'] == 'arrived'


def test_check_in_deletes_the_shared_location(load, add_trip, table):
    add_trip('trip-1', lastLocation={'lat': Decimal('-26.2'), 'lng': Decimal('28.0'),
                                     'accuracy': Decimal('5'), 'at': '2026-10-17T09:00:00'})
    check_in(load('checkIn'), 'trip-1')

    saved = table.get_item(Key={'tripId': 'trip-1'})['Item']
    assert 'lastLocation' not in saved        # once you are safe, nobody needs your location


def test_check_in_works_after_an_alert_was_sent(load, add_trip, table):
    add_trip('trip-1', status='alert_sent')
    check_in(load('checkIn'), 'trip-1')
    assert table.get_item(Key={'tripId': 'trip-1'})['Item']['status'] == 'arrived'


def test_check_in_leaves_other_trips_alone(load, add_trip, table):
    add_trip('trip-1')
    add_trip('trip-2')
    check_in(load('checkIn'), 'trip-1')
    assert table.get_item(Key={'tripId': 'trip-2'})['Item']['status'] == 'in_progress'


def test_response_has_cors_headers(load, add_trip):
    add_trip('trip-1')
    assert check_in(load('checkIn'), 'trip-1')['headers']['Access-Control-Allow-Origin'] == '*'