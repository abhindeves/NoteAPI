# app/app.py
import os
import uuid
import json
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Optional AWS DynamoDB; falback to simple sqlite for local/dev
USE_DYNAMODB = os.getenv("USE_DYNAMODB", "false").lower() == "true"
DYNAMO_TABLE = os.getenv("DYNAMO_TABLE", "NotesTable")

if USE_DYNAMODB:
    import boto3
    dynamo = boto3.resource("dynamodb")
    table = dynamo.Table(DYNAMO_TABLE)
else:
    import sqlite3
    # SQLite setup
    DB_PATH = os.getenv("SQLITE_PATH", os.path.join(os.path.dirname(os.path.dirname(__file__)), "notes.db"))

    if not os.path.exists(DB_PATH):
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute(
                "CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY AUTOINCREMENT, display_id INTEGER, title TEXT, content TEXT, summary TEXT, created_at TEXT)"
            )
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_display_id ON notes(display_id)")
            conn.commit()

    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cur = conn.cursor()
    # Add display_id if not present
    cur.execute("PRAGMA table_info(notes)")
    columns = [row[1] for row in cur.fetchall()]
    if 'display_id' not in columns:
        cur.execute("ALTER TABLE notes ADD COLUMN display_id INTEGER")
    cur.execute(
        "CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY AUTOINCREMENT, display_id INTEGER, title TEXT, content TEXT, summary TEXT, created_at TEXT)"
    )
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_display_id ON notes(display_id)")
    conn.commit()

from mangum import Mangum
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="FastAPI Notes (Lambda container)")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class NoteIn(BaseModel):
    title: str | None = None
    content: str

class NoteOut(BaseModel):
    id: int
    display_id: int
    title: str | None
    content: str
    summary: str | None
    created_at: str


def generate_summary(text: str) -> str:
    # Simple lightweight summary: first 120 chars + ellipsis
    s = text.strip()
    if len(s) <= 120:
        return s
    return s[:117].rsplit(" ", 1)[0] + "..."

@app.post("/notes", response_model=NoteOut)
def create_note(payload: NoteIn):
    created_at = datetime.now(timezone.utc).isoformat()
    summary = generate_summary(payload.content)
    if USE_DYNAMODB:
        note_id = str(uuid.uuid4())
        item = {"id": note_id, "display_id": None, "title": payload.title or "", "content": payload.content, "summary": summary, "created_at": created_at}
        table.put_item(Item=item)
        return item
    else:
        cur.execute("SELECT COALESCE(MAX(display_id), 0) + 1 FROM notes")
        next_display_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO notes (display_id, title, content, summary, created_at) VALUES (?, ?, ?, ?, ?)",
            (next_display_id, payload.title or "", payload.content, summary, created_at),
        )
        conn.commit()
        note_id = cur.lastrowid
        item = {"id": note_id, "display_id": next_display_id, "title": payload.title or "", "content": payload.content, "summary": summary, "created_at": created_at}
        return item

@app.get("/notes")
def list_notes():
    if USE_DYNAMODB:
        resp = table.scan()
        items = resp.get("Items", [])
    else:
        cur.execute("SELECT id, display_id, title, content, summary, created_at FROM notes ORDER BY created_at DESC")
        rows = cur.fetchall()
        items = [
            {"id": r[0], "display_id": r[1], "title": r[2], "content": r[3], "summary": r[4], "created_at": r[5]} for r in rows
        ]
    return items

@app.get("/notes/{display_id}")
def get_note(display_id: int):
    if USE_DYNAMODB:
        raise HTTPException(status_code=400, detail="display_id not supported in DynamoDB mode")
    else:
        cur.execute("SELECT id, display_id, title, content, summary, created_at FROM notes WHERE display_id = ?", (display_id,))
        r = cur.fetchone()
        if not r:
            raise HTTPException(status_code=404, detail="Note not found")
        return {"id": r[0], "display_id": r[1], "title": r[2], "content": r[3], "summary": r[4], "created_at": r[5]}
    
    
@app.put("/notes/{display_id}")
def update_note(display_id: int, payload: NoteIn):
    if USE_DYNAMODB:
        raise HTTPException(status_code=400, detail="display_id not supported in DynamoDB mode")
    else:
        cur.execute("SELECT id FROM notes WHERE display_id = ?", (display_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Note not found")
        note_id = row[0]
        cur.execute(
            "UPDATE notes SET title = ?, content = ?, summary = ? WHERE display_id = ?",
            (payload.title or "", payload.content, generate_summary(payload.content), display_id),
        )
        conn.commit()
        cur.execute("SELECT id, display_id, title, content, summary, created_at FROM notes WHERE display_id = ?", (display_id,))
        r = cur.fetchone()
        return {"id": r[0], "display_id": r[1], "title": r[2], "content": r[3], "summary": r[4], "created_at": r[5]}

@app.delete("/notes/{display_id}")
def delete_note(display_id: int):
    if USE_DYNAMODB:
        raise HTTPException(status_code=400, detail="display_id not supported in DynamoDB mode")
    else:
        cur.execute("DELETE FROM notes WHERE display_id = ?", (display_id,))
        conn.commit()
    return {"status": "deleted", "display_id": display_id}


# For local dev: uvicorn app:app --reload
# For Lambda container: expose `handler` for the AWS Lambda runtime
handler = Mangum(app)
