import json
import boto3

dynamodb = boto3.resource('dynamodb')

def lambda_handler(event, context):
    try:
        print("Get My Units function started")
        
        # Get user_id from query parameters
        query_params = event.get('queryStringParameters', {}) or {}
        user_id = query_params.get('user_id')
        
        if not user_id:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': 'user_id parameter is required'})
            }
        
        # Use correct table name
        user_units_table = dynamodb.Table('UserUnits-dev')
        buildings_table = dynamodb.Table('Buildings-dev')
        
        # Scan for user's units (since we don't have GSI)
        response = user_units_table.scan(
            FilterExpression='user_id = :uid',
            ExpressionAttributeValues={':uid': user_id}
        )
        
        units = response.get('Items', [])
        
        # Enrich with building details
        for unit in units:
            building_id = unit.get('building_id')
            if building_id:
                try:
                    building_response = buildings_table.get_item(Key={'building_id': building_id})
                    if 'Item' in building_response:
                        unit['building_details'] = building_response['Item']
                except Exception as e:
                    print(f"Error fetching building {building_id}: {e}")
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({
                'user_id': user_id,
                'units': units,
                'count': len(units)
            })
        }
        
    except Exception as e:
        print(f"Error in get_my_units: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': 'Failed to get units'})
        }
