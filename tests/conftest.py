"""Shared test setup.

The tests never touch your real AWS account. moto pretends to be AWS inside
your computer, so every test gets a fresh, empty, fake Trips table.
"""
import importlib
import os
import sys

import boto3
import pytest
from moto import mock_aws

# Fake credentials so boto3 never looks for real ones
os.environ['AWS_DEFAULT_REGION'] = 'eu-north-1'
os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'


@pytest.fixture
def table():
    """A fresh, empty, fake Trips table for one test."""
    with mock_aws():
        dynamodb = boto3.resource('dynamodb')
        trips = dynamodb.create_table(
            TableName='Trips',
            KeySchema=[{'AttributeName': 'tripId', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'tripId', 'AttributeType': 'S'}],
            BillingMode='PAY_PER_REQUEST',
        )
        yield trips


@pytest.fixture
def load(table):
    """Load a Lambda file by name, e.g. load('createTrip').

    The Lambda files connect to DynamoDB the moment they are imported, so they
    must be imported while the fake AWS is running. This makes sure of that.
    """
    def _load(name):
        sys.modules.pop(name, None)
        return importlib.import_module(name)
    return _load


@pytest.fixture
def add_trip(table):
    """Put a ready-made trip into the fake table and return its ID."""
    def _add(trip_id='trip-1', status='in_progress', expected='2099-01-01T20:00:00', **extra):
        item = {
            'tripId': trip_id,
            'userName': 'Nhlanhla',
            'contactName': 'Mom',
            'contactPhoneOrEmail': 'mom@example.com',
            'startTime': '2026-10-17T10:00:00',
            'expectedArrivalTime': expected,
            'status': status,
        }
        item.update(extra)
        table.put_item(Item=item)
        return trip_id
    return _add