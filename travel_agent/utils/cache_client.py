import boto3
import json
from datetime import datetime
from decimal import Decimal

def convert_floats_to_decimal(obj):
    if isinstance(obj, float):
        return Decimal(str(obj))  # float을 문자열로 바꾼 뒤 Decimal로
    elif isinstance(obj, dict):
        return {k: convert_floats_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_floats_to_decimal(i) for i in obj]
    else:
        return obj
class CacheClient:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CacheClient, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        self.dynamodb = boto3.resource('dynamodb')
        self.table = self.dynamodb.Table('travel-agent-cache')

    def get_conversation_history(self, user_id: str) -> dict:
        """사용자의 대화 기록을 가져옵니다."""
        try:
            response = self.table.get_item(Key={'user_id': user_id})
            if 'Item' in response:
                return response['Item'].get('messages', {})
            return {}
        except Exception as e:
            print(f"Error getting conversation history: {e}")
            return {}

    def add_message(self, user_id: str, message: dict):
        """사용자의 대화 기록에 메시지를 추가합니다."""
        try:
            # 현재 메시지 가져오기
            current_messages = self.get_conversation_history(user_id)
            
            # 메시지 타입에 따라 저장
            message_type = message.get('type', 'message')
            if message_type not in current_messages:
                current_messages[message_type] = []
            
            # 새 메시지 추가
            current_messages[message_type].append({
                **message,
                'timestamp': datetime.now().isoformat()
            })
            current_messages = convert_floats_to_decimal(current_messages)
            
            # DynamoDB에 저장
            self.table.put_item(
                Item={
                    'user_id': user_id,
                    'messages': current_messages,
                    'updated_at': datetime.now().isoformat()
                }
            )
        except Exception as e:
            print(f"Error adding message: {e}")

    def clear_conversation(self, user_id: str):
        """사용자의 대화 기록을 삭제합니다."""
        try:
            self.table.delete_item(Key={'user_id': user_id})
        except Exception as e:
            print(f"Error clearing conversation: {e}")

cache_client = CacheClient() 