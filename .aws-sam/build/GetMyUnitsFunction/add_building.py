import json
import boto3
import uuid
import os
from datetime import datetime
from decimal import Decimal

TABLE_BUILDINGS = os.environ['TABLE_BUILDINGS']

def lambda_handler(event, context):
    try:
        print("=== ADD BUILDING ===")

        body = json.loads(event.get('body', '{}'))
        print(f"Request body: {body}")

        building_name = body.get('name')
        wings = body.get('wings', [])
        wing_details = body.get('wing_details', {})

        if not building_name or not wings or not wing_details:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'message': 'Missing required fields'})
            }

        building_id = f"BLD-{uuid.uuid4().hex[:8].upper()}"
        current_time = datetime.utcnow().isoformat()

        total_units_of_building = 0
        processed_wings = {}

        # Process each wing
        for wing in wings:
            details = wing_details.get(wing)

            if not details:
                return {
                    'statusCode': 400,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({'message': f'Missing details for wing {wing}'})
                }

            total_floors = details.get('total_floors')
            units_per_floor = details.get('units_per_floor')

            if not total_floors or not units_per_floor:
                return {
                    'statusCode': 400,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({'message': f'Invalid data for wing {wing}'})
                }

            wing_total_units = total_floors * units_per_floor
            total_units_of_building += wing_total_units

            processed_wings[wing] = {
                'total_floors': Decimal(str(total_floors)),
                'units_per_floor': Decimal(str(units_per_floor)),
                'total_units': Decimal(str(wing_total_units))
            }

        building_item = {
            'building_id': building_id,
            'building_name': building_name,
            'wings': wings,  # as it is
            'wing_details': processed_wings,
            'total_wings': Decimal(str(len(wings))),
            'total_units_of_building': Decimal(str(total_units_of_building)),
            'status': 'active',
            'created_at': current_time,
            'updated_at': current_time
        }

        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table(TABLE_BUILDINGS)
        table.put_item(Item=building_item)

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'message': 'Building created successfully',
                'building_id': building_id,
                'total_wings': len(wings),
                'total_units_of_building': total_units_of_building
            })
        }

    except Exception as e:
        print(str(e))
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'message': 'Failed to create building'})
        }

