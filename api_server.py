from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.responses import StreamingResponse
import sqlite3
import requests
import json

# 🔄 Import your custom LLaMA SQL logic
from llama_sql_generator import generate_sql_with_llama, clean_sql, get_all_table_columns

app = FastAPI()

# 🎯 Request model
class QuestionRequest(BaseModel):
    question: str

# ✅ /ask endpoint — for SQL generation + execution
@app.post("/ask")
def ask_question(request: QuestionRequest):
    try:
        # 1. Generate SQL from question
        raw_sql = generate_sql_with_llama(request.question)
        sql_query = clean_sql(raw_sql)

        # 2. Allow only SELECT or WITH queries
        if not sql_query.strip().lower().startswith(("select", "with")):
            raise ValueError("Only SELECT queries are allowed.")

        # 3. Connect to SQLite DB
        conn = sqlite3.connect('ecommerce.db')
        cursor = conn.cursor()

        # 4. Run SQL
        cursor.execute(sql_query)
        rows = cursor.fetchall()

        # 5. Format results
        columns = [desc[0] for desc in cursor.description]
        result = [dict(zip(columns, row)) for row in rows]

        return {
            "question": request.question,
            "sql_query": sql_query,
            "result": result
        }

    except Exception as e:
        return {
            "error": f"{type(e).__name__}: {str(e)}",
            "generated_sql": locals().get("sql_query", "N/A")
        }

    finally:
        try:
            conn.close()
        except:
            pass

# ✅ Streaming helper (token-by-token from Groq)
def stream_llama_response(prompt: str):
    import os
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        yield "Error: GROQ_API_KEY is not set in environment."
        return

    from groq import Groq
    client = Groq(api_key=api_key)
    
    stream = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.3-70b-versatile",
        stream=True
    )

    def event_stream():
        for chunk in stream:
            content = chunk.choices[0].delta.content
            if content:
                yield content

    return event_stream()

# ✅ /stream endpoint — for typing-style natural language answer
@app.post("/stream")
def stream_question(request: QuestionRequest):
    try:
        # Add table schema to help LLaMA
        schema = get_all_table_columns()

        prompt = f"""You are a helpful assistant. Answer the user's question clearly.

Database Schema:
{schema}

Question: {request.question}
Answer:"""

        return StreamingResponse(
            stream_llama_response(prompt),
            media_type="text/plain"
        )

    except Exception as e:
        return {"error": str(e)}