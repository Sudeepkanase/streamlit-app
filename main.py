from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import psycopg2
import os
from dotenv import load_dotenv
from groq import Groq
import json
import re

# Load environment variables
load_dotenv()

app = FastAPI(title="Smart Employee Data Finder API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database connection
def get_db_connection():
    try:
        conn = psycopg2.connect(
            host=os.getenv("SUPABASE_HOST"),
            port=os.getenv("SUPABASE_PORT"),
            database=os.getenv("SUPABASE_DB"),
            user=os.getenv("SUPABASE_USER"),
            password=os.getenv("SUPABASE_PASSWORD")
        )
        return conn
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")

# Groq client
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

class QueryRequest(BaseModel):
    query: str

def generate_fallback_query(natural_language_query: str) -> str:
    """Generate SQL query using pattern matching as fallback"""
    query_lower = natural_language_query.lower()
    
    # Pattern matching for common queries
    if ("all employees" in query_lower or "show all" in query_lower) and not any(skill in query_lower for skill in ["sql", "python", "java", "aws", "javascript"]):
        return "SELECT * FROM employees;"
    
    elif "sql" in query_lower and ("skills" in query_lower or "skill" in query_lower or "know" in query_lower or "with" in query_lower):
        return "SELECT * FROM employees WHERE skills ILIKE '%SQL%';"
    
    elif "javascript" in query_lower:  # Check JavaScript first (more specific)
        return "SELECT * FROM employees WHERE skills ILIKE '%JavaScript%';"
    
    elif "java" in query_lower and "javascript" not in query_lower:  # Then check Java (but not JavaScript)
        return "SELECT * FROM employees WHERE (skills ILIKE '%Java,%' OR skills ILIKE '%Java %' OR skills LIKE '%Java' OR skills LIKE 'Java%');"
    
    elif "python" in query_lower and ("experience" in query_lower or "years" in query_lower):
        # Extract number if present
        numbers = re.findall(r'\d+', natural_language_query)
        if numbers:
            years = numbers[0]
            return f"SELECT * FROM employees WHERE skills ILIKE '%Python%' AND experience_years > {years};"
        else:
            return "SELECT * FROM employees WHERE skills ILIKE '%Python%';"
    
    elif "more than" in query_lower and "years" in query_lower:
        numbers = re.findall(r'\d+', natural_language_query)
        if numbers:
            years = numbers[0]
            return f"SELECT * FROM employees WHERE experience_years > {years};"
    
    elif "python" in query_lower:
        return "SELECT * FROM employees WHERE skills ILIKE '%Python%';"
    
    elif "sql" in query_lower:
        return "SELECT * FROM employees WHERE skills ILIKE '%SQL%';"
    
    elif "aws" in query_lower:
        return "SELECT * FROM employees WHERE skills ILIKE '%AWS%';"
    
    else:
        return "SELECT * FROM employees;"

def extract_sql_from_response(response_text: str) -> str:
    """Extract clean SQL query from AI response"""
    # Remove any markdown code blocks
    response_text = re.sub(r'```sql\s*', '', response_text, flags=re.IGNORECASE)
    response_text = re.sub(r'```\s*', '', response_text)
    
    # Try to find a complete SELECT statement
    # This pattern looks for SELECT...FROM...optional WHERE...optional semicolon
    sql_patterns = [
        # Pattern 1: Complete SELECT statement
        r'(SELECT\s+[^;]*FROM\s+employees[^;]*(?:WHERE[^;]*)?);?',
        # Pattern 2: Just SELECT * FROM employees variations
        r'(SELECT\s+\*\s+FROM\s+employees(?:\s+WHERE[^;]*)?);?',
        # Pattern 3: Any SELECT statement that ends with semicolon
        r'(SELECT[^;]+;)',
        # Pattern 4: Any SELECT statement at the end of text
        r'(SELECT.*?)(?:\n|$)',
    ]
    
    for pattern in sql_patterns:
        matches = re.findall(pattern, response_text, re.IGNORECASE | re.DOTALL)
        if matches:
            sql_query = matches[0].strip()
            # Clean up the match
            sql_query = re.sub(r'\s+', ' ', sql_query)  # Normalize whitespace
            sql_query = sql_query.rstrip(';')  # Remove trailing semicolon
            
            # Validate it looks like a proper SELECT statement
            if sql_query.upper().startswith('SELECT') and 'FROM employees' in sql_query.upper():
                return sql_query + ';'
    
    # If no pattern matches, raise an exception
    raise Exception(f"Could not extract valid SQL from response: {response_text[:200]}...")

def generate_sql_query(natural_language_query: str) -> str:
    """Convert natural language to SQL query using Groq API"""
    
    schema_info = """
    Table: employees
    Columns:
    - id (SERIAL PRIMARY KEY)
    - name (TEXT) - Employee name
    - experience_years (INT) - Years of experience
    - skills (TEXT) - Comma-separated skills like 'Python, SQL', 'Java, React'
    
    Sample data:
    - Alice, 6 years, 'Python, SQL'
    - Bob, 3 years, 'Java, React'  
    - Charlie, 7 years, 'Python, JavaScript, AWS'
    """
    
    prompt = f"""
    You are a SQL query generator. Convert the natural language query to a PostgreSQL SELECT statement.

    Database Schema:
    {schema_info}
    
    Natural Language Query: "{natural_language_query}"
    
    CRITICAL RULES:
    1. ONLY return a SELECT statement - no explanations, no reasoning, no extra text
    2. Use ILIKE for case-insensitive text matching on skills column
    3. Skills are stored as comma-separated values like 'Python, SQL' or 'Java, React'
    4. BE PRECISE with skill matching - avoid partial matches that cause confusion
    5. For Java (NOT JavaScript): Use pattern that matches 'Java' but NOT 'JavaScript'
    6. Start with SELECT and end with semicolon
    7. Do not include any text before or after the SQL query
    
    IMPORTANT SKILL DISTINCTIONS:
    - "Java" should match "Java" but NOT "JavaScript" 
    - "JavaScript" should match "JavaScript" only
    - Use word boundaries or comma separation for precision
    
    Examples:
    Query: "employees with more than 5 years experience"
    Answer: SELECT * FROM employees WHERE experience_years > 5;
    
    Query: "employees who know Python"
    Answer: SELECT * FROM employees WHERE skills ILIKE '%Python%';
    
    Query: "employees who know Java" (NOT JavaScript)
    Answer: SELECT * FROM employees WHERE (skills ILIKE '%Java,%' OR skills ILIKE '%Java %' OR skills LIKE '%Java' OR skills LIKE 'Java%');
    
    Query: "employees who know JavaScript"
    Answer: SELECT * FROM employees WHERE skills ILIKE '%JavaScript%';
    
    Query: "list all employees with SQL skills"
    Answer: SELECT * FROM employees WHERE skills ILIKE '%SQL%';
    
    Query: "show all employees"
    Answer: SELECT * FROM employees;
    
    Now convert this query: "{natural_language_query}"
    """
    
    try:
        completion = client.chat.completions.create(
            model="deepseek-r1-distill-llama-70b",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.1,
            max_tokens=100  # Reduced to encourage shorter responses
        )
        
        response_text = completion.choices[0].message.content.strip()
        print(f"Raw AI response: {response_text}")  # Debug log
        
        # Extract SQL from the response
        sql_query = extract_sql_from_response(response_text)
        print(f"Extracted SQL: {sql_query}")  # Debug log
        
        return sql_query
        
    except Exception as e:
        # If AI fails, use fallback pattern matching
        print(f"AI SQL generation failed: {str(e)}, using fallback...")
        fallback_query = generate_fallback_query(natural_language_query)
        print(f"Fallback SQL: {fallback_query}")  # Debug log
        return fallback_query

def execute_query(sql_query: str):
    """Execute SQL query and return results"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql_query)
        
        # Get column names
        columns = [desc[0] for desc in cursor.description]
        
        # Fetch results
        rows = cursor.fetchall()
        
        # Convert to list of dictionaries
        results = []
        for row in rows:
            results.append(dict(zip(columns, row)))
            
        return {
            "sql_query": sql_query,
            "results": results,
            "count": len(results)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query execution failed: {str(e)}")
    finally:
        cursor.close()
        conn.close()

@app.get("/")
async def root():
    return {"message": "Smart Employee Data Finder API is running!"}

@app.post("/query")
async def process_query(request: QueryRequest):
    """Process natural language query and return employee data"""
    try:
        # Generate SQL from natural language
        sql_query = generate_sql_query(request.query)
        
        # Execute the query
        result = execute_query(sql_query)
        
        return {
            "status": "success",
            "natural_query": request.query,
            "generated_sql": result["sql_query"],
            "data": result["results"],
            "count": result["count"]
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@app.get("/test-db")
async def test_database():
    """Test database connection and return sample data"""
    try:
        result = execute_query("SELECT * FROM employees LIMIT 5")
        return {
            "status": "success",
            "message": "Database connection successful",
            "sample_data": result["results"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database test failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)