import json
import boto3
import uuid
import os
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

def validate_ids(user_id, building_id, maintenance_id, unit_maintenance_id):
    dynamodb = boto3.resource('dynamodb')
    
    users_table_name = os.environ.get('USERS_TABLE', 'UsersTable-dev')
    members_table_name = os.environ.get('MEMBERS_TABLE', 'MembersTable-dev')
    maintenance_table_name = os.environ.get('TABLE_MAINTENANCE', 'MaintenanceRecords-dev')
    unit_maintenance_table_name = os.environ.get('TABLE_UNIT_MAINTENANCE', 'UnitMaintenanceRecords-dev')
    
    users_table = dynamodb.Table(users_table_name)
    members_table = dynamodb.Table(members_table_name)
    maintenance_table = dynamodb.Table(maintenance_table_name)
    unit_maintenance_table = dynamodb.Table(unit_maintenance_table_name)
    
    try:
        user_response = users_table.get_item(Key={'user_id': user_id})
        if 'Item' not in user_response:
            return False, "User not found"
    except:
        return False, "Error validating user"
    
    try:
        response = members_table.query(
            IndexName='building-index',
            KeyConditionExpression='building_id = :b AND user_id = :u',
            ExpressionAttributeValues={
                ':b': building_id,
                ':u': user_id
            }
        )
        if response.get('Count', 0) == 0:
            return False, "User is not a member of this building"
    except Exception as e:
        print(f"Building validation error: {str(e)}")
        return False, "Error validating building membership"
    
    is_unit_maintenance = bool(unit_maintenance_id)
    
    if is_unit_maintenance:
        try:
            unit_maintenance_response = unit_maintenance_table.get_item(
                Key={'unit_maintenance_id': unit_maintenance_id}
            )
            if 'Item' not in unit_maintenance_response:
                return False, "Unit maintenance record not found"
            
            maintenance_record = unit_maintenance_response['Item']
            if maintenance_record.get('building_id') != building_id:
                return False, "Unit maintenance does not belong to this building"
                
            if maintenance_record.get('status') == 'paid':
                return False, "Unit maintenance is already paid"
                
        except Exception as e:
            print(f"Unit maintenance validation error: {str(e)}")
            return False, "Error validating unit maintenance"
    else:
        try:
            maintenance_response = maintenance_table.get_item(
                Key={'maintenance_id': maintenance_id}
            )
            
            if 'Item' not in maintenance_response:
                return False, "Maintenance record not found"
            
            maintenance_record = maintenance_response['Item']
            if maintenance_record.get('building_id') != building_id:
                return False, "Maintenance does not belong to this building"
                
            if maintenance_record.get('status') == 'paid':
                return False, "Maintenance is already paid"
                
        except Exception as e:
            print(f"Maintenance validation error: {str(e)}")
            return False, "Error validating maintenance"
    
    return True, "All validations passed"

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
    required_fields = ['user_id', 'building_id', 'amount']
    for field in required_fields:
        if field not in body:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': f'Missing field: {field}'})
            }
    
    maintenance_id = body.get('maintenance_id')
    unit_maintenance_id = body.get('unit_maintenance_id')
    
    if not maintenance_id and not unit_maintenance_id:
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': 'Either maintenance_id or unit_maintenance_id is required'})
        }

    user_id = body['user_id']
    building_id = body['building_id']
    
    is_valid, message = validate_ids(user_id, building_id, maintenance_id, unit_maintenance_id)
    if not is_valid:
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': message})
        }

    payment_id = f"PAY-{uuid.uuid4().hex[:8].upper()}"
    current_time = datetime.utcnow().isoformat()
    amount_decimal = Decimal(str(body['amount']))

    payment_record = {
        'payment_id': payment_id,
        'building_id': building_id,
        'user_id': user_id,
        'amount': amount_decimal,
        'payment_method': 'cash',
        'payment_status': 'completed',
        'payment_date': current_time,
        'created_at': current_time,
        'updated_at': current_time
    }
    
    if maintenance_id:
        payment_record['maintenance_id'] = maintenance_id
    
    if unit_maintenance_id:
        payment_record['unit_maintenance_id'] = unit_maintenance_id

    dynamodb = boto3.resource('dynamodb')
    payment_table_name = os.environ.get('TABLE_PAYMENT', 'PaymentRecords-dev')
    maintenance_table_name = os.environ.get('TABLE_MAINTENANCE', 'MaintenanceRecords-dev')
    unit_maintenance_table_name = os.environ.get('TABLE_UNIT_MAINTENANCE', 'UnitMaintenanceRecords-dev')
    
    payment_table = dynamodb.Table(payment_table_name)
    maintenance_table = dynamodb.Table(maintenance_table_name)
    unit_maintenance_table = dynamodb.Table(unit_maintenance_table_name)
    
    try:
        payment_table.put_item(Item=payment_record)
        
        if maintenance_id:
            maintenance_table.update_item(
                Key={'maintenance_id': maintenance_id},
                UpdateExpression='SET #status = :status, updated_at = :updated_at',
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={
                    ':status': 'paid',
                    ':updated_at': current_time
                }
            )
        
        if unit_maintenance_id:
            unit_maintenance_table.update_item(
                Key={'unit_maintenance_id': unit_maintenance_id},
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

    print(f"Cash payment recorded: {payment_id}")

    response_data = {
        'message': 'Cash payment successful',
        'payment_id': payment_id,
        'payment': {
            'payment_id': payment_id,
            'building_id': building_id,
            'user_id': user_id,
            'amount': float(amount_decimal),
            'payment_method': 'cash',
            'payment_status': 'completed',
            'payment_date': current_time
        }
    }
    
    if maintenance_id:
        response_data['payment']['maintenance_id'] = maintenance_id
    
    if unit_maintenance_id:
        response_data['payment']['unit_maintenance_id'] = unit_maintenance_id
    
    return {
        'statusCode': 201,
        'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
        'body': json.dumps(response_data, cls=DecimalEncoder)
    }

def process_online_payment(body):
    required_fields = ['user_id', 'building_id', 'amount', 'card_number', 'card_holder', 'expiry_date', 'cvv']
    for field in required_fields:
        if field not in body:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': f'Missing field: {field}'})
            }
    
    maintenance_id = body.get('maintenance_id')
    unit_maintenance_id = body.get('unit_maintenance_id')
    
    if not maintenance_id and not unit_maintenance_id:
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': 'Either maintenance_id or unit_maintenance_id is required'})
        }

    user_id = body['user_id']
    building_id = body['building_id']
    
    is_valid, message = validate_ids(user_id, building_id, maintenance_id, unit_maintenance_id)
    if not is_valid:
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': message})
        }

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

    payment_id = f"PAY-{uuid.uuid4().hex[:8].upper()}"
    current_time = datetime.utcnow().isoformat()
    amount_decimal = Decimal(str(body['amount']))

    payment_record = {
        'payment_id': payment_id,
        'building_id': building_id,
        'user_id': user_id,
        'amount': amount_decimal,
        'payment_method': 'online',
        'payment_status': 'completed',
        'payment_date': current_time,
        'created_at': current_time,
        'updated_at': current_time
    }
    
    if maintenance_id:
        payment_record['maintenance_id'] = maintenance_id
    
    if unit_maintenance_id:
        payment_record['unit_maintenance_id'] = unit_maintenance_id

    dynamodb = boto3.resource('dynamodb')
    payment_table_name = os.environ.get('TABLE_PAYMENT', 'PaymentRecords-dev')
    maintenance_table_name = os.environ.get('TABLE_MAINTENANCE', 'MaintenanceRecords-dev')
    unit_maintenance_table_name = os.environ.get('TABLE_UNIT_MAINTENANCE', 'UnitMaintenanceRecords-dev')
    
    payment_table = dynamodb.Table(payment_table_name)
    maintenance_table = dynamodb.Table(maintenance_table_name)
    unit_maintenance_table = dynamodb.Table(unit_maintenance_table_name)
    
    try:
        payment_table.put_item(Item=payment_record)
        
        if maintenance_id:
            maintenance_table.update_item(
                Key={'maintenance_id': maintenance_id},
                UpdateExpression='SET #status = :status, updated_at = :updated_at',
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={
                    ':status': 'paid',
                    ':updated_at': current_time
                }
            )
        
        if unit_maintenance_id:
            unit_maintenance_table.update_item(
                Key={'unit_maintenance_id': unit_maintenance_id},
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

    print(f"Online payment recorded: {payment_id}")

    response_data = {
        'message': 'Online payment successful',
        'payment_id': payment_id,
        'payment': {
            'payment_id': payment_id,
            'building_id': building_id,
            'user_id': user_id,
            'amount': float(amount_decimal),
            'payment_method': 'online',
            'payment_status': 'completed',
            'payment_date': current_time
        }
    }
    
    if maintenance_id:
        response_data['payment']['maintenance_id'] = maintenance_id
    
    if unit_maintenance_id:
        response_data['payment']['unit_maintenance_id'] = unit_maintenance_id
    
    return {
        'statusCode': 201,
        'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
        'body': json.dumps(response_data, cls=DecimalEncoder)
    }

def get_payments_by_maintenance(event):
    query_params = event.get('queryStringParameters', {}) or {}
    maintenance_id = query_params.get('maintenance_id')
    unit_maintenance_id = query_params.get('unit_maintenance_id')

    if not maintenance_id and not unit_maintenance_id:
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': 'Either maintenance_id or unit_maintenance_id query parameter is required'})
        }

    dynamodb = boto3.resource('dynamodb')
    payment_table_name = os.environ.get('TABLE_PAYMENT', 'PaymentRecords-dev')
    table = dynamodb.Table(payment_table_name)

    try:
        if maintenance_id:
            response = table.query(
                IndexName='MaintenanceIndex',
                KeyConditionExpression='maintenance_id = :maintenance_id',
                ExpressionAttributeValues={':maintenance_id': maintenance_id}
            )
        else:
            response = table.query(
                IndexName='UnitMaintenanceIndex',
                KeyConditionExpression='unit_maintenance_id = :unit_maintenance_id',
                ExpressionAttributeValues={':unit_maintenance_id': unit_maintenance_id}
            )
    except Exception as e:
        print(f"DynamoDB error: {str(e)}")
        try:
            if maintenance_id:
                response = table.scan(
                    FilterExpression='maintenance_id = :maintenance_id',
                    ExpressionAttributeValues={':maintenance_id': maintenance_id}
                )
            else:
                response = table.scan(
                    FilterExpression='unit_maintenance_id = :unit_maintenance_id',
                    ExpressionAttributeValues={':unit_maintenance_id': unit_maintenance_id}
                )
        except Exception as e2:
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

    result = {
        'payments': payments,
        'summary': {
            'total_payments': len(payments),
            'total_amount': total_paid,
            'cash_payments': len([p for p in payments if p.get('payment_method') == 'cash']),
            'online_payments': len([p for p in payments if p.get('payment_method') == 'online'])
        }
    }
    
    if maintenance_id:
        result['maintenance_id'] = maintenance_id
    
    if unit_maintenance_id:
        result['unit_maintenance_id'] = unit_maintenance_id
    
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
        'body': json.dumps(result, cls=DecimalEncoder)
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
    payment_table_name = os.environ.get('TABLE_PAYMENT', 'PaymentRecords-dev')
    table = dynamodb.Table(payment_table_name)

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