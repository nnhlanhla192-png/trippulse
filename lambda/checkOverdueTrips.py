import json
import boto3
from datetime import datetime, timezone
import os
import re
from botocore.exceptions import ClientError

# Connect to DynamoDB and point to our Trips table
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('Trips')

# Connect to SNS, the service we use to send alert notifications
sns = boto3.client('sns')
ses = boto3.client('ses')

# The SNS "topic" is the notification channel the alert emails go through
SNS_TOPIC_ARN = 'arn:aws:sns:eu-north-1:544795558109:TripPulseAlerts'

# The address contact emails are sent FROM. It must be verified in Amazon SES.
# It lives in an environment variable on the Lambda function, not in the code.
# If it is not set, contact emails are simply switched off.
SENDER_EMAIL = os.environ.get('SENDER_EMAIL')

# A simple check that a contact looks like an email address (and not a phone number)
EMAIL_PATTERN = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def email_the_contact(trip):
    """
    Emails the contact typed on the trip. Returns True if an email was sent.
    It never raises an error: if the email fails, the other alerts must still go out.
    """
    contact = trip['contactPhoneOrEmail'].strip()
    if not SENDER_EMAIL or not EMAIL_PATTERN.match(contact):
        return False

    location = trip.get('lastLocation')
    if location:
        where = (
            f"Their last known location is: https://www.google.com/maps?q={location['lat']},{location['lng']}\n"
            f"(updated at {location['at']} UTC)"
        )
    else:
        where = "They did not share their location."

    text = (
        f"Hi {trip['contactName']},\n\n"
        f"{trip['userName']} said they would arrive by {trip['expectedArrivalTime']} (UTC) "
        f"and has not checked in yet.\n\n"
        f"{where}\n\n"
        f"Please try to reach {trip['userName']}. If you cannot reach them and you are worried "
        f"about their safety, contact the police on 10111 (or 112 from a mobile phone).\n\n"
        f"This message was sent automatically by TripPulse."
    )

    try:
        ses.send_email(
            Source=SENDER_EMAIL,
            Destination={'ToAddresses': [contact]},
            Message={
                'Subject': {'Data': f"TripPulse alert: {trip['userName']} has not checked in"},
                'Body': {'Text': {'Data': text}},
            },
        )
        return True
    except ClientError as error:
        # For example: the address is not verified while SES is still in sandbox mode.
        # This message shows up in the CloudWatch logs.
        print(f"Could not email {contact}: {error}")
        return False


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
    emailed = 0

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

            # Email the contact typed on the trip (if it is an email address)
            if email_the_contact(trip):
                emailed += 1

            # Send the actual alert via SNS
            message = (
                f"ALERT: {trip['userName']} has not checked in.\n"
                f"Expected arrival: {trip['expectedArrivalTime']}\n"
                f"Contact: {trip['contactName']} ({trip['contactPhoneOrEmail']})"
            )

            # If the traveler was sharing their location, add the last known
            # position to the alert so the contact knows where to start looking.
            location = trip.get('lastLocation')
            if location:
                message += (
                    f"\nLast known location: https://www.google.com/maps?q={location['lat']},{location['lng']}"
                    f"\nLocation updated at: {location['at']} (UTC)"
                )
            else:
                message += "\nNo location was shared for this trip."

            sns.publish(
                TopicArn=SNS_TOPIC_ARN,
                Message=message,
                Subject='TripPulse Safety Alert'
            )

    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': f'Checked all trips, found {len(overdue_trips)} overdue',
            'overdueCount': len(overdue_trips),
                        'overdueCount': len(overdue_trips),
            'emailedContacts': emailed
            
        })
    }