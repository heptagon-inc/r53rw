import os
import json
import slack
import boto3


ssm_client = boto3.client('ssm')
response = ssm_client.get_parameter(
    Name='r53rw_SLACK_ACCESS_TOKEN',
    WithDecryption=True
)
SLACK_API_TOKEN = response['Parameter']['Value']


slack_client = slack.WebClient(token=SLACK_API_TOKEN)


def lambda_handler(event, context):
    messages = {
        'channel': '#_notice_ops',
        'text': 'CodeBuild Notification',
        'username': 'api.cloud3rs.io',
        'icon_emoji': ':dart:',
        'attachments': [
            {
                'color': '#808080',
                'blocks': [
                    {
                        'type': 'section',
                        'text': {
                            'type': 'mrkdwn',
                            'text': f"project-name - {event['detail']['project-name']}\nbuild-id - {event['detail']['build-id']}\nbuild-status - {event['detail']['build-status']}"
                        }
                    },
                ]
            }
        ]
    }
    resp = slack_client.chat_postMessage(**messages)
    print(resp)
    return True
