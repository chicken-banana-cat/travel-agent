import json
import os
from travel_agent.tasks import process_search_and_mail

def lambda_handler(event, context):
    """
    AWS Lambda handler for processing Celery tasks
    """
    try:
        # Parse the SQS message
        for record in event['Records']:
            message_body = json.loads(record['body'])
            
            # Extract task parameters
            context = message_body.get('context', {})
            email = message_body.get('email', '')
            plan = message_body.get('plan', {})
            
            # Process the task
            process_search_and_mail(context, email, plan)
            
        return {
            'statusCode': 200,
            'body': json.dumps('Task processed successfully')
        }
    except Exception as e:
        print(f"Error processing task: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error processing task: {str(e)}')
        } 