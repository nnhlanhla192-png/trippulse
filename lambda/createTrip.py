import json
import uuid
from datetime import datetime

import boto3

# Connect to DynamoDB and point to our Trips table
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('Trips')

# CORS headers. A browser will only let a web page talk to this API if the API
# says so in writing. These headers are that written permission.
CORS_HEADERS = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Allow-Methods': 'GET,POST,PATCH,OPTIONS',
}

REQUIRED_FIELDS = ['userName', 'contactName', 'contactPhoneOrEmail', 'expectedArrivalTime']


def respond(status_code, payload):
    return {
        'statusCode': status_code,
        'headers': CORS_HEADERS,
        'body': json.dumps(payload),
    }


def lambda_handler(event, context):
    """Runs when someone calls POST /trips. Saves a new trip and returns its ID."""

    # Read the JSON body that was sent with the request
    try:
        body = json.loads(event.get('body') or '{}')
    except json.JSONDecodeError:
        return respond(400, {'message': 'Request body must be valid JSON'})

    # Make sure nothing important is missing or blank
    missing = [f for f in REQUIRED_FIELDS if not str(body.get(f, '')).strip()]
    if missing:
        return respond(400, {'message': 'Missing fields: ' + ', '.join(missing)})

    # The overdue checker reads this time later, so make sure it is a real date
    # (a bad value here would make the checker crash for every trip).
    try:
        datetime.fromisoformat(body['expectedArrivalTime'])
    except ValueError:
        return respond(400, {'message': 'expectedArrivalTime must look like 2026-08-16T20:00:00'})

    # Generate a unique trip ID
    trip_id = str(uuid.uuid4())

    # Build the trip record
    trip = {
        'tripId': trip_id,
        'userName': body['userName'].strip(),
        'contactName': body['contactName'].strip(),
        'contactPhoneOrEmail': body['contactPhoneOrEmail'].strip(),
        'startTime': datetime.utcnow().isoformat(),
        'expectedArrivalTime': body['expectedArrivalTime'],
        'status': 'in_progress',
    }

    # Save it to DynamoDB
    table.put_item(Item=trip)

    return respond(201, {
        'message': 'Trip started successfully',
        'tripId': trip_id,
    })