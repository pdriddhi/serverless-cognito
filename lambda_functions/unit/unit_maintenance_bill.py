import json
import boto3
import uuid
import os
from datetime import datetime
from decimal import Decimal
from boto3.dynamodb.conditions import Key, Attr

TABLE_UNIT_MAINTENANCE = os.environ["TABLE_UNIT_MAINTENANCE"]
TABLE_USER_BUILDING_ROLES = os.environ.get("TABLE_USER_BUILDING_ROLES", "UserBuildingRoles-dev")
TABLE_MAINTENANCE = os.environ.get("TABLE_MAINTENANCE", "MaintenanceRecords-dev")

dynamodb = boto3.resource("dynamodb")
unit_maintenance_table = dynamodb.Table(TABLE_UNIT_MAINTENANCE)
user_building_roles_table = dynamodb.Table(TABLE_USER_BUILDING_ROLES) if TABLE_USER_BUILDING_ROLES else None
maintenance_table = dynamodb.Table(TABLE_MAINTENANCE) if TABLE_MAINTENANCE else None

def check_user_is_admin(user_id, building_id):
    """Check if user is admin for the given building"""
    try:
        if not TABLE_USER_BUILDING_ROLES or not user_building_roles_table:
            print("WARNING: TABLE_USER_BUILDING_ROLES not configured, skipping admin check")
            return True
            
        composite_key = f"{user_id}#{building_id}"
        
        response = user_building_roles_table.get_item(
            Key={'user_building_composite': composite_key}
        )
        
        if 'Item' in response:
            user_role = response['Item'].get('role')
            return user_role == 'admin'
        
        return False
        
    except Exception as e:
        print(f"Error checking user role: {str(e)}")
        return False

def check_user_has_any_role(user_id, building_id):
    """Check if user has any role (admin/member) in the building"""
    try:
        if not TABLE_USER_BUILDING_ROLES or not user_building_roles_table:
            print("WARNING: TABLE_USER_BUILDING_ROLES not configured, skipping role check")
            return True
            
        composite_key = f"{user_id}#{building_id}"
        
        response = user_building_roles_table.get_item(
            Key={'user_building_composite': composite_key}
        )
        
        if 'Item' in response:
            return True
        
        return False
        
    except Exception as e:
        print(f"Error checking user role: {str(e)}")
        return False

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj) if obj % 1 != 0 else int(obj)
        return super().default(obj)

def response(status, body):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "GET,POST,PATCH,DELETE,OPTIONS"
        },
        "body": json.dumps(body, cls=DecimalEncoder)
    }

def calculate_bill_items(items):
    """Calculate total amount from bill items - preserve all original fields"""
    total = Decimal("0.00")
    updated_items = []

    for item in items:
        try:
            if "amount" in item:
                item_total = Decimal(str(item.get("amount", 0)))
                updated_item = {
                    "name": item.get("name", ""),
                    "amount": float(item_total) if item_total % 1 != 0 else int(item_total),
                    "item_total": float(item_total) if item_total % 1 != 0 else int(item_total)
                }
            else:
                price_per_unit = Decimal(str(item.get("price_per_unit", 0)))
                units_consumed = Decimal(str(item.get("units_consumed", 1)))
                item_total = price_per_unit * units_consumed
                
                updated_item = {
                    "name": item.get("name", ""),
                    "price_per_unit": float(price_per_unit) if price_per_unit % 1 != 0 else int(price_per_unit),
                    "units_consumed": float(units_consumed) if units_consumed % 1 != 0 else int(units_consumed),
                    "item_total": float(item_total) if item_total % 1 != 0 else int(item_total)
                }
            
            for key, value in item.items():
                if key not in updated_item:
                    if isinstance(value, Decimal):
                        updated_item[key] = float(value) if value % 1 != 0 else int(value)
                    else:
                        updated_item[key] = value
            
            updated_items.append(updated_item)
            total += item_total
            
        except Exception as e:
            print(f"Error calculating bill item: {str(e)}")
            continue

    return updated_items, total

def get_maintenance_details(maintenance_id):
    """Get maintenance details to include in unit bill"""
    if not TABLE_MAINTENANCE or not maintenance_table:
        return None
    
    try:
        response = maintenance_table.get_item(
            Key={"maintenance_id": maintenance_id}
        )
        
        if 'Item' in response:
            item = response['Item']
            return {
                "maintenance_name": item.get("name", f"Maintenance-{maintenance_id}"),
                "description": item.get("description", ""),
                "due_date": item.get("due_date"),
                "month": item.get("month"),
                "year": item.get("year"),
                "status": item.get("status", "pending")
            }
    except Exception as e:
        print(f"Error fetching maintenance details: {str(e)}")
    
    return None

