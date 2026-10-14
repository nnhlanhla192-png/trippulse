import json
import boto3

# Connect to DynamoDB and point to our Trips table
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('Trips')


def lambda_handler(event, context):
    """
    Runs when someone calls GET /trips/{tripId} through API Gateway.
    Fetches and returns the current details of a specific trip.
    """

    # Get the tripId from the URL path (e.g. /trips/abc123 -> "abc123")
    trip_id = event['pathParameters']['tripId']

    # Fetch the item from DynamoDB matching this tripId
    response = table.get_item(
        Key={'tripId': trip_id}
    )

    # If no trip was found with that ID, return a 404
    if 'Item' not in response:
        return {
            'statusCode': 404,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'GET,POST,PATCH,OPTIONS'
            },
            'body': json.dumps({
                'message': 'Trip not found'
            })
        }

    # Otherwise, return the trip's details
    trip = response['Item']

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Methods': 'GET,POST,PATCH,OPTIONS'
        },
        'body': json.dumps(trip)
    }