import json
import boto3
import uuid
from datetime import datetime
from decimal import Decimal

# ============================================
# SNS for email notifications
# ============================================
sns = boto3.client('sns', region_name='us-east-1')

# REPLACE THE NUMBER BELOW WITH YOUR ACTUAL AWS ACCOUNT ID
SNS_TOPIC_ARN = 'arn:aws:sns:us-east-1:YOUR-ACCOUNT-ID:EventRegistrationNotifications'

dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
events_table = dynamodb.Table('Events')
registrations_table = dynamodb.Table('Registrations')

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        return super().default(obj)

def lambda_handler(event, context):
    try:
        body = json.loads(event.get('body', '{}'))
        
        event_id = body.get('eventId')
        email = body.get('email')
        full_name = body.get('fullName')
        
        if not all([event_id, email, full_name]):
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'success': False, 'error': 'Missing required fields'})
            }
        
        if '@' not in email or '.' not in email.split('@')[-1]:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'success': False, 'error': 'Invalid email format'})
            }
        
        event_response = events_table.get_item(Key={'eventId': event_id})
        event = event_response.get('Item')
        
        if not event:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'success': False, 'error': 'Event not found'})
            }
        
        available_seats = int(event.get('availableSeats', 0))
        
        if available_seats <= 0:
            return {
                'statusCode': 409,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'success': False, 'error': 'Event is sold out'})
            }
        
        registration_id = str(uuid.uuid4())
        registration_date = datetime.utcnow().isoformat() + 'Z'
        
        dynamodb_client = boto3.client('dynamodb', region_name='us-east-1')
        
        try:
            dynamodb_client.transact_write_items(
                TransactItems=[
                    {
                        'Update': {
                            'TableName': 'Events',
                            'Key': {
                                'eventId': {'S': event_id}
                            },
                            'UpdateExpression': 'SET availableSeats = availableSeats - :dec, #status = :status',
                            'ConditionExpression': 'availableSeats >= :min',
                            'ExpressionAttributeNames': {
                                '#status': 'status'
                            },
                            'ExpressionAttributeValues': {
                                ':dec': {'N': '1'},
                                ':min': {'N': '1'},
                                ':status': {'S': 'Limited' if available_seats - 1 < int(event.get('totalSeats', 0)) * 0.2 else 'Available'}
                            }
                        }
                    },
                    {
                        'Put': {
                            'TableName': 'Registrations',
                            'Item': {
                                'registrationId': {'S': registration_id},
                                'eventId': {'S': event_id},
                                'email': {'S': email},
                                'fullName': {'S': full_name},
                                'registrationDate': {'S': registration_date},
                                'ticketStatus': {'S': 'Confirmed'}
                            },
                            'ConditionExpression': 'attribute_not_exists(registrationId)'
                        }
                    }
                ]
            )
        except dynamodb_client.exceptions.TransactionCanceledException:
            return {
                'statusCode': 409,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'success': False, 'error': 'Registration failed. Event may be sold out. Please try again.'})
            }
        
        # ============================================
        # SEND EMAIL VIA SNS
        # ============================================
        try:
            sns.publish(
                TopicArn=SNS_TOPIC_ARN,
                Subject=f'Registration Confirmed: {event.get("eventName")}',
                Message=f"""Hello {full_name},

You have successfully registered for:
Event: {event.get('eventName')}
Date: {event.get('eventDate')}
Location: {event.get('location')}

Your registration ID: {registration_id}

See you there!
"""
            )
        except Exception as e:
            print(f"Failed to send SNS notification: {e}")
            # Don't fail the registration if email fails
        
        updated_event = events_table.get_item(Key={'eventId': event_id})['Item']
        new_available = int(updated_event.get('availableSeats', 0))
        
        if new_available == 0:
            events_table.update_item(
                Key={'eventId': event_id},
                UpdateExpression='SET #status = :status',
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={':status': 'Sold Out'}
            )
        
        return {
            'statusCode': 201,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'success': True,
                'message': 'Registration successful',
                'registrationId': registration_id,
                'eventName': event.get('eventName'),
                'remainingSeats': new_available
            }, cls=DecimalEncoder)
        }
        
    except json.JSONDecodeError:
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'success': False, 'error': 'Invalid JSON in request body'})
        }
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'success': False, 'error': str(e)})
        }