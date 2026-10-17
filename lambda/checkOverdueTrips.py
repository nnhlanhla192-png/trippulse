import json
import boto3
from datetime import datetime, timezone

# Connect to DynamoDB and point to our Trips table
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('Trips')

# Connect to SNS, the service we use to send alert notifications
sns = boto3.client('sns')

# The SNS "topic" is the notification channel the alert emails go through
SNS_TOPIC_ARN = 'arn:aws:sns:eu-north-1:544795558109:TripPulseAlerts'


def lambda_handler(event, context):
    """
    This function does NOT run because a user clicked something.
    It runs automatically on a schedule (every 5 minutes), triggered
    by EventBridge. Its job: scan for trips that are overdue and haven't
    been checked in, then send an alert for each one.
    """

    # Get the current time, so we can compare it against each trip's
    # expected arrival time
    now = datetime.now(timezone.utc)

    # Scan the whole table for trips that are still 'in_progress'
    # (In a bigger real-world app, we'd use a smarter query instead of
    # a full scan, but for this project's scale, scan is fine.)
    response = table.scan(
        FilterExpression='#s = :status',
        ExpressionAttributeNames={'#s': 'status'},
        ExpressionAttributeValues={':status': 'in_progress'}
    )

    overdue_trips = []

    # Check each in-progress trip to see if it's overdue
    for trip in response['Items']:
        expected_time = datetime.fromisoformat(trip['expectedArrivalTime']).replace(tzinfo=timezone.utc)

        if now > expected_time:
            overdue_trips.append(trip)

            # Mark this trip as 'alert_sent' so we don't alert on it again
            table.update_item(
                Key={'tripId': trip['tripId']},
                UpdateExpression='SET #s = :status',
                ExpressionAttributeNames={'#s': 'status'},
                ExpressionAttributeValues={':status': 'alert_sent'}
            )

            # Send the actual alert via SNS
            message = (
                f"ALERT: {trip['userName']} has not checked in.\n"
                f"Expected arrival: {trip['expectedArrivalTime']}\n"
                f"Contact: {trip['contactName']} ({trip['contactPhoneOrEmail']})"
            )

            sns.publish(
                TopicArn=SNS_TOPIC_ARN,
                Message=message,
                Subject='TripPulse Safety Alert'
            )

    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': f'Checked all trips, found {len(overdue_trips)} overdue',
            'overdueCount': len(overdue_trips)
        })
    }