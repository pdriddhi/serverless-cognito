import json
import boto3
import os
import traceback

TABLE_BUILDINGS = os.environ['TABLE_BUILDINGS']

def lambda_handler(event, context):
    print("=== GET USER BUILDINGS (Cognito Auth) ===")
    
    try:
        request_context = event.get('requestContext', {})
        authorizer = request_context.get('authorizer', {})
        claims = authorizer.get('claims', {})
        
        cognito_user_id = claims.get('sub')
        username = claims.get('username', '')
        
        user_id_to_search = None
        query_params = event.get('queryStringParameters') or {}
        query_user_id = query_params.get('user_id')
        
        if query_user_id:
            user_id_to_search = query_user_id
        elif username and username.startswith('+91'):
            user_id_to_search = username[3:]
        
        if not user_id_to_search:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({
                    'message': 'Unable to determine user identity.',
                    'success': False
                })
            }
        
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table(TABLE_BUILDINGS)
        
        response = table.scan(
            FilterExpression='user_id = :uid',
            ExpressionAttributeValues={':uid': user_id_to_search}
        )
        
        items = response.get('Items', [])
        
        buildings = []
        
        for item in items:
            wing_details = item.get('wing_details', {})
            wings = item.get('wings', [])
            
            building_total_units = 0
            updated_wing_details = {}
            
            for wing in wings:
                wing_info = wing_details.get(wing, {})
                
                total_floors = int(wing_info.get('total_floors', 0))
                units_per_floor = int(wing_info.get('units_per_floor', 0))
                
                wing_total_units = total_floors * units_per_floor
                
                updated_wing_info = wing_info.copy()
                updated_wing_info['total_units'] = wing_total_units
                
                building_total_units += wing_total_units
                
                updated_wing_details[wing] = updated_wing_info
            
            building_data = {
                'building_id': item.get('building_id'),
                'name': item.get('building_name'),
                'building_name': item.get('building_name'),
                'user_id': item.get('user_id'),
                'wings': wings,
                'wing_details': updated_wing_details,
                'total_wings': len(wings),
                'total_units': building_total_units,
                'total_units_of_building': building_total_units,
                'status': item.get('status', 'active'),
                'created_at': item.get('created_at'),
                'updated_at': item.get('updated_at')
            }
            
            if item.get('address'):
                building_data['address'] = item.get('address')
            if item.get('city'):
                building_data['city'] = item.get('city')
            if item.get('pincode'):
                building_data['pincode'] = item.get('pincode')
            
            buildings.append(building_data)
        
        if not buildings:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({
                    'message': 'No buildings found for this user',
                    'success': False,
                    'user_id': user_id_to_search
                })
            }
        
        response_body = {
            'success': True,
            'message': f'Found {len(buildings)} building(s)',
            'user_id': user_id_to_search,
            'buildings': buildings
        }
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps(response_body, default=str)
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        traceback.print_exc()
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({
                'success': False,
                'message': 'Failed to get buildings',
                'error': str(e)
            })
        }
