import json
import boto3
import uuid
import os
from datetime import datetime
from decimal import Decimal
import traceback

dynamodb = boto3.resource('dynamodb')

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)

def calculate_total(bill_items):
    """Calculate total amount from bill items"""
    try:
        total = Decimal('0.00')
        for item in bill_items:
            if 'price_per_unit' in item:
                price_per_unit = Decimal(str(item.get('price_per_unit', 0)))
                units_consumed = Decimal(str(item.get('units_consumed', 1)))
                item_total = price_per_unit * units_consumed
            elif 'fixed_amount' in item:
                item_total = Decimal(str(item.get('fixed_amount', 0)))
            elif 'amount' in item:
                amount = Decimal(str(item.get('amount', 0)))
                units_consumed = Decimal(str(item.get('units_consumed', 1)))
                item_total = amount * units_consumed
            else:
                item_total = Decimal('0.00')
            
            total += item_total
        
        return round(total, 2)
    except Exception as e:
        print(f"Error calculating total: {str(e)}")
        return Decimal('0.00')

def build_response(status_code, body):
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token',
            'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
        },
        'body': json.dumps(body, cls=DecimalEncoder)
    }

def lambda_handler(event, context):
    print("=== CREATE UNIT MAINTENANCE BILL API ===")
    
    try:
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})
        
        print(f"Request body: {body}")
        
        required_fields = ['building_id', 'maintenance_id', 'user_id', 'wings', 'floor', 'unit_no', 'bill_items']
        missing_fields = [field for field in required_fields if not body.get(field)]
        
        if missing_fields:
            return build_response(400, {
                'success': False,
                'message': 'Missing required fields',
                'missing_fields': missing_fields
            })
        
        bill_items = body.get('bill_items', [])
        if not isinstance(bill_items, list):
            return build_response(400, {
                'success': False,
                'message': 'bill_items must be a list'
            })
        
        total_amount = calculate_total(bill_items)
        
        unit_maintenance_id = f"UNIT-MAINT-{uuid.uuid4().hex[:8].upper()}"
        now = datetime.utcnow().isoformat()
        
        UNIT_MAINTENANCE_TABLE = os.environ.get('TABLE_UNIT_MAINTENANCE', 'UnitMaintenanceBills-dev')
        table = dynamodb.Table(UNIT_MAINTENANCE_TABLE)
        
        item = {
            'unit_maintenance_id': unit_maintenance_id,
            'sk': f'MAINT#{body["maintenance_id"]}',

            'user_id': body['user_id'],
            
            'building_id': body['building_id'],
            'maintenance_id': body['maintenance_id'],
            'wings': body['wings'],
            'floor': str(body['floor']),
            'unit_no': body['unit_no'],
            
            'bill_items': bill_items,
            'total_amount': total_amount,
            
            'status': body.get('status', 'pending'),
            'payment_status': body.get('payment_status', 'unpaid'),
            
            'created_at': now,
            'updated_at': now
        }
        
        print(f"Saving to DynamoDB: {UNIT_MAINTENANCE_TABLE}")
        print(f"Item: {json.dumps(item, default=str)}")
        
        table.put_item(Item=item)
        
        response_data = {
            'unit_maintenance_id': unit_maintenance_id,
            'user_id': body['user_id'],
            'building_id': body['building_id'],
            'maintenance_id': body['maintenance_id'],
            'wings': body['wings'],
            'floor': body['floor'],
            'unit_no': body['unit_no'],
            'bill_items': bill_items,
            'total_amount': float(total_amount),
            'status': item['status'],
            'payment_status': item['payment_status'],
            'created_at': now
        }
        
        return build_response(201, {
            'success': True,
            'message': 'Unit maintenance bill created successfully',
            'data': response_data
        })
        
    except json.JSONDecodeError:
        return build_response(400, {
            'success': False,
            'message': 'Invalid JSON in request body'
        })
    except Exception as e:
        print(f"Error: {str(e)}")
        traceback.print_exc()
        return build_response(500, {
            'success': False,
            'message': f'Internal server error: {str(e)}'
        })
