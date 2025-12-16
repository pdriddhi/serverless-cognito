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
    required_fields = ['maintenance_id', 'amount', 'received_by']
    for field in required_fields:
        if field not in body:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': f'Missing field: {field}'})
            }

    dynamodb = boto3.resource('dynamodb')
    maintenance_table = dynamodb.Table('MaintenanceRecords-dev')

    try:
        maintenance_response = maintenance_table.get_item(
            Key={'maintenance_id': body['maintenance_id']}
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

    maintenance_record = maintenance_response['Item']
    payment_id = f"PAY-{uuid.uuid4().hex[:8].upper()}"
    current_time = datetime.utcnow().isoformat()

    amount_decimal = Decimal(str(body['amount']))

    payment_record = {
        'payment_id': payment_id,
        'maintenance_id': body['maintenance_id'],
        'building_id': maintenance_record['building_id'],
        'amount': amount_decimal,
        'payment_method': 'cash',
        'payment_status': 'completed',
        'transaction_id': f"CASH-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        'received_by': body['received_by'],
        'payer_name': body.get('payer_name', ''),
        'payer_contact': body.get('payer_contact', ''),
        'notes': body.get('notes', ''),
        'payment_date': current_time,
        'created_at': current_time,
        'updated_at': current_time
    }

    payment_table = dynamodb.Table('PaymentRecords-dev')
    
    try:
        payment_table.put_item(Item=payment_record)
        
        maintenance_table.update_item(
            Key={'maintenance_id': body['maintenance_id']},
            UpdateExpression='SET #status = :status, updated_at = :updated_at',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':status': 'paid',
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

    response_payment = payment_record.copy()
    response_payment['amount'] = float(response_payment['amount'])
    
    return {
        'statusCode': 201,
        'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
        'body': json.dumps({
            'message': 'Cash payment successful',
            'payment_id': payment_id,
            'receipt_number': f"RC-{payment_id}",
            'payment_method': 'cash',
            'payment': response_payment
        }, cls=DecimalEncoder)
    }

def process_online_payment(body):
    required_fields = ['maintenance_id', 'amount', 'card_number', 'card_holder', 'expiry_date', 'cvv']
    for field in required_fields:
        if field not in body:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': f'Missing field: {field}'})
            }

    dynamodb = boto3.resource('dynamodb')
    maintenance_table = dynamodb.Table('MaintenanceRecords-dev')

    try:
        maintenance_response = maintenance_table.get_item(
            Key={'maintenance_id': body['maintenance_id']}
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

    maintenance_record = maintenance_response['Item']

    card_number = str(body['card_number']).replace(' ', '').replace('-', '')
    
    if len(card_number) != 16 or not card_number.isdigit():
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': 'Invalid card number. Must be 16 digits.'})
        }

    cvv = str(body['cvv'])
    if len(cvv) != 3 or not cvv.isdigit():
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': 'Invalid CVV. Must be 3 digits.'})
        }

    transaction_id = f"TXN{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}"
    payment_id = f"PAY-{uuid.uuid4().hex[:8].upper()}"
    current_time = datetime.utcnow().isoformat()

    def get_card_type(card_num):
        if card_num.startswith('4'):
            return 'visa'
        elif card_num.startswith('5'):
            return 'mastercard'
        elif card_num.startswith('34') or card_num.startswith('37'):
            return 'amex'
        elif card_num.startswith('6'):
            return 'discover'
        else:
            return 'unknown'

    amount_decimal = Decimal(str(body['amount']))

    payment_record = {
        'payment_id': payment_id,
        'maintenance_id': body['maintenance_id'],
        'building_id': maintenance_record['building_id'],
        'amount': amount_decimal,
        'payment_method': 'online',
        'payment_status': 'completed',
        'transaction_id': transaction_id,
        'gateway_reference': f"GW-{uuid.uuid4().hex[:8].upper()}",
        'card_last_four': card_number[-4:],
        'card_type': get_card_type(card_number),
        'payer_name': body['card_holder'],
        'payer_email': body.get('payer_email', ''),
        'payer_contact': body.get('payer_contact', ''),
        'payment_date': current_time,
        'created_at': current_time,
        'updated_at': current_time
    }

    payment_table = dynamodb.Table('PaymentRecords-dev')
    
    try:
        payment_table.put_item(Item=payment_record)
        
        maintenance_table.update_item(
            Key={'maintenance_id': body['maintenance_id']},
            UpdateExpression='SET #status = :status, updated_at = :updated_at',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':status': 'paid',
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

    print(f"Online payment: {payment_id}")

    response_payment = payment_record.copy()
    response_payment['amount'] = float(response_payment['amount'])
    
    return {
        'statusCode': 201,
        'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
        'body': json.dumps({
            'message': 'Online payment successful',
            'payment_id': payment_id,
            'transaction_id': transaction_id,
            'receipt_number': f"RC-{payment_id}",
            'payment_method': 'online',
            'payment': {
                **response_payment,
                'card_number': f"**** **** **** {card_number[-4:]}"
            }
        }, cls=DecimalEncoder)
    }

def get_payments_by_maintenance(event):
    query_params = event.get('queryStringParameters', {}) or {}
    maintenance_id = query_params.get('maintenance_id')

    if not maintenance_id:
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': 'maintenance_id query parameter is required'})
        }

    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('PaymentRecords-dev')

    try:
        response = table.scan(
            FilterExpression='maintenance_id = :maintenance_id',
            ExpressionAttributeValues={':maintenance_id': maintenance_id}
        )
    except Exception as e:
        print(f"DynamoDB error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': 'Database error'})
        }

    def convert_decimals(obj):
        if isinstance(obj, Decimal):
            return float(obj) if '.' in str(obj) else int(obj)
        elif isinstance(obj, dict):
            return {k: convert_decimals(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_decimals(i) for i in obj]
        return obj

    payments = [convert_decimals(item) for item in response.get('Items', [])]
    total_paid = sum(p['amount'] for p in payments)

    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
        'body': json.dumps({
            'maintenance_id': maintenance_id,
            'payments': payments,
            'summary': {
                'total_payments': len(payments),
                'total_amount': total_paid,
                'cash_payments': len([p for p in payments if p.get('payment_method') == 'cash']),
                'online_payments': len([p for p in payments if p.get('payment_method') == 'online'])
            }
        }, cls=DecimalEncoder)
    }

