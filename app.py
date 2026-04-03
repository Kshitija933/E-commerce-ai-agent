import streamlit as st
import sqlite3
import pandas as pd
import os
import subprocess
from llama_sql_generator import generate_sql_with_llama, clean_sql

# Page configuration
st.set_page_config(page_title="E-commerce AI Agent", page_icon="🛒", layout="wide")

st.title("🛒 E-commerce Data Agent")
st.markdown("Ask natural language questions to interact dynamically with your E-commerce metrics database.")

# Ensure DB is created for Cloud environment (since it's in .gitignore)
if not os.path.exists("ecommerce.db"):
    with st.spinner("Initializing database from Excel source files..."):
        try:
            import load_data_to_db
            st.success("Database initialized successfully!")
        except Exception as e:
            st.error(f"Failed to initialize database: {e}")

from dotenv import load_dotenv
load_dotenv()

# Sidebar config
st.sidebar.header("⚙️ Agent Configuration")
st.sidebar.success("Powered by Groq Cloud (Llama 3)")

api_key = ""
try:
    # Try getting from Streamlit secrets first (for cloud)
    api_key = st.secrets.get("GROQ_API_KEY", "")
except FileNotFoundError:
    pass

# Try getting from environment variable (local .env)
if not api_key:
    api_key = os.environ.get("GROQ_API_KEY", "")

# Fallback: Ask user
if not api_key:
    api_key = st.sidebar.text_input("Enter Groq API Key:", type="password")
    if not api_key:
        st.sidebar.warning("API key is required. Get one for free at [console.groq.com](https://console.groq.com)")

st.sidebar.markdown("---")
st.sidebar.markdown("**Sample Questions**")
st.sidebar.markdown("- What is my total sales?")
st.sidebar.markdown("- Which product had the highest CPC?")
st.sidebar.markdown("- Show top 5 products by ad sales.")

# Chat history state
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        if "sql" in msg:
            with st.expander("Show SQL Code"):
                st.code(msg["sql"], language="sql")
        if "data" in msg:
            st.dataframe(msg["data"])

# Chat input
if prompt := st.chat_input("E.g., What is the average return on ad spend?"):
    # Append User Message
    st.chat_message("user").write(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Process
    with st.chat_message("assistant"):
        if not api_key:
            err = "Please enter a Groq API key in the sidebar configuration to use cloud."
            st.error(err)
            st.session_state.messages.append({"role": "assistant", "content": err})
            st.stop()
            
        with st.spinner("Generating SQL query using AI..."):
            sql_query = generate_sql_with_llama(prompt, api_key=api_key)
            
        if sql_query.startswith("-- ❌"):
            st.error(sql_query)
            st.session_state.messages.append({"role": "assistant", "content": f"Error: {sql_query}"})
        elif not sql_query.strip().lower().startswith(("select", "with")):
            err = "The model generated a non-SELECT query which was blocked for database security."
            st.error(err)
            with st.expander("Show Generated Text"):
                st.write(sql_query)
            st.session_state.messages.append({"role": "assistant", "content": err})
        else:
            st.write("Here is the requested data:")
            with st.expander("Show Executed SQL", expanded=False):
                st.code(sql_query, language="sql")
                
            try:
                # Query Execution
                conn = sqlite3.connect('ecommerce.db')
                df = pd.read_sql_query(sql_query, conn)
                conn.close()
                
                st.dataframe(df)
                # Save to history
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": "Here is the requested data:",
                    "sql": sql_query,
                    "data": df
                })
            except Exception as e:
                st.error(f"Error executing SQL query on the database: {e}")
                st.session_state.messages.append({"role": "assistant", "content": f"SQL DB Error: {e}"})
