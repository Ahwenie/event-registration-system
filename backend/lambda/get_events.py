import json
import boto3
from boto3.dynamodb.conditions import Key
from decimal import Decimal

# Initialize DynamoDB resource
# 'dynamodb' is the AWS service name. 'resource' is high-level API.
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')  # Change to your region
events_table = dynamodb.Table('Events')

# Helper: DynamoDB returns Decimal types, but JSON can't serialize them.
# This function converts Decimal to int or float.
class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        return super().default(obj)

def lambda_handler(event, context):
    """
    This function runs every time the API Gateway receives a GET /events request.
    'event' contains HTTP request info (method, headers, body).
    'context' contains runtime info (request ID, time remaining).
    """
    try:
        # Scan reads ALL items from the table. For small tables (<1MB), this is fine.
        # For production with millions of items, you'd use Query with pagination.
        response = events_table.scan()
        events = response.get('Items', [])
        
        # If there are more items (pagination), keep scanning
        while 'LastEvaluatedKey' in response:
            response = events_table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
            events.extend(response.get('Items', []))
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'  # CORS: allows frontend to call this
            },
            'body': json.dumps({
                'success': True,
                'count': len(events),
                'events': events
            }, cls=DecimalEncoder)
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")  # Goes to CloudWatch Logs
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'success': False, 'error': str(e)})
        }