def get_payment_by_id(event):
    query_params = event.get('queryStringParameters', {}) or {}
    payment_id = query_params.get('payment_id')

    if not payment_id:
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': 'payment_id query parameter is required'})
        }

    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('PaymentRecords-dev')

    try:
        response = table.get_item(Key={'payment_id': payment_id})
    except Exception as e:
        print(f"DynamoDB error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': 'Database error'})
        }

    if 'Item' not in response:
        return {
            'statusCode': 404,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': 'Payment not found'})
        }

    def convert_decimals(obj):
        if isinstance(obj, Decimal):
            return float(obj) if '.' in str(obj) else int(obj)
        elif isinstance(obj, dict):
            return {k: convert_decimals(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_decimals(i) for i in obj]
        return obj

    payment = convert_decimals(response['Item'])

    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
        'body': json.dumps(payment, cls=DecimalEncoder)
    }

def generate_receipt(event):
    query_params = event.get('queryStringParameters', {}) or {}
    payment_id = query_params.get('payment_id')

    if not payment_id:
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': 'payment_id query parameter is required'})
        }

    dynamodb = boto3.resource('dynamodb')
    payment_table = dynamodb.Table('PaymentRecords-dev')

    try:
        payment_response = payment_table.get_item(Key={'payment_id': payment_id})
    except Exception as e:
        print(f"DynamoDB error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': 'Database error'})
        }

    if 'Item' not in payment_response:
        return {
            'statusCode': 404,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': 'Payment not found'})
        }

    payment_record = payment_response['Item']

    maintenance_table = dynamodb.Table('MaintenanceRecords-dev')
    
    try:
        maintenance_response = maintenance_table.get_item(
            Key={'maintenance_id': payment_record['maintenance_id']}
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

    maintenance_record = maintenance_response['Item']

    amount = float(payment_record['amount']) if isinstance(payment_record['amount'], Decimal) else payment_record['amount']

    receipt_data = {
        'receipt_number': f"RC-{payment_id}",
        'payment_id': payment_id,
        'transaction_id': payment_record['transaction_id'],
        'payment_date': payment_record['payment_date'],
        'amount': amount,
        'payment_method': payment_record['payment_method'],
        'payer_name': payment_record.get('payer_name', 'N/A'),
        'building_id': payment_record['building_id'],
        'maintenance_id': payment_record['maintenance_id'],
        'bill_name': maintenance_record['bill_name'],
        'description': maintenance_record.get('description', ''),
        'status': 'PAID',
        'issued_date': datetime.utcnow().isoformat()
    }

    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
        'body': json.dumps({
            'message': 'Receipt generated',
            'receipt': receipt_data
        }, cls=DecimalEncoder)
    }

def verify_payment(event):
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

    transaction_id = body.get('transaction_id')

    if not transaction_id:
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': 'transaction_id is required'})
        }

    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('PaymentRecords-dev')

    try:
        response = table.scan(
            FilterExpression='transaction_id = :transaction_id',
            ExpressionAttributeValues={':transaction_id': transaction_id}
        )
    except Exception as e:
        print(f"DynamoDB error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': 'Database error'})
        }

    items = response.get('Items', [])

    if not items:
        return {
            'statusCode': 404,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': 'Transaction not found'})
        }

    payment_record = items[0]

    amount = float(payment_record['amount']) if isinstance(payment_record['amount'], Decimal) else payment_record['amount']

    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
        'body': json.dumps({
            'transaction_id': transaction_id,
            'payment_status': payment_record['payment_status'],
            'payment_id': payment_record['payment_id'],
            'amount': amount,
            'payment_date': payment_record['payment_date'],
            'verified': True
        }, cls=DecimalEncoder)
    }