def lambda_handler(event, context):
    print("=== UNIT MAINTENANCE BILL HANDLER ===")

    method = event.get("httpMethod")
    path = event.get("path")

    if method == "OPTIONS":
        return response(200, {"success": True, "message": "CORS preflight successful"})

    if method == "GET" and path == "/unit_maintenance_bill":
        params = event.get("queryStringParameters") or {}
        
        unit_maintenance_id = params.get("unit_maintenance_id")
        if unit_maintenance_id:
            try:
                response_data = unit_maintenance_table.get_item(
                    Key={"unit_maintenance_id": unit_maintenance_id}
                )
                
                if 'Item' not in response_data:
                    return response(404, {
                        "success": False,
                        "message": "Unit maintenance bill not found"
                    })
                
                item = response_data['Item']
                building_id = item.get('building_id')
                user_id = params.get('user_id')
                
                if user_id:
                    if not check_user_has_any_role(user_id, building_id):
                        return response(403, {
                            "success": False,
                            "message": "You do not have access to view this bill"
                        })
                    
                    if not check_user_is_admin(user_id, building_id) and item.get('user_id') != user_id:
                        return response(403, {
                            "success": False,
                            "message": "You can only view your own bills"
                        })
                
                maintenance_id = item.get("maintenance_id")
                if maintenance_id:
                    maintenance_details = get_maintenance_details(maintenance_id)
                    if maintenance_details:
                        item["maintenance_details"] = maintenance_details
                
                return response(200, {
                    "success": True,
                    "data": item
                })
                
            except Exception as e:
                print(f"Error fetching unit maintenance bill: {str(e)}")
                return response(500, {
                    "success": False,
                    "message": "Failed to fetch unit maintenance bill",
                    "error": str(e)
                })
        
        building_id = params.get("building_id")
        user_id = params.get("user_id")
        
        if not building_id or not user_id:
            return response(400, {
                "success": False,
                "message": "building_id and user_id are required for listing bills"
            })
        
        if not check_user_has_any_role(user_id, building_id):
            return response(403, {
                "success": False,
                "message": "You do not have access to view bills for this building"
            })
        
        try:
            key_expr = Key("building_id").eq(building_id)
            
            filter_expressions = []
            expression_values = {}
            expression_names = {}
            
            if params.get("maintenance_id"):
                key_expr &= Key("sk").begins_with(f"MAINT#{params['maintenance_id']}")
            
            query_params = {
                "IndexName": "BuildingIndex",
                "KeyConditionExpression": key_expr
            }
            
            is_admin = check_user_is_admin(user_id, building_id)
            if not is_admin:
                filter_expressions.append("user_id = :user_id")
                expression_values[":user_id"] = user_id
            else:
                filter_user_id = params.get("filter_user_id")
                if filter_user_id:
                    filter_expressions.append("user_id = :filter_user_id")
                    expression_values[":filter_user_id"] = filter_user_id
            
            status = params.get("status")
            if status:
                filter_expressions.append("#status = :status")
                expression_values[":status"] = status
                expression_names["#status"] = "status"
            
            payment_status = params.get("payment_status")
            if payment_status:
                filter_expressions.append("payment_status = :payment_status")
                expression_values[":payment_status"] = payment_status
            
            wing = params.get("wing")
            if wing:
                filter_expressions.append("contains(wings, :wing)")
                expression_values[":wing"] = wing
            
            floor = params.get("floor")
            if floor:
                filter_expressions.append("floor = :floor")
                expression_values[":floor"] = str(floor)
            
            unit_no = params.get("unit_no")
            if unit_no:
                filter_expressions.append("unit_no = :unit_no")
                expression_values[":unit_no"] = unit_no
            
            if filter_expressions:
                query_params["FilterExpression"] = " AND ".join(filter_expressions)
                if expression_values:
                    query_params["ExpressionAttributeValues"] = expression_values
                if expression_names:
                    query_params["ExpressionAttributeNames"] = expression_names
            
            print(f"Query params: {json.dumps(query_params, default=str)}")
            
            res = unit_maintenance_table.query(**query_params)
            items = res.get("Items", [])
            
            
            while 'LastEvaluatedKey' in res:
                query_params['ExclusiveStartKey'] = res['LastEvaluatedKey']
                res = unit_maintenance_table.query(**query_params)
                items.extend(res.get('Items', []))
            
            
            for item in items:
                maintenance_id = item.get("maintenance_id")
                if maintenance_id:
                    maintenance_details = get_maintenance_details(maintenance_id)
                    if maintenance_details:
                        item["maintenance_details"] = maintenance_details
            
            return response(200, {
                "success": True,
                "count": len(items),
                "building_id": building_id,
                "requested_by": user_id,
                "is_admin": is_admin,
                "data": items
            })
            
        except Exception as e:
            print(f"Error fetching unit maintenance bills: {str(e)}")
            import traceback
            traceback.print_exc()
            return response(500, {
                "success": False,
                "message": "Failed to fetch unit maintenance bills",
                "error": str(e)
            })

    if method == "POST" and path == "/unit_maintenance_bill":
        try:
            body = json.loads(event.get("body") or "{}")
            
            print(f"POST body: {json.dumps(body, indent=2)}")
            
            required = [
                "building_id",
                "maintenance_id",
                "user_id", 
                "wings",
                "floor",
                "unit_no",
                "bill_items"
            ]
            
            missing = [f for f in required if f not in body]
            if missing:
                return response(400, {
                    "success": False,
                    "message": "Missing required fields",
                    "missing_fields": missing
                })
            
            building_id = body["building_id"]
            user_id = body["user_id"]
            
            if not check_user_is_admin(user_id, building_id):
                return response(403, {
                    "success": False,
                    "message": "Only building admin can create unit maintenance bills",
                    "user_id": user_id,
                    "building_id": building_id
                })
            
            if not isinstance(body["bill_items"], list) or len(body["bill_items"]) == 0:
                return response(400, {
                    "success": False,
                    "message": "bill_items must be a non-empty array"
                })
            
            bill_items, total_amount = calculate_bill_items(body["bill_items"])
            
            if total_amount <= 0:
                return response(400, {
                    "success": False,
                    "message": "Total amount must be greater than 0"
                })
            
            maintenance_details = get_maintenance_details(body["maintenance_id"])
            
            unit_id = f"UNIT-BILL-{uuid.uuid4().hex[:8].upper()}"
            now = datetime.utcnow().isoformat()
            
            item = {
                "unit_maintenance_id": unit_id,
                "building_id": building_id,
                "sk": f"MAINT#{body['maintenance_id']}",
                "maintenance_id": body["maintenance_id"],
                "user_id": body["user_id"], 
                "wings": body["wings"],
                "floor": str(body["floor"]),
                "unit_no": body["unit_no"],
                "bill_items": bill_items,
                "total_amount": float(total_amount) if total_amount % 1 != 0 else int(total_amount),
                "status": "pending",
                "payment_status": "unpaid",
                "created_at": now,
                "updated_at": now
            }
            
            if maintenance_details:
                item["maintenance_details"] = maintenance_details
            
            unit_maintenance_table.put_item(Item=item)
            
            return response(201, {
                "success": True,
                "message": "Unit maintenance bill created successfully",
                "data": item
            })
            
        except json.JSONDecodeError:
            return response(400, {
                "success": False,
                "message": "Invalid JSON in request body"
            })
        except Exception as e:
            print(f"Error creating unit maintenance bill: {str(e)}")
            return response(500, {
                "success": False,
                "message": "Failed to create unit maintenance bill",
                "error": str(e)
            })

    if method == "PATCH" and path.startswith("/unit_maintenance_bill/"):
        try:
            path_params = event.get("pathParameters") or {}
            unit_id = path_params.get("id")
            
            if not unit_id:
                return response(400, {
                    "success": False,
                    "message": "unit_maintenance_id missing in path"
                })
            
            body = json.loads(event.get("body") or "{}")
            user_id = body.get("user_id")
            
            if not user_id:
                return response(400, {
                    "success": False,
                    "message": "user_id is required for update"
                })
            
            existing_bill = unit_maintenance_table.get_item(
                Key={"unit_maintenance_id": unit_id}
            )
            
            if 'Item' not in existing_bill:
                return response(404, {
                    "success": False,
                    "message": "Unit maintenance bill not found"
                })
            
            building_id = existing_bill['Item'].get('building_id')
            
            if not check_user_is_admin(user_id, building_id):
                return response(403, {
                    "success": False,
                    "message": "Only building admin can update unit maintenance bills",
                    "user_id": user_id,
                    "building_id": building_id
                })
            
            update_expr = []
            values = {}
            
            allowed_fields = ["status", "payment_status", "wings", "floor", "unit_no", "user_id"]
            for field in allowed_fields:
                if field in body:
                    update_expr.append(f"{field} = :{field}")
                    values[f":{field}"] = body[field]
            
            if "bill_items" in body:
                if not isinstance(body["bill_items"], list):
                    return response(400, {
                        "success": False,
                        "message": "bill_items must be an array"
                    })
                
                bill_items, total_amount = calculate_bill_items(body["bill_items"])
                update_expr.append("bill_items = :bill_items")
                update_expr.append("total_amount = :total_amount")
                values[":bill_items"] = bill_items
                values[":total_amount"] = total_amount
            
            update_expr.append("updated_at = :updated_at")
            values[":updated_at"] = datetime.utcnow().isoformat()
            
            if not update_expr:
                return response(400, {
                    "success": False,
                    "message": "No fields to update"
                })
            
            unit_maintenance_table.update_item(
                Key={"unit_maintenance_id": unit_id},
                UpdateExpression="SET " + ", ".join(update_expr),
                ExpressionAttributeValues=values,
                ReturnValues="ALL_NEW"
            )
            
            updated_bill = unit_maintenance_table.get_item(
                Key={"unit_maintenance_id": unit_id}
            )
            
            item = updated_bill.get('Item', {})
            maintenance_id = item.get("maintenance_id")
            if maintenance_id:
                maintenance_details = get_maintenance_details(maintenance_id)
                if maintenance_details:
                    item["maintenance_details"] = maintenance_details
            
            return response(200, {
                "success": True,
                "message": "Unit maintenance bill updated successfully",
                "data": item
            })
            
        except Exception as e:
            print(f"Error updating unit maintenance bill: {str(e)}")
            return response(500, {
                "success": False,
                "message": "Failed to update unit maintenance bill",
                "error": str(e)
            })

    if method == "DELETE" and path.startswith("/unit_maintenance_bill/"):
        try:
            path_params = event.get("pathParameters") or {}
            unit_id = path_params.get("id")
            
            if not unit_id:
                return response(400, {
                    "success": False,
                    "message": "unit_maintenance_id missing in path"
                })
            
            body = json.loads(event.get("body") or "{}")
            user_id = body.get("user_id")  
            
            if not user_id:
                return response(400, {
                    "success": False,
                    "message": "user_id is required for deletion"
                })
            
            existing_bill = unit_maintenance_table.get_item(
                Key={"unit_maintenance_id": unit_id}
            )
            
            if 'Item' not in existing_bill:
                return response(404, {
                    "success": False,
                    "message": "Unit maintenance bill not found"
                })
            
            building_id = existing_bill['Item'].get('building_id')
            
            if not check_user_is_admin(user_id, building_id):
                return response(403, {
                    "success": False,
                    "message": "Only building admin can delete unit maintenance bills",
                    "user_id": user_id,
                    "building_id": building_id
                })
            
            bill_to_delete = existing_bill['Item']
            
            # Check payment status
            payment_status = bill_to_delete.get('payment_status', 'unpaid')
            if payment_status == 'paid':
                return response(400, {
                    "success": False,
                    "message": "Cannot delete paid bills. Refund payment first."
                })
            
            unit_maintenance_table.delete_item(
                Key={"unit_maintenance_id": unit_id}
            )
            
            return response(200, {
                "success": True,
                "message": "Unit maintenance bill deleted successfully",
                "deleted_bill": {
                    "unit_maintenance_id": unit_id,
                    "building_id": building_id,
                    "user_id": bill_to_delete.get('user_id'),
                    "maintenance_id": bill_to_delete.get('maintenance_id'),
                    "total_amount": bill_to_delete.get('total_amount')
                }
            })
            
        except Exception as e:
            print(f"Error deleting unit maintenance bill: {str(e)}")
            return response(500, {
                "success": False,
                "message": "Failed to delete unit maintenance bill",
                "error": str(e)
            })

    return response(404, {
        "success": False,
        "message": "Route not found"
    })