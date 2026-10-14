import json
import boto3

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('Trips')

def lambda_handler(event, context):
    # Get the tripId from the URL path
    trip_id = event['pathParameters']['tripId']
    
    # Update the trip's status to 'arrived'
    table.update_item(
        Key={'tripId': trip_id},
        UpdateExpression='SET #s = :status',
        ExpressionAttributeNames={'#s': 'status'},
        ExpressionAttributeValues={':status': 'arrived'}
    )
    
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json'
             'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Methods': 'GET,POST,PATCH,OPTIONS'
        },
        'body': json.dumps({
            'message': 'Checked in successfully',
            'tripId': trip_id
        })
    }