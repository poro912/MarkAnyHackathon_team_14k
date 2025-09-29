import boto3
import os
from botocore.exceptions import ClientError

# AWS 설정
AWS_REGION = 'us-east-1'
S3_BUCKET_NAME = 'utility-dll-storage'
DYNAMODB_TABLE_NAME = 'utility-builds'
BEDROCK_MODEL_ID = 'anthropic.claude-3-5-sonnet-20240620-v1:0'

# AWS 클라이언트 초기화
def get_s3_client():
    return boto3.client('s3', region_name=AWS_REGION)

def get_dynamodb_client():
    return boto3.resource('dynamodb', region_name=AWS_REGION)

def get_bedrock_client():
    return boto3.client('bedrock-runtime', region_name=AWS_REGION)

# S3 버킷 생성 (없으면)
def create_s3_bucket():
    s3 = get_s3_client()
    try:
        s3.create_bucket(
            Bucket=S3_BUCKET_NAME,
            CreateBucketConfiguration={'LocationConstraint': AWS_REGION}
        )
        print(f"S3 버킷 '{S3_BUCKET_NAME}' 생성 완료")
    except ClientError as e:
        if e.response['Error']['Code'] == 'BucketAlreadyExists':
            print(f"S3 버킷 '{S3_BUCKET_NAME}' 이미 존재")
        else:
            print(f"S3 버킷 생성 실패: {e}")

# DynamoDB 테이블 생성 (없으면)
def create_dynamodb_table():
    dynamodb = get_dynamodb_client()
    try:
        table = dynamodb.create_table(
            TableName=DYNAMODB_TABLE_NAME,
            KeySchema=[
                {'AttributeName': 'build_id', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'build_id', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        table.wait_until_exists()
        print(f"DynamoDB 테이블 '{DYNAMODB_TABLE_NAME}' 생성 완료")
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceInUseException':
            print(f"DynamoDB 테이블 '{DYNAMODB_TABLE_NAME}' 이미 존재")
        else:
            print(f"DynamoDB 테이블 생성 실패: {e}")

# 초기화 함수
def init_aws_resources():
    create_s3_bucket()
    create_dynamodb_table()
