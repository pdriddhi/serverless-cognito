import json
import boto3
import os

dynamodb = boto3.resource('dynamodb')
TABLE_BUILDINGS = os.environ['TABLE_BUILDINGS']

def lambda_handler(event, context):
    try:
        print("=== DELETE BUILDING ===")

        body = json.loads(event.get('body', '{}'))
        building_id = body.get('building_id')

        if not building_id:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': 'building_id is required'})
            }

        table = dynamodb.Table(TABLE_BUILDINGS)

        # Check existence
        response = table.get_item(Key={'building_id': building_id})
        if 'Item' not in response:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': 'Building not found'})
            }

        table.delete_item(Key={'building_id': building_id})

        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({
                'message': 'Building deleted successfully',
                'building_id': building_id
            })
        }

    except Exception as e:
        print("ERROR:", str(e))
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': 'Failed to delete building'})
        }
