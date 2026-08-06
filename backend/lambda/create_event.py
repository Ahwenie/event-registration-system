import json
import boto3
import uuid
from datetime import datetime
from decimal import Decimal

dynamodb = boto3.resource('dynamodb', region_name='us-east-1')  # Change to your region
events_table = dynamodb.Table('Events')

def lambda_handler(event, context):
    try:
        body = json.loads(event.get('body', '{}'))
        
        required_fields = ['eventName', 'eventDate', 'location', 'totalSeats']
        for field in required_fields:
            if field not in body:
                return {
                    'statusCode': 400,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({'success': False, 'error': f'Missing field: {field}'})
                }
        
        event_id = body.get('eventId', str(uuid.uuid4()))
        total_seats = int(body['totalSeats'])
        
        new_event = {
            'eventId': event_id,
            'eventName': body['eventName'],
            'eventDate': body['eventDate'],
            'location': body['location'],
            'totalSeats': total_seats,
            'availableSeats': total_seats,
            'status': 'Available',
            'createdAt': datetime.utcnow().isoformat() + 'Z'
        }
        
        events_table.put_item(Item=new_event)
        
        return {
            'statusCode': 201,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'success': True,
                'message': 'Event created',
                'eventId': event_id
            })
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'success': False, 'error': str(e)})
        }