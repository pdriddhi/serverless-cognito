import json
import boto3
import os
import traceback
from decimal import Decimal
from boto3.dynamodb.conditions import Attr

dynamodb = boto3.resource('dynamodb')

USER_UNITS_TABLE = os.environ['TABLE_USERUNITS']
BUILDINGS_TABLE = os.environ['TABLE_BUILDINGS']


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def lambda_handler(event, context):
    try:
        print("Get My Units function started")
        print("EVENT:", json.dumps(event))

        query_params = event.get('queryStringParameters') or {}
        user_id = query_params.get('user_id')

        if not user_id:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({
                    'success': False,
                    'message': 'user_id parameter is required'
                })
            }

        user_units_table = dynamodb.Table(USER_UNITS_TABLE)
        buildings_table = dynamodb.Table(BUILDINGS_TABLE)

        response = user_units_table.scan(
            FilterExpression=Attr('user_id').eq(user_id)
        )

        units = response.get('Items', [])

        for unit in units:
            building_id = unit.get('building_id')
            if building_id:
                building_resp = buildings_table.get_item(
                    Key={'building_id': building_id}
                )
                if 'Item' in building_resp:
                    unit['building_details'] = building_resp['Item']

        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({
                'success': True,
                'user_id': user_id,
                'count': len(units),
                'units': units
            }, cls=DecimalEncoder)
        }

    except Exception as e:
        print("ERROR:", str(e))
        traceback.print_exc()

        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({
                'success': False,
                'message': 'Failed to get units',
                'error': str(e)
            })
        }
