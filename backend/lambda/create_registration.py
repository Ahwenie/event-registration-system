import json
import boto3  # type: ignore[import]
import uuid
from datetime import datetime
from decimal import Decimal

sns = boto3.client('sns', region_name='us-east-1')
SNS_TOPIC_ARN = 'arn:aws:sns:us-east-1:943378954952:EventRegistrationNotifications:1125ac99-66f8-4030-a9ea-ba9d9278a5e0'

dynamodb = boto3.resource('dynamodb', region_name='us-east-1')  # Change to your region
events_table = dynamodb.Table('Events')
registrations_table = dynamodb.Table('Registrations')

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        return super().default(obj)

def lambda_handler(event, context):
    """
    POST /registrations
    Body: {"eventId": "...", "email": "...", "fullName": "..."}
    """
    try:
        # Parse the JSON body from API Gateway
        body = json.loads(event.get('body', '{}'))
        
        event_id = body.get('eventId')
        email = body.get('email')
        full_name = body.get('fullName')
        
        # Input validation
        if not all([event_id, email, full_name]):
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'success': False, 'error': 'Missing required fields'})
            }
        
        # Basic email validation
        if '@' not in email or '.' not in email.split('@')[-1]:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'success': False, 'error': 'Invalid email format'})
            }
        
        # Step 1: Get current event to check availability
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
                'statusCode': 409,  # 409 = Conflict
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'success': False, 'error': 'Event is sold out'})
            }
        
        # Step 2: Atomically update availableSeats and create registration
        # We use ConditionExpression to prevent race conditions.
        # If another user registered between our get_item and update_item,
        # the condition fails and we retry.
        
        registration_id = str(uuid.uuid4())
        registration_date = datetime.utcnow().isoformat() + 'Z'
        
        # Transaction: Update event seats + Create registration
        # If either fails, BOTH fail. This keeps data consistent.
        dynamodb_client = boto3.client('dynamodb', region_name='us-east-1')  # Change to your region
        
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
                            # Prevent duplicate registration from same email for same event
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
        # Send confirmation email
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

        # Step 3: Update status if fully booked
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
            'statusCode': 201,  # 201 = Created
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
    