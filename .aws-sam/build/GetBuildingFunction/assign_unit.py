import json
import boto3
import uuid
from datetime import datetime

dynamodb = boto3.resource('dynamodb')

def lambda_handler(event, context):
    try:
        print("Assign Unit function started")

        # Parse request body
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})

        # Extract required fields
        user_id = body.get('user_id')
        building_id = body.get('building_id')
        unit_number = body.get('unit_number')
        floor = body.get('floor')  # Now required
        wings = body.get('wings')    # New required field
        
        # Optional fields with defaults
        unit_type = body.get('unit_type', '2BHK')
        area_sqft = body.get('area_sqft', 0)
        rent_amount = body.get('rent_amount', 0)

        # Validation - ALL required fields
        required_fields = ['user_id', 'building_id', 'unit_number', 'floor', 'wings']
        missing_fields = [field for field in required_fields if not body.get(field)]
        
        if missing_fields:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({
                    'message': f'Missing required fields: {", ".join(missing_fields)}'
                })
            }

        # Use correct table names
        user_units_table = dynamodb.Table('UserUnits-dev')
        users_table = dynamodb.Table('Users-dev')
        buildings_table = dynamodb.Table('Buildings-dev')

        # Check if user exists
        user_response = users_table.get_item(Key={'user_id': user_id})
        if 'Item' not in user_response:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': 'User not found'})
            }

        # Check if building exists
        building_response = buildings_table.get_item(Key={'building_id': building_id})
        if 'Item' not in building_response:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': 'Building not found'})
            }

        # Check if wing exists in building
        building_data = building_response['Item']
        building_wings = building_data.get('wings', [])
        
        # If building has wings defined, validate the wing
        if isinstance(building_wings, str):
            available_wings = [w.strip() for w in building_wings.split(',')]

# Already list
        elif isinstance(building_wings, list):
            available_wings = [str(w).strip() for w in building_wings]

        else:
            available_wings = []

# Validate wings value
        if wings not in available_wings:
           return {
               'statusCode': 400,
               'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
               'body': json.dumps({
                    'message': f'Invalid wings. Available wings: {", ".join(available_wings)}'
               })
             }

        # Generate unit ID
        unit_id = f"UNIT-{uuid.uuid4().hex[:8].upper()}"

        # Create unit assignment with wing
        unit_item = {
            'unit_id': unit_id,
            'user_id': user_id,
            'building_id': building_id,
            'unit_number': unit_number,
            'floor': int(floor),  
            'wings': wings,          
            'unit_type': unit_type,
            'area_sqft': area_sqft,
            'rent_amount': rent_amount,
            'assigned_at': datetime.now().isoformat(),
            'status': 'active'
        }

        # Save to DynamoDB
        user_units_table.put_item(Item=unit_item)

        return {
            'statusCode': 201,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({
                'message': 'Unit assigned successfully',
                'unit_id': unit_id,
                'user_id': user_id,
                'building_id': building_id,
                'unit_number': unit_number,
                'floor': floor,
                'wings': wings,
                'unit_type': unit_type,
                'area_sqft': area_sqft,
                'rent_amount': rent_amount
            })
        }

    except Exception as e:
        print(f"Error in assign_unit: {str(e)}")
        import traceback
        print(traceback.format_exc())
        
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': f'Failed to assign unit: {str(e)}'})
        }
