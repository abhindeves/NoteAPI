# app/app.py
import os
import uuid
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import boto3
from botocore.exceptions import ClientError
from mangum import Mangum
from fastapi.middleware.cors import CORSMiddleware

# Environment
DYNAMO_TABLE = os.getenv("DYNAMO_TABLE", "NotesTable")
REGION = os.getenv("AWS_REGION", "ap-south-1")

# Initialize DynamoDB client and resource
dynamo_client = boto3.client("dynamodb", region_name=REGION)
dynamo_resource = boto3.resource("dynamodb", region_name=REGION)

# Function to create table if it doesn't exist
def create_notes_table():
    try:
        dynamo_client.create_table(
            TableName=DYNAMO_TABLE,
            KeySchema=[
                {"AttributeName": "id", "KeyType": "HASH"}  # Partition key
            ],
            AttributeDefinitions=[
                {"AttributeName": "id", "AttributeType": "S"}
            ],
            BillingMode="PAY_PER_REQUEST"  # On-demand billing
        )
        print(f"Creating table {DYNAMO_TABLE}...")
        waiter = dynamo_client.get_waiter("table_exists")
        waiter.wait(TableName=DYNAMO_TABLE)
        print(f"Table {DYNAMO_TABLE} is ready.")
    except ClientError as e:
        if e.response['Error']['Code'] == "ResourceInUseException":
            print(f"Table {DYNAMO_TABLE} already exists.")
        else:
            raise

# Ensure the table exists at startup
def ensure_table_exists():
    try:
        dynamo_client.describe_table(TableName=DYNAMO_TABLE)
        print(f"Table {DYNAMO_TABLE} already exists.")
    except dynamo_client.exceptions.ResourceNotFoundException:
        create_notes_table()

ensure_table_exists()

# Reference the DynamoDB table
table = dynamo_resource.Table(DYNAMO_TABLE)
print(f"Using DynamoDB table: {table.table_name}")

# FastAPI app
app = FastAPI(title="FastAPI Notes (DynamoDB)")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Pydantic models
class NoteIn(BaseModel):
    title: str | None = None
    content: str

class NoteOut(BaseModel):
    id: str
    title: str | None
    content: str
    summary: str | None
    created_at: str

# Simple summary generator
def generate_summary(text: str) -> str:
    s = text.strip()
    if len(s) <= 120:
        return s
    return s[:117].rsplit(" ", 1)[0] + "..."

# Create a note
@app.post("/notes", response_model=NoteOut)
def create_note(payload: NoteIn):
    note_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    summary = generate_summary(payload.content)
    item = {
        "id": note_id,
        "title": payload.title or "",
        "content": payload.content,
        "summary": summary,
        "created_at": created_at
    }
    table.put_item(Item=item)
    return item

# List all notes
@app.get("/notes", response_model=list[NoteOut])
def list_notes():
    resp = table.scan()
    items = resp.get("Items", [])
    return items

# Get note by id
@app.get("/notes/{note_id}", response_model=NoteOut)
def get_note(note_id: str):
    resp = table.get_item(Key={"id": note_id})
    item = resp.get("Item")
    if not item:
        raise HTTPException(status_code=404, detail="Note not found")
    return item

# Update note by id
@app.put("/notes/{note_id}", response_model=NoteOut)
def update_note(note_id: str, payload: NoteIn):
    resp = table.get_item(Key={"id": note_id})
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

# Delete note by id
@app.delete("/notes/{note_id}")
def delete_note(note_id: str):
    table.delete_item(Key={"id": note_id})
    return {"status": "deleted", "id": note_id}

# AWS Lambda handler
handler = Mangum(app)
