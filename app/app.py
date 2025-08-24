# app/app.py
import os
import uuid
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Depends, Request
from pydantic import BaseModel
import boto3
from botocore.exceptions import ClientError
from mangum import Mangum
from fastapi.middleware.cors import CORSMiddleware

# --- Environment and DynamoDB Setup (with new schema) ---
DYNAMO_TABLE = os.getenv("DYNAMO_TABLE", "NotesTable")
REGION = os.getenv("AWS_REGION", "ap-south-1")

dynamo_client = boto3.client("dynamodb", region_name=REGION)
dynamo_resource = boto3.resource("dynamodb", region_name=REGION)

def create_notes_table():
    try:
        dynamo_client.create_table(
            TableName=DYNAMO_TABLE,
            KeySchema=[
                {"AttributeName": "userId", "KeyType": "HASH"},  # Partition key
                {"AttributeName": "noteId", "KeyType": "RANGE"}  # Sort key
            ],
            AttributeDefinitions=[
                {"AttributeName": "userId", "AttributeType": "S"},
                {"AttributeName": "noteId", "AttributeType": "S"}
            ],
            BillingMode="PAY_PER_REQUEST"
        )
        print(f"Creating table {DYNAMO_TABLE} with composite key...")
        waiter = dynamo_client.get_waiter("table_exists")
        waiter.wait(TableName=DYNAMO_TABLE)
        print(f"Table {DYNAMO_TABLE} is ready.")
    except ClientError as e:
        if e.response['Error']['Code'] == "ResourceInUseException":
            print(f"Table {DYNAMO_TABLE} already exists.")
        else:
            raise

def ensure_table_exists():
    try:
        dynamo_client.describe_table(TableName=DYNAMO_TABLE)
        print(f"Table {DYNAMO_TABLE} already exists.")
    except dynamo_client.exceptions.ResourceNotFoundException:
        create_notes_table()

ensure_table_exists()
table = dynamo_resource.Table(DYNAMO_TABLE)
print(f"Using DynamoDB table: {table.table_name}")

# --- FastAPI App and Models ---
app = FastAPI(title="Secure FastAPI Notes (DynamoDB)", root_path="/dev")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class NoteIn(BaseModel):
    title: str | None = None
    content: str

class NoteOut(BaseModel):
    noteId: str
    userId: str
    title: str | None
    content: str
    summary: str | None
    created_at: str

# --- Authentication Dependency ---
def get_current_user(request: Request) -> str:
    """
    Extracts the user ID from the request context set by the API Gateway Cognito Authorizer.
    The user ID is typically available under 'claims' -> 'sub'.
    """
    try:
        # The authorizer context is passed in the request scope by Mangum
        authorizer_data = request.scope.get("aws.event", {}).get("requestContext", {}).get("authorizer", {})
        user_id = authorizer_data.get("claims", {}).get("sub")
        if not user_id:
            raise HTTPException(status_code=403, detail="User ID not found in token")
        return user_id
    except Exception:
        raise HTTPException(status_code=403, detail="Could not validate user credentials")

# --- Helper Function ---
def generate_summary(text: str) -> str:
    s = text.strip()
    return s if len(s) <= 120 else s[:117].rsplit(" ", 1)[0] + "..."

# --- API Endpoints (Refactored for AuthZ) ---

@app.post("/notes", response_model=NoteOut)
def create_note(payload: NoteIn, user_id: str = Depends(get_current_user)):
    note_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    summary = generate_summary(payload.content)
    item = {
        "userId": user_id,
        "noteId": note_id,
        "title": payload.title or "",
        "content": payload.content,
        "summary": summary,
        "created_at": created_at
    }
    table.put_item(Item=item)
    return item

@app.get("/notes", response_model=list[NoteOut])
def list_notes(user_id: str = Depends(get_current_user)):
    """
    Lists notes for the authenticated user. Uses query instead of scan.
    """
    from boto3.dynamodb.conditions import Key
    
    resp = table.query(
        KeyConditionExpression=Key('userId').eq(user_id)
    )
    items = resp.get("Items", [])
    return sorted(items, key=lambda x: x['created_at'], reverse=True)


@app.get("/notes/{note_id}", response_model=NoteOut)
def get_note(note_id: str, user_id: str = Depends(get_current_user)):
    resp = table.get_item(Key={"userId": user_id, "noteId": note_id})
    item = resp.get("Item")
    if not item:
        raise HTTPException(status_code=404, detail="Note not found")
    return item

@app.put("/notes/{note_id}", response_model=NoteOut)
def update_note(note_id: str, payload: NoteIn, user_id: str = Depends(get_current_user)):
    # First, ensure the note exists and belongs to the user
    resp = table.get_item(Key={"userId": user_id, "noteId": note_id})
    item = resp.get("Item")
    if not item:
        raise HTTPException(status_code=404, detail="Note not found")
    
    summary = generate_summary(payload.content)
    updated_item = {
        **item,
        "title": payload.title or "",
        "content": payload.content,
        "summary": summary
    }
    table.put_item(Item=updated_item)
    return updated_item

@app.delete("/notes/{note_id}")
def delete_note(note_id: str, user_id: str = Depends(get_current_user)):
    # The key includes the userId, ensuring users can only delete their own notes
    table.delete_item(Key={"userId": user_id, "noteId": note_id})
    return {"status": "deleted", "noteId": note_id}

# --- AWS Lambda Handler ---
handler = Mangum(app)