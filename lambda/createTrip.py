import json
import boto3
import uuid
from datetime import datetime

# Connect to DynamoDB
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('Trips')

def lambda_handler(event, context):
    # Parse the incoming request body
    body = json.loads(event['body'])
    
    # Generate a unique trip ID
    trip_id = str(uuid.uuid4())
    
    # Build the trip record
    trip = {
        'tripId': trip_id,
        'userName': body['userName'],
        'contactName': body['contactName'],
        'contactPhoneOrEmail': body['contactPhoneOrEmail'],
        'startTime': datetime.utcnow().isoformat(),
        'expectedArrivalTime': body['expectedArrivalTime'],
        'status': 'in_progress'
    }
    
    # Save it to DynamoDB
    table.put_item(Item=trip)
    
    # Return a success response
    return {
        'statusCode': 201,
        'headers': {
            'Content-Type': 'application/json'
        },
        'body': json.dumps({
            'message': 'Trip started successfully',
            'tripId': trip_id
        })
    }