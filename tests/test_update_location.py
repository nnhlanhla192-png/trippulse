import json
import pytest


def send(module, trip_id, body):
    event = {
        'pathParameters': {'tripId': trip_id},
        'body': body if isinstance(body, str) else json.dumps(body),
    }
    return module.lambda_handler(event, None)


GOOD_POSITION = {'lat': -26.2041, 'lng': 28.0473, 'accuracy': 12.6}


def test_saves_the_position_on_an_active_trip(load, add_trip, table):
    add_trip('trip-1')
    response = send(load('updateLocation'), 'trip-1', GOOD_POSITION)

    assert response['statusCode'] == 200
    saved = table.get_item(Key={'tripId': 'trip-1'})['Item']['lastLocation']
    assert float(saved['lat']) == -26.2041
    assert float(saved['lng']) == 28.0473
    assert float(saved['accuracy']) == 13          # rounded to whole metres
    assert saved['at']                              # has a timestamp


def test_a_newer_position_replaces_the_older_one(load, add_trip, table):
    add_trip('trip-1')
    module = load('updateLocation')
    send(module, 'trip-1', GOOD_POSITION)
    send(module, 'trip-1', {'lat': -26.3, 'lng': 28.1})

    saved = table.get_item(Key={'tripId': 'trip-1'})['Item']['lastLocation']
    assert float(saved['lat']) == -26.3             # only the newest is kept


def test_still_accepts_positions_after_an_alert_was_sent(load, add_trip):
    add_trip('trip-1', status='alert_sent')
    assert send(load('updateLocation'), 'trip-1', GOOD_POSITION)['statusCode'] == 200


def test_refuses_a_trip_that_already_arrived(load, add_trip, table):
    add_trip('trip-1', status='arrived')
    response = send(load('updateLocation'), 'trip-1', GOOD_POSITION)

    assert response['statusCode'] == 409
    assert 'lastLocation' not in table.get_item(Key={'tripId': 'trip-1'})['Item']


def test_unknown_trip_is_refused_and_no_fake_trip_is_created(load, table):
    response = send(load('updateLocation'), 'ghost', GOOD_POSITION)

    assert response['statusCode'] == 409
    assert table.scan()['Count'] == 0


@pytest.mark.parametrize('bad_body', [
    {'lat': 'north', 'lng': 28.0},      # not a number
    {'lat': 95, 'lng': 28.0},           # latitude cannot be above 90
    {'lat': -26.2, 'lng': 200},         # longitude cannot be above 180
    {'lat': 'nan', 'lng': 28.0},        # "not a number"
    {'lng': 28.0},                      # lat missing
    'this is not json',
])
def test_bad_positions_are_rejected_with_400(load, add_trip, bad_body):
    add_trip('trip-1')
    assert send(load('updateLocation'), 'trip-1', bad_body)['statusCode'] == 400


def test_response_has_cors_headers(load, add_trip):
    add_trip('trip-1')
    response = send(load('updateLocation'), 'trip-1', GOOD_POSITION)
    assert response['headers']['Access-Control-Allow-Origin'] == '*'