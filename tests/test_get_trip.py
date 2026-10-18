import json


def get(module, trip_id):
    return module.lambda_handler({'pathParameters': {'tripId': trip_id}}, None)


def test_returns_the_trip(load, add_trip):
    add_trip('trip-1')
    response = get(load('getTrip'), 'trip-1')

    assert response['statusCode'] == 200
    trip = json.loads(response['body'])
    assert trip['tripId'] == 'trip-1'
    assert trip['userName'] == 'Nhlanhla'
    assert trip['status'] == 'in_progress'


def test_unknown_trip_returns_404(load):
    response = get(load('getTrip'), 'does-not-exist')
    assert response['statusCode'] == 404
    assert json.loads(response['body'])['message'] == 'Trip not found'


def test_response_has_cors_headers(load, add_trip):
    add_trip('trip-1')
    assert get(load('getTrip'), 'trip-1')['headers']['Access-Control-Allow-Origin'] == '*'


def test_a_saved_location_comes_back_as_normal_numbers(load, add_trip):
    # DynamoDB stores numbers as Decimal, which json.dumps cannot print.
    # This test protects the fix that turns them into normal numbers.
    from decimal import Decimal
    add_trip('trip-1', lastLocation={
        'lat': Decimal('-26.2041'), 'lng': Decimal('28.0473'),
        'accuracy': Decimal('10'), 'at': '2026-10-17T09:00:00',
    })
    trip = json.loads(get(load('getTrip'), 'trip-1')['body'])

    assert trip['lastLocation']['lat'] == -26.2041
    assert trip['lastLocation']['lng'] == 28.0473
    assert trip['lastLocation']['at'] == '2026-10-17T09:00:00'