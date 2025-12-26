import json
import boto3
import uuid
import os
import traceback
from datetime import datetime
from decimal import Decimal

TABLE_BUILDINGS = os.environ['TABLE_BUILDINGS']

def lambda_handler(event, context):
    try:
        print("=== ADD BUILDING ===")
        print(f"Event: {json.dumps(event, default=str)}")

       
        body = {}
        if event.get('body'):
            try:
                body = json.loads(event['body'])
            except json.JSONDecodeError:
                return {
                    'statusCode': 400,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({
                        'message': 'Invalid JSON in request body',
                        'success': False
                    })
                }

        print(f"Request body: {body}")

        
        building_name = body.get('name')
        wings = body.get('wings', [])
        wing_details = body.get('wing_details', {})
        user_id = body.get('user_id')  

        
        if not building_name or not wings or not wing_details or not user_id:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'message': 'Missing required fields: name, wings, wing_details, or user_id',
                    'success': False
                })
            }

       
        building_name = building_name.strip()
        if len(building_name) < 2:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'message': 'Building name must be at least 2 characters long',
                    'success': False
                })
            }

        if not isinstance(user_id, str) or len(user_id) < 10:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'message': 'Invalid user_id format',
                    'success': False
                })
            }

       
        if not isinstance(wings, list) or len(wings) == 0:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'message': 'Wings must be a non-empty array',
                    'success': False
                })
            }

        for wing in wings:
            if not isinstance(wing, str) or not wing.strip():
                return {
                    'statusCode': 400,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({
                        'message': f'Invalid wing name: {wing}',
                        'success': False
                    })
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
                    'body': json.dumps({
                        'message': f'Missing details for wing {wing}',
                        'success': False
                    })
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
                    'body': json.dumps({
                        'message': f'Invalid data for wing {wing}. Need total_floors and units_per_floor',
                        'success': False
                    })
                }

            
            try:
                total_floors = int(total_floors)
                units_per_floor = int(units_per_floor)

                
                if total_floors <= 0 or total_floors > 100:
                    return {
                        'statusCode': 400,
                        'headers': {
                            'Content-Type': 'application/json',
                            'Access-Control-Allow-Origin': '*'
                        },
                        'body': json.dumps({
                            'message': f'Total floors for wing {wing} must be between 1 and 100',
                            'success': False
                        })
                    }

                if units_per_floor <= 0 or units_per_floor > 20:
                    return {
                        'statusCode': 400,
                        'headers': {
                            'Content-Type': 'application/json',
                            'Access-Control-Allow-Origin': '*'
                        },
                        'body': json.dumps({
                            'message': f'Units per floor for wing {wing} must be between 1 and 20',
                            'success': False
                        })
                    }

            except (ValueError, TypeError):
                return {
                    'statusCode': 400,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({
                        'message': f'Invalid numeric values for wing {wing}',
                        'success': False
                    })
                }

            wing_total_units = total_floors * units_per_floor
            total_units_of_building += wing_total_units

            processed_wings[wing] = {
                'total_floors': total_floors,
                'units_per_floor': units_per_floor,
                'total_units': wing_total_units
            }

        
        building_item = {
            'building_id': building_id,
            'building_name': building_name,
            'user_id': user_id,  
            'wings': wings,
            'wing_details': processed_wings,
            'total_wings': len(wings),
            'total_units_of_building': total_units_of_building,
            'status': 'active',
            'created_at': current_time,
            'updated_at': current_time
        }

        
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table(TABLE_BUILDINGS)
        
        try:
            table.put_item(Item=building_item)
            print(f"Building created: {building_id} by user: {user_id}")
            
        except Exception as e:
            print(f"Error saving building: {str(e)}")
            return {
                'statusCode': 500,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'message': 'Failed to save building to database',
                    'success': False,
                    'error': str(e)
                })
            }

        
        response_data = {
            'user_id': user_id,
            'name': building_name,
            'wings': wings,
            'wing_details': wing_details  
        }

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'message': 'Building created successfully',
                'success': True,
                'data': response_data,  # Main data in 'data' field
                'building_info': {      # Additional info
                    'building_id': building_id,
                    'total_wings': len(wings),
                    'total_units_of_building': total_units_of_building,
                    'status': 'active',
                    'created_at': current_time
                }
            })
        }

    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        traceback.print_exc()
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'message': 'Internal server error',
                'success': False,
                'error': str(e)
            })
        }