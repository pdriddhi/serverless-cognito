import json
import boto3
import uuid
from datetime import datetime
from decimal import Decimal

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            if obj % 1 == 0:
                return int(obj)
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

def lambda_handler(event, context):
    try:
        print("=== PAYMENT PROCESSING ===")

        http_method = event.get('httpMethod')
        path = event.get('path', '')

        if http_method == 'POST' and '/payment/process' in path:
            return process_payment(event)
        elif http_method == 'GET' and '/payment' in path:
            query_params = event.get('queryStringParameters', {}) or {}
            if 'maintenance_id' in query_params:
                return get_payments_by_maintenance(event)
            elif 'payment_id' in query_params:
                return get_payment_by_id(event)
        elif http_method == 'GET' and '/payment/receipt' in path:
            return generate_receipt(event)
        elif http_method == 'POST' and '/payment/verify' in path:
            return verify_payment(event)
        else:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': 'Endpoint not found'})
            }

    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': 'Internal server error', 'error': str(e)})
        }

def process_payment(event):
    if 'body' not in event or not event['body']:
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': 'Request body is missing'})
        }

    try:
        body = json.loads(event['body'])
    except json.JSONDecodeError:
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': 'Invalid JSON in request body'})
        }

    payment_method = body.get('payment_method', '').lower()

    if payment_method == 'cash':
        return process_cash_payment(body)
    elif payment_method == 'online':
        return process_online_payment(body)
    else:
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': 'Invalid payment method. Use "cash" or "online"'})
        }

def process_cash_payment(body):
    # ✅ REMOVED: amount, received_by, payer_name, payer_contact, notes
    # ✅ ADDED: unit_maintenance_id, floor, wings, unit_number
    required_fields = ['maintenance_id', 'user_id', 'unit_maintenance_id']
    for field in required_fields:
        if field not in body:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': f'Missing field: {field}'})
            }

    dynamodb = boto3.resource('dynamodb')
    maintenance_table = dynamodb.Table('MaintenanceRecords-dev')
    unit_maintenance_table = dynamodb.Table('UnitMaintenanceBills-dev')

    try:
        # Get maintenance record
        maintenance_response = maintenance_table.get_item(
            Key={'maintenance_id': body['maintenance_id']}
        )
        
        # Get unit maintenance record
        unit_response = unit_maintenance_table.get_item(
            Key={'unit_maintenance_id': body['unit_maintenance_id']}
        )
        
    except Exception as e:
        print(f"DynamoDB error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': 'Database error'})
        }

    if 'Item' not in maintenance_response:
        return {
            'statusCode': 404,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': 'Maintenance not found'})
        }
    
    if 'Item' not in unit_response:
        return {
            'statusCode': 404,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': 'Unit maintenance bill not found'})
        }

    maintenance_record = maintenance_response['Item']
    unit_record = unit_response['Item']
    
    # Verify user owns this unit maintenance
    if unit_record.get('user_id') != body['user_id']:
        return {
            'statusCode': 403,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': 'Unauthorized: User does not own this unit maintenance'})
        }

    payment_id = f"PAY-{uuid.uuid4().hex[:8].upper()}"
    transaction_id = f"CASH-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    current_time = datetime.utcnow().isoformat()

    # ✅ Get amount from unit maintenance record
    amount_decimal = Decimal(str(unit_record.get('total_amount', '0')))
    
    # ✅ Get user details from Users table
    users_table = dynamodb.Table('Users-dev')
    try:
        user_response = users_table.get_item(
            Key={'user_id': body['user_id']}
        )
    except Exception as e:
        print(f"Error fetching user details: {str(e)}")

    # ✅ Get unit details from unit record
    unit_no = unit_record.get('unit_no', '')
    wings = unit_record.get('wings', '')
    floor = unit_record.get('floor', '')

    # ✅ Override with request values if provided
    unit_no = body.get('unit_number', unit_no)
    wings = body.get('wings', wings)
    floor = body.get('floor', floor)

    payment_record = {
        'payment_id': payment_id,
        'maintenance_id': body['maintenance_id'],
        'unit_maintenance_id': body['unit_maintenance_id'],
        'building_id': maintenance_record['building_id'],
        'user_id': body['user_id'],
        'amount': amount_decimal,
        'payment_method': 'cash',
        'payment_status': 'completed',
        'transaction_id': transaction_id,
        'received_by': 'System',  # ✅ Default value
        'wings': wings,
        'floor': floor,
        'unit_no': unit_no,
        'payment_date': current_time,
        'created_at': current_time,
        'updated_at': current_time
    }

    payment_table = dynamodb.Table('PaymentRecords-dev')

    try:
        # Save payment
        payment_table.put_item(Item=payment_record)

        # Update maintenance status
        maintenance_table.update_item(
            Key={'maintenance_id': body['maintenance_id']},
            UpdateExpression='SET #status = :status, updated_at = :updated_at',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':status': 'paid',
                ':updated_at': current_time
            }
        )
        
        # Update unit maintenance payment status
        unit_maintenance_table.update_item(
            Key={'unit_maintenance_id': body['unit_maintenance_id']},
            UpdateExpression='SET payment_status = :payment_status, updated_at = :updated_at',
            ExpressionAttributeValues={
                ':payment_status': 'paid',
                ':updated_at': current_time
            }
        )
        
    except Exception as e:
        print(f"DynamoDB write error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': 'Failed to save payment'})
        }

    print(f"Cash payment: {payment_id}")

    # ✅ New response format
    return {
        'statusCode': 201,
        'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
        'body': json.dumps({
            'success': True,
            'message': 'Cash payment processed successfully',
            'transaction_id': transaction_id,
            'unit_number': unit_no,
            'payment_status': 'completed',
            'payment_type': 'cash',
            'paid_date': current_time,
            'payment_id': payment_id,
            'amount': float(amount_decimal)
        }, cls=DecimalEncoder)
    }

