import streamlit as st
import requests
import pandas as pd
import json
from typing import Dict, Any

# Configure Streamlit page
st.set_page_config(
    page_title="Smart Employee Data Finder",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Backend API URL
BACKEND_URL = "https://streamlit-app-o3t7.onrender.com"

def call_backend_api(endpoint: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
    """Make API call to backend"""
    try:
        url = f"{BACKEND_URL}/{endpoint}"
        if data:
            response = requests.post(url, json=data, timeout=120)
        else:
            response = requests.get(url, timeout=120)
        
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"API Error: {response.status_code} - {response.text}")
            return None
    except requests.exceptions.ConnectionError:
        st.error("❌ Cannot connect to backend API. Please ensure the backend server is running on port 8000.")
        return None
    except requests.exceptions.Timeout:
        st.error("⏱️ Request timed out. Please try again.")
        return None
    except Exception as e:
        st.error(f"❌ Error: {str(e)}")
        return None

def display_results(data: Dict[str, Any]):
    """Display query results in a formatted way"""
    if not data or data.get("count", 0) == 0:
        st.warning("No employees found matching your criteria.")
        return
    
    # Display summary
    st.success(f"Found {data['count']} employee(s) matching your query!")
    
    # Show generated SQL (in expandable section)
    with st.expander("🔍 View Generated SQL Query"):
        st.code(data["generated_sql"], language="sql")
    
    # Display results as a table
    if data["data"]:
        df = pd.DataFrame(data["data"])
        
        # Format the table nicely - Remove custom styling that causes dark mode issues
        st.subheader("📊 Results")
        
        # Use Streamlit's native dataframe without custom styling
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Show individual employee cards for better visualization
        st.subheader("👥 Employee Details")
        
        # Create columns dynamically based on number of employees
        num_employees = len(data["data"])
        if num_employees <= 3:
            cols = st.columns(num_employees)
        else:
            cols = st.columns(3)
        
        for idx, employee in enumerate(data["data"]):
            col_idx = idx % len(cols)
            with cols[col_idx]:
                # Use Streamlit's native components instead of custom HTML/CSS
                with st.container():
                    st.markdown(f"**👤 {employee.get('name', 'N/A')}**")
                    st.write(f"**Experience:** {employee.get('experience_years', 'N/A')} years")
                    st.write(f"**Skills:** {employee.get('skills', 'N/A')}")
                    st.divider()
    else:
        st.error("No data returned from the query.")

# Alternative display function with better dark mode support
def display_results_alternative(data: Dict[str, Any]):
    """Alternative display with better dark mode compatibility"""
    if not data or data.get("count", 0) == 0:
        st.warning("No employees found matching your criteria.")
        return
    
    # Display summary
    st.success(f"Found {data['count']} employee(s) matching your query!")
    
    # Show generated SQL (in expandable section)
    with st.expander("🔍 View Generated SQL Query"):
        st.code(data["generated_sql"], language="sql")
    
    # Display results as a table
    if data["data"]:
        df = pd.DataFrame(data["data"])
        
        st.subheader("📊 Results")
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Show individual employee cards using Streamlit's metric and container components
        st.subheader("👥 Employee Details")
        
        # Create columns dynamically based on number of employees
        num_employees = len(data["data"])
        if num_employees <= 3:
            cols = st.columns(num_employees)
        else:
            cols = st.columns(3)
        
        for idx, employee in enumerate(data["data"]):
            col_idx = idx % len(cols)
            with cols[col_idx]:
                # Use a combination of metrics and info boxes
                with st.container(border=True):
                    st.markdown(f"### 👤 {employee.get('name', 'N/A')}")
                    
                    # Create two columns for metrics
                    metric_col1, metric_col2 = st.columns(2)
                    
                    with metric_col1:
                        st.metric(
                            label="Experience",
                            value=f"{employee.get('experience_years', 0)} years"
                        )
                    
                    with metric_col2:
                        # For skills, use an info box since it's text
                        st.info(f"**Skills:** {employee.get('skills', 'N/A')}")
    else:
        st.error("No data returned from the query.")

def main():
    # Header
    st.title("🔍 Smart Employee Data Finder")
    st.markdown("### Find employees using natural language queries!")
    
    # Sidebar with instructions and examples
    with st.sidebar:
        st.header("📋 How to Use")
        st.markdown("""
        Simply type your query in natural language, and the system will:
        1. Convert it to SQL automatically
        2. Search the employee database
        3. Display matching results
        """)
        
        st.header("💡 Example Queries")
        example_queries = [
            "Show me employees with more than 5 years experience",
            "Find employees who know Python",
            "List all employees with SQL skills",
            "Show employees with Python and more than 5 years experience",
            "Find employees with AWS experience",
            "Show all employees"
        ]
        
        for query in example_queries:
            if st.button(f"📝 {query}", key=query, use_container_width=True):
                st.session_state.example_query = query
    
    # Test connection button
    if st.button("🔗 Test Database Connection"):
        with st.spinner("Testing database connection..."):
            result = call_backend_api("test-db")
            if result and result.get("status") == "success":
                st.success("✅ Database connection successful!")
                if result.get("sample_data"):
                    st.write("Sample data from database:")
                    st.dataframe(pd.DataFrame(result["sample_data"]), use_container_width=True)
    
    st.divider()
    
    # Main query interface
    st.subheader("🎯 Enter Your Query")
    
    # Initialize current_query in session state if it doesn't exist
    if "current_query" not in st.session_state:
        st.session_state.current_query = ""
    
    # Check if an example query was clicked
    if "example_query" in st.session_state:
        st.session_state.current_query = st.session_state.example_query
        del st.session_state.example_query
    
    # Use the current query from session state
    query_input = st.text_area(
        "What would you like to know about our employees?",
        value=st.session_state.current_query,
        height=100,
        placeholder="e.g., Show me employees who have more than 5 years experience in Python",
        key="query_text_area"
    )
    
    # Update session state when user types
    if query_input != st.session_state.current_query:
        st.session_state.current_query = query_input
    
    # Search button
    col1, col2, col3 = st.columns([1, 1, 4])
    
    with col1:
        search_clicked = st.button("🔍 Search", type="primary", use_container_width=True)
    
    with col2:
        if st.button("🗑️ Clear", use_container_width=True):
            st.session_state.current_query = ""
            st.rerun()
    
    # Process query
    if search_clicked and query_input.strip():
        with st.spinner("🤖 Processing your query..."):
            result = call_backend_api("query", {"query": query_input.strip()})
            
            if result:
                if result.get("status") == "success":
                    # Use the alternative display function for better dark mode support
                    display_results_alternative(result)
                else:
                    st.error(f"❌ Query failed: {result.get('detail', 'Unknown error')}")
    
    elif search_clicked and not query_input.strip():
        st.warning("⚠️ Please enter a query first!")
    
    # Footer
    st.divider()
    st.markdown("""
    <div style="text-align: center; padding: 1rem;">
        <p>🚀 Powered by Streamlit, Supabase, and Groq API (DeepSeek)</p>
        <p>💡 Ask questions about employees in plain English!</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
