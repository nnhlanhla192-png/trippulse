import json


def post(module, body):
    """Send a request to createTrip the way API Gateway would."""
    event = {'body': body if isinstance(body, str) else json.dumps(body)}
    return module.lambda_handler(event, None)


GOOD_TRIP = {
    'userName': 'Nhlanhla',
    'contactName': 'Mom',
    'contactPhoneOrEmail': 'mom@example.com',
    'expectedArrivalTime': '2099-01-01T20:00:00',
}


def test_creates_a_trip_and_returns_its_id(load, table):
    createTrip = load('createTrip')
    response = post(createTrip, GOOD_TRIP)

    assert response['statusCode'] == 201
    trip_id = json.loads(response['body'])['tripId']

    saved = table.get_item(Key={'tripId': trip_id})['Item']
    assert saved['userName'] == 'Nhlanhla'
    assert saved['contactName'] == 'Mom'
    assert saved['expectedArrivalTime'] == '2099-01-01T20:00:00'
    assert saved['status'] == 'in_progress'


def test_every_trip_gets_its_own_id(load):
    createTrip = load('createTrip')
    first = json.loads(post(createTrip, GOOD_TRIP)['body'])['tripId']
    second = json.loads(post(createTrip, GOOD_TRIP)['body'])['tripId']
    assert first != second


def test_response_has_cors_headers_so_browsers_accept_it(load):
    response = post(load('createTrip'), GOOD_TRIP)
    assert response['headers']['Access-Control-Allow-Origin'] == '*'


def test_missing_field_is_rejected_with_400(load, table):
    bad = {k: v for k, v in GOOD_TRIP.items() if k != 'contactName'}
    response = post(load('createTrip'), bad)
    assert response['statusCode'] == 400
    assert 'contactName' in json.loads(response['body'])['message']
    assert table.scan()['Count'] == 0          # nothing was saved


def test_blank_field_is_rejected_with_400(load):
    response = post(load('createTrip'), {**GOOD_TRIP, 'userName': '   '})
    assert response['statusCode'] == 400


def test_bad_arrival_time_is_rejected_with_400(load, table):
    # A bad time saved here would crash the overdue checker for everyone later.
    response = post(load('createTrip'), {**GOOD_TRIP, 'expectedArrivalTime': 'tomorrow'})
    assert response['statusCode'] == 400
    assert table.scan()['Count'] == 0


def test_body_that_is_not_json_is_rejected_with_400(load):
    assert post(load('createTrip'), 'this is not json')['statusCode'] == 400