def process_online_payment(body):
    # ✅ REMOVED: card_number, card_holder, expiry_date, cvv, payer_email, payer_contact, payer_name
    # ✅ ADDED: unit_maintenance_id, floor, wings, unit_number
    required_fields = ['maintenance_id', 'user_id', 'unit_maintenance_id']
    for field in required_fields:
        if field not in body:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': f'Missing field: {field}'})
            }

    dynamodb = boto3.resource('dynamodb')
    maintenance_table = dynamodb.Table('MaintenanceRecords-dev')
    unit_maintenance_table = dynamodb.Table('UnitMaintenanceBills-dev')

    try:
        # Get maintenance record
        maintenance_response = maintenance_table.get_item(
            Key={'maintenance_id': body['maintenance_id']}
        )
        
        # Get unit maintenance record
        unit_response = unit_maintenance_table.get_item(
            Key={'unit_maintenance_id': body['unit_maintenance_id']}
        )
        
    except Exception as e:
        print(f"DynamoDB error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': 'Database error'})
        }

    if 'Item' not in maintenance_response:
        return {
            'statusCode': 404,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': 'Maintenance not found'})
        }
    
    if 'Item' not in unit_response:
        return {
            'statusCode': 404,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': 'Unit maintenance bill not found'})
        }

    maintenance_record = maintenance_response['Item']
    unit_record = unit_response['Item']
    
    # Verify user owns this unit maintenance
    if unit_record.get('user_id') != body['user_id']:
        return {
            'statusCode': 403,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': 'Unauthorized: User does not own this unit maintenance'})
        }

    # ✅ Get amount from unit maintenance record
    amount_decimal = Decimal(str(unit_record.get('total_amount', '0')))
    
    # ✅ Get user details from Users table
    users_table = dynamodb.Table('Users-dev')
    try:
        user_response = users_table.get_item(
            Key={'user_id': body['user_id']}
        )
    except Exception as e:
        print(f"Error fetching user details: {str(e)}")

    # ✅ Get unit details from unit record
    unit_no = unit_record.get('unit_no', '')
    wings = unit_record.get('wings', '')
    floor = unit_record.get('floor', '')

    # ✅ Override with request values if provided
    unit_no = body.get('unit_number', unit_no)
    wings = body.get('wings', wings)
    floor = body.get('floor', floor)

    # ✅ Simulate online payment (mock payment gateway)
    transaction_id = f"TXN{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}"
    payment_id = f"PAY-{uuid.uuid4().hex[:8].upper()}"
    current_time = datetime.utcnow().isoformat()

    # ✅ Mock payment gateway response
    gateway_reference = f"GW-{uuid.uuid4().hex[:8].upper()}"
    gateway_status = 'approved'
    
    if gateway_status != 'approved':
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({
                'success': False,
                'message': 'Payment failed. Please try again.'
            })
        }

    payment_record = {
        'payment_id': payment_id,
        'maintenance_id': body['maintenance_id'],
        'unit_maintenance_id': body['unit_maintenance_id'],
        'building_id': maintenance_record['building_id'],
        'user_id': body['user_id'],
        'amount': amount_decimal,
        'payment_method': 'online',
        'payment_status': 'completed',
        'transaction_id': transaction_id,
        'gateway_reference': gateway_reference,
        'gateway_status': gateway_status,
        'card_last_four': '1111',
        'card_type': 'visa',
        'wings': wings,
        'floor': floor,
        'unit_no': unit_no,
        'payment_date': current_time,
        'created_at': current_time,
        'updated_at': current_time
    }

    payment_table = dynamodb.Table('PaymentRecords-dev')

    try:
        payment_table.put_item(Item=payment_record)

        maintenance_table.update_item(
            Key={'maintenance_id': body['maintenance_id']},
            UpdateExpression='SET
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':status': 'paid',
                ':updated_at': current_time
            }
        )
        
        unit_maintenance_table.update_item(
            Key={'unit_maintenance_id': body['unit_maintenance_id']},
            UpdateExpression='SET payment_status = :payment_status, updated_at = :updated_at',
            ExpressionAttributeValues={
                ':payment_status': 'paid',
                ':updated_at': current_time
            }
        )
        
    except Exception as e:
        print(f"DynamoDB write error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({
                'success': False,
                'message': 'Failed to save payment'
            })
        }

    print(f"Online payment: {payment_id}")

    return {
        'statusCode': 201,
        'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
        'body': json.dumps({
            'success': True,
            'message': 'Online payment processed successfully',
            'transaction_id': transaction_id,
            'unit_number': unit_no,
            'payment_status': 'completed',
            'payment_type': 'online',
            'paid_date': current_time,
            'payment_id': payment_id,
            'amount': float(amount_decimal),
            'gateway_reference': gateway_reference
        }, cls=DecimalEncoder)
    }

