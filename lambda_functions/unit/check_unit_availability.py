# lambda_functions/unit/check_unit_availability.py (UPDATED VERSION)
import json
import boto3
import os
from decimal import Decimal

dynamodb = boto3.resource('dynamodb')

TABLE_USERUNITS = os.environ.get('TABLE_USERUNITS', 'UserUnits-dev')
MEMBERS_TABLE = os.environ.get('MEMBERS_TABLE', 'Members-dev')
TABLE_BUILDINGS = os.environ.get('TABLE_BUILDINGS', 'Buildings-dev')

def convert_decimal(obj):
    """Convert Decimal objects to float/int for JSON serialization"""
    if isinstance(obj, list):
        return [convert_decimal(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: convert_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    return obj

def enrich_wing_details(wing_details):
    """Add total_units calculation to wing_details"""
    enriched = {}
    for wing_name, details in wing_details.items():
        if isinstance(details, dict):
            total_floors = details.get('total_floors', 0)
            units_per_floor = details.get('units_per_floor', 0)
            
            try:
                total_floors = int(total_floors)
                units_per_floor = int(units_per_floor)
                total_units = total_floors * units_per_floor
            except:
                total_units = 0
            
            enriched[wing_name] = {
                **details,
                'total_units': total_units
            }
    return enriched

def lambda_handler(event, context):
    """
    Check if a unit is available for assignment/connection request
    """
    try:
        print("=== CHECK UNIT AVAILABILITY FUNCTION ===")
        
        query_params = event.get('queryStringParameters', {}) or {}
        print(f"Query params: {query_params}")
        
        building_id = query_params.get('building_id')
        wing = query_params.get('wing')
        floor = query_params.get('floor')
        unit_number = query_params.get('unit_number')
        
        if not building_id:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'success': False,
                    'message': 'building_id is required'
                })
            }
        
        user_units_table = dynamodb.Table(TABLE_USERUNITS)
        members_table = dynamodb.Table(MEMBERS_TABLE) if MEMBERS_TABLE else None
        buildings_table = dynamodb.Table(TABLE_BUILDINGS)
        
        try:
            building_response = buildings_table.get_item(
                Key={'building_id': building_id}
            )
            
            if 'Item' not in building_response:
                return {
                    'statusCode': 404,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({
                        'success': False,
                        'message': 'Building not found'
                    })
                }
            
            building = building_response['Item']
            building_wings = building.get('wings', [])
            
            wing_details = building.get('wing_details', {})
            enriched_wing_details = enrich_wing_details(wing_details)
            
            if wing and wing not in building_wings:
                return {
                    'statusCode': 400,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({
                        'success': False,
                        'message': f'Invalid wing. Available wings: {", ".join(building_wings)}'
                    })
                }
                
        except Exception as e:
            print(f"Error fetching building: {e}")
            return {
                'statusCode': 500,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'success': False,
                    'message': 'Error validating building',
                    'error': str(e)
                })
            }
        
        unit_occupants = []
        
        check_specific_unit = all([building_id, wing, floor, unit_number])
        
        if check_specific_unit:
            filter_expressions = [
                'building_id = :bid',
                'wings = :wing',
                'floor = :floor',
                'unit_number = :unit',
                'status = :active'
            ]
            
            try:
                floor_int = int(floor)
                expression_values = {
                    ':bid': building_id,
                    ':wing': wing,
                    ':floor': floor_int,
                    ':unit': unit_number,
                    ':active': 'active'
                }
                
                response = user_units_table.scan(
                    FilterExpression=' AND '.join(filter_expressions),
                    ExpressionAttributeValues=expression_values
                )
                
                for unit in response.get('Items', []):
                    occupant = {
                        'unit_id': unit.get('unit_id'),
                        'user_id': unit.get('user_id'),
                        'assigned_at': unit.get('assigned_at'),
                        'status': unit.get('status'),
                        'source': 'UserUnits'
                    }
                    unit_occupants.append(occupant)
                    
            except ValueError:
                return {
                    'statusCode': 400,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({
                        'success': False,
                        'message': 'floor must be a valid number'
                    })
                }
        else:
            filter_expressions = ['building_id = :bid', 'status = :active']
            expression_values = {':bid': building_id, ':active': 'active'}
            
            if wing:
                filter_expressions.append('wings = :wing')
                expression_values[':wing'] = wing
            
            if floor:
                try:
                    floor_int = int(floor)
                    filter_expressions.append('floor = :floor')
                    expression_values[':floor'] = floor_int
                except ValueError:
                    return {
                        'statusCode': 400,
                        'headers': {
                            'Content-Type': 'application/json',
                            'Access-Control-Allow-Origin': '*'
                        },
                        'body': json.dumps({
                            'success': False,
                            'message': 'floor must be a valid number'
                        })
                    }
            
            if unit_number:
                filter_expressions.append('unit_number = :unit')
                expression_values[':unit'] = unit_number
            
            try:
                response = user_units_table.scan(
                    FilterExpression=' AND '.join(filter_expressions),
                    ExpressionAttributeValues=expression_values
                )
                
                for unit in response.get('Items', []):
                    occupant = {
                        'unit_id': unit.get('unit_id'),
                        'user_id': unit.get('user_id'),
                        'assigned_at': unit.get('assigned_at'),
                        'source': 'UserUnits'
                    }
                    unit_occupants.append(occupant)
                    
            except Exception as e:
                print(f"Error scanning UserUnits: {e}")
        
        member_occupants = []
        
        if members_table and check_specific_unit:
            try:
                member_filter_expressions = [
                    'building_id = :bid',
                    'wings = :wing',
                    'floor = :floor',
                    'unit_number = :unit'
                ]
                member_values = {
                    ':bid': building_id,
                    ':wing': wing,
                    ':floor': floor,
                    ':unit': unit_number
                }
                
                member_response = members_table.scan(
                    FilterExpression=' AND '.join(member_filter_expressions),
                    ExpressionAttributeValues=member_values
                )
                
                for member in member_response.get('Items', []):
                    member_details = {
                        'user_id': member.get('user_id'),
                        'name': member.get('name'),
                        'mobile_no': member.get('mobile_no'),
                        'approved_at': member.get('approved_at'),
                        'member_type': member.get('member_type'),
                        'source': 'Members'
                    }
                    member_occupants.append(member_details)
                    
            except Exception as e:
                print(f"Error scanning Members table: {e}")
        
        all_occupants = unit_occupants + member_occupants
        
        building_info = {
            'building_id': building_id,
            'building_name': building.get('building_name'),
            'building_code': building.get('building_code'), 
            'valid_wings': building_wings,
            'wing_details': enriched_wing_details
        }
        
        search_criteria = {
            'building_id': building_id,
            'wing': wing,
            'floor': floor,
            'unit_number': unit_number
        }
        
        if all_occupants and check_specific_unit:

            first_occupant = all_occupants[0]
            
            user_info = {}
            try:
                if first_occupant.get('user_id'):
                    users_table = dynamodb.Table('Users-dev')
                    user_response = users_table.get_item(
                        Key={'user_id': first_occupant.get('user_id')}
                    )
                    if 'Item' in user_response:
                        user_data = user_response['Item']
                        user_info = {
                            'user_name': user_data.get('name'),
                            'user_mobile': user_data.get('mobile'),
                            'user_email': user_data.get('email')
                        }
            except Exception as e:
                print(f"Error fetching user details: {e}")
            
            response_data = {
                'success': True,
                'available': False,
                'message': 'Unit is already occupied',
                'occupants_count': len(all_occupants),
                'current_occupant': {
                    **first_occupant,
                    **user_info
                },
                'all_occupants': all_occupants[:5],
                'building_info': building_info,
                'search_criteria': search_criteria
            }
        elif check_specific_unit and not all_occupants:

            response_data = {
                'success': True,
                'available': True,
                'message': 'Unit is available for assignment',
                'occupants_count': 0,
                'building_info': building_info,
                'search_criteria': search_criteria
            }
        else:
            if all_occupants:
                message = f'Found {len(all_occupants)} occupied unit(s) matching criteria'
            else:
                message = 'No occupied units found matching criteria'
            
            response_data = {
                'success': True,
                'available': len(all_occupants) == 0,
                'message': message,
                'occupants_count': len(all_occupants),
                'building_info': building_info,
                'search_criteria': search_criteria,
                'occupants_preview': all_occupants[:3] if all_occupants else []
            }
        
        response_data = convert_decimal(response_data)
        
        print(f"Check result: Available = {response_data.get('available')}")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(response_data, default=str)
        }
        
    except Exception as e:
        print(f"Unexpected error in check_unit_availability: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'success': False,
                'message': 'Internal server error while checking unit availability',
                'error': str(e)
            })
        }