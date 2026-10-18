import json
from datetime import datetime
from decimal import Decimal

import boto3

# Connect to DynamoDB and point to our Trips table
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('Trips')

# CORS headers: written permission for the browser (same as the other functions)
CORS_HEADERS = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Allow-Methods': 'GET,POST,PATCH,OPTIONS'
}


def respond(status_code, payload):
    return {
        'statusCode': status_code,
        'headers': CORS_HEADERS,
        'body': json.dumps(payload)
    }


def lambda_handler(event, context):
    """
    Runs when someone calls POST /trips/{tripId}/location.
    Saves the traveler's latest position on their trip. Only the newest
    position is kept, and only while the trip is still active.
    """

    # Which trip is this for? (comes from the URL)
    trip_id = (event.get('pathParameters') or {}).get('tripId')
    if not trip_id:
        return respond(400, {'message': 'tripId is required'})

    # Read the position that was sent
    try:
        body = json.loads(event.get('body') or '{}')
        lat = float(body['lat'])
        lng = float(body['lng'])
        accuracy = float(body.get('accuracy') or 0)
    except (KeyError, TypeError, ValueError):
        return respond(400, {'message': 'lat and lng must be numbers'})

    # Reject impossible positions (this also rejects NaN and infinity)
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return respond(400, {'message': 'lat or lng is out of range'})

    # DynamoDB does not accept normal decimal numbers (floats), so we use Decimal.
    location = {
        'lat': Decimal(str(lat)),
        'lng': Decimal(str(lng)),
        'accuracy': Decimal(str(round(accuracy))),
        'at': datetime.utcnow().isoformat(timespec='seconds')
    }

    try:
        # Only save if the trip exists and has not already ended with a safe arrival
        table.update_item(
            Key={'tripId': trip_id},
            ConditionExpression='attribute_exists(tripId) AND (#s = :active OR #s = :alerted)',
            UpdateExpression='SET lastLocation = :loc',
            ExpressionAttributeNames={'#s': 'status'},
            ExpressionAttributeValues={
                ':active': 'in_progress',
                ':alerted': 'alert_sent',
                ':loc': location
            }
        )
    except table.meta.client.exceptions.ConditionalCheckFailedException:
        return respond(409, {'message': 'This trip was not found or is no longer active'})

    return respond(200, {'message': 'Location saved'})