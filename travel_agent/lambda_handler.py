import json

from .tasks import process_search_and_mail


def lambda_handler(event, context):
    """
    Lambda handler function to process SQS messages from Celery
    """
    try:
        print("Received event:", json.dumps(event, indent=2))

        # Process each record in the event
        for record in event["Records"]:
            # Celery message is in the body as a JSON string
            body = record["body"]
            print(f"undecoded body : {body}")
            # Extract the actual task arguments from Celery message
            # Celery message contains task args in the 'body' field as a base64 encoded string
            import base64

            task_body = json.loads(base64.b64decode(body).decode())
            print("Task body:", json.dumps(task_body, indent=2))

            celery_body = json.loads(base64.b64decode(task_body["body"]).decode())
            # Extract the three arguments: context, email, plan
            context, email, plan = celery_body[0]
            print(email)
            # Process the travel request directly
            process_search_and_mail(context, email, plan)

        return {
            "statusCode": 200,
            "body": json.dumps("Messages processed successfully"),
        }
    except Exception as e:
        print(f"Error processing messages: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps(f"Error processing messages: {str(e)}"),
        }
