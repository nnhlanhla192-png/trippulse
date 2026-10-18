                                                          
import io
import json
import pathlib
import sys
import zipfile

import boto3
from botocore.exceptions import BotoCoreError, ClientError

REGION = 'eu-north-1'
FUNCTIONS = ['createTrip', 'getTrip', 'checkIn', 'updateLocation', 'checkOverdueTrips']
LAMBDA_DIR = pathlib.Path(__file__).parent / 'lambda'

# Functions made in the console expect their code in a file called lambda_function.py
EXPECTED_HANDLER = 'lambda_function.lambda_handler'

SEND_EMAIL_POLICY = {
    'Version': '2012-10-17',
    'Statement': [{'Effect': 'Allow', 'Action': 'ses:SendEmail', 'Resource': '*'}],
}


def make_zip(name):
    """Pack lambda/<name>.py into a zip, renamed to lambda_function.py."""
    source = (LAMBDA_DIR / f'{name}.py').read_bytes()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('lambda_function.py', source)
    return buffer.getvalue()


def deploy(client, name):
    """Upload one function's code. Returns True if it worked."""
    config = client.get_function_configuration(FunctionName=name)
    if config['Handler'] != EXPECTED_HANDLER:
        print(f"SKIPPED {name}: its handler is {config['Handler']}, not {EXPECTED_HANDLER}")
        return False
    client.update_function_code(FunctionName=name, ZipFile=make_zip(name))
    client.get_waiter('function_updated_v2').wait(FunctionName=name)   # wait until it is live
    print(f'deployed {name}')
    return True


def set_up_email(client, sender):
    """Give checkOverdueTrips a sender address and permission to send email."""
    name = 'checkOverdueTrips'

    # 1. Add SENDER_EMAIL to the function, keeping any variables it already has
    config = client.get_function_configuration(FunctionName=name)
    variables = (config.get('Environment') or {}).get('Variables', {})
    variables['SENDER_EMAIL'] = sender
    client.update_function_configuration(FunctionName=name, Environment={'Variables': variables})
    client.get_waiter('function_updated_v2').wait(FunctionName=name)
    print(f'{name}: SENDER_EMAIL is now {sender}')

    # 2. Let the function's role send email (and nothing else in SES)
    role_name = config['Role'].split('/')[-1]
    iam = boto3.client('iam')
    iam.put_role_policy(RoleName=role_name, PolicyName='AllowSendEmail',
                        PolicyDocument=json.dumps(SEND_EMAIL_POLICY))
    print(f'{role_name}: allowed to send email (policy AllowSendEmail)')
    print(f'Reminder: {sender} must show "Verified" in Amazon SES.')
    return True


def main(args):
    client = boto3.client('lambda', region_name=REGION)
    try:
        if args and args[0] == 'email':
            if len(args) != 2 or '@' not in args[1]:
                print('Usage: deploy.py email you@gmail.com')
                return 1
            return 0 if set_up_email(client, args[1]) else 1

        names = args or FUNCTIONS
        unknown = [n for n in names if n not in FUNCTIONS]
        if unknown:
            print(f"Unknown function(s): {', '.join(unknown)}. Choose from: {', '.join(FUNCTIONS)}")
            return 1
        results = [deploy(client, name) for name in names]
        return 0 if all(results) else 1
    except ClientError as error:
        print(f"AWS said no: {error}")
        return 1
    except BotoCoreError as error:
        print(f"Could not talk to AWS (are your credentials set up with `aws configure`?): {error}")
        return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))