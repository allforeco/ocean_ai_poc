#!/usr/bin/env python3
"""
Ocean AI POC - Streamlit Interface
Interactive web interface for ocean sustainability queries using RAG system.
"""

import streamlit as st
import argparse
import sys
import os
from typing import Dict, Any, Optional
import time

# Add the current directory to Python path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from rag_retriever import OceanRAGRetriever

def init_session_state():
    """Initialize Streamlit session state variables"""
    if 'retriever' not in st.session_state:
        st.session_state.retriever = None
    if 'query_history' not in st.session_state:
        st.session_state.query_history = []
    if 'config_loaded' not in st.session_state:
        st.session_state.config_loaded = False

def load_retriever(config_path: str) -> bool:
    """Load the RAG retriever with error handling"""
    try:
        st.session_state.retriever = OceanRAGRetriever(config_path)
        st.session_state.config_loaded = True
        return True
    except Exception as e:
        st.error(f"Failed to load configuration: {e}")
        return False

def format_sources(sources: list) -> str:
    """Format sources for display"""
    if not sources:
        return "No sources found."
    
    formatted = []
    for i, source in enumerate(sources, 1):
        geographic = source.get('geographic_focus', 'N/A')
        topics = ', '.join(source.get('topics', [])) if source.get('topics') else 'N/A'
        
        source_text = f"""
**{i}. {source['filename']}**
- Organization: {source['organization']}
- Document Type: {source['doc_type']}
- Similarity Score: {source['similarity_score']}
- Geographic Focus: {geographic}
- Topics: {topics}
"""
        formatted.append(source_text)
    
    return "\n".join(formatted)

def display_query_result(result: Dict[str, Any]):
    """Display the query result in a formatted way"""
    
    # Main answer
    st.markdown("### 🌊 Answer")
    st.markdown(result['answer'])
    
    # Metadata
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Results Found", result['metadata']['results_count'])
    with col2:
        st.metric("Sources Used", len(result['sources']))
    with col3:
        if 'model_usage' in result['metadata'] and result['metadata']['model_usage']:
            tokens = result['metadata']['model_usage'].get('total_tokens', 'N/A')
            st.metric("Tokens Used", tokens)
    
    # Sources
    if result['sources']:
        with st.expander(f"📚 Sources ({len(result['sources'])})", expanded=True):
            st.markdown(format_sources(result['sources']))
    
    # Context (for debugging/transparency)
    if st.checkbox("Show Context (Debug)", key=f"context_{time.time()}"):
        with st.expander("🔍 Retrieved Context"):
            st.text(result['context'])

def main_interface():
    """Main Streamlit interface"""
    st.set_page_config(
        page_title="Ocean AI POC",
        page_icon="🌊",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Header
    st.title("🌊 Ocean AI POC")
    st.markdown("*Sustainable ocean research powered by AI*")
    
    # Sidebar configuration
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # Config file input
        config_path = st.text_input(
            "Configuration File", 
            value="config.yaml",
            help="Path to the YAML configuration file"
        )
        
        if st.button("Load Configuration"):
            if load_retriever(config_path):
                st.success("✅ Configuration loaded successfully!")
            else:
                st.error("❌ Failed to load configuration")
        
        # Query parameters
        st.header("🎛️ Query Parameters")
        max_results = st.slider("Max Results", 1, 10, 5)
        similarity_threshold = st.slider("Similarity Threshold", 0.0, 1.0, 0.4, 0.1)
        
        # Filters
        st.header("🔍 Filters")
        doc_type_filter = st.selectbox(
            "Document Type", 
            ["None", "report", "research_paper", "policy_document", "news"],
            index=0
        )
        geographic_filter = st.text_input("Geographic Filter", placeholder="e.g., Baltic Sea")
        topic_filter = st.text_input("Topic Filter", placeholder="e.g., seagrass")
        
        # Convert "None" to None
        doc_type_filter = None if doc_type_filter == "None" else doc_type_filter
        geographic_filter = geographic_filter if geographic_filter.strip() else None
        topic_filter = topic_filter if topic_filter.strip() else None
    
    # Main content area
    if not st.session_state.config_loaded:
        st.warning("⚠️ Please load configuration first using the sidebar.")
        st.info("💡 Make sure your `config.yaml` file is properly configured with OpenAI API keys and PostgreSQL connection details.")
        return
    
    # Query input
    st.header("❓ Ask a Question")
    
    # Example questions
    with st.expander("💡 Example Questions"):
        example_questions = [
            "What are seagrass restoration methods?",
            "What is the success rate of transplantation methods in the Baltic Sea?",
            "List recent seagrass restoration methods in the Baltic Sea.",
            "How effective is seed broadcasting for seagrass restoration?",
            "What are the carbon sequestration benefits of seagrass meadows?",
            "What monitoring techniques are used in seagrass restoration?"
        ]
        
        for i, question in enumerate(example_questions):
            if st.button(f"📋 {question}", key=f"example_{i}"):
                st.session_state.current_question = question
    
    # Question input
    question = st.text_area(
        "Enter your question:",
        value=st.session_state.get('current_question', ''),
        height=100,
        placeholder="Ask anything about ocean sustainability, marine ecosystems, or seagrass restoration..."
    )
    
    # Query execution
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("🔍 Search", type="primary", disabled=not question.strip()):
            if question.strip():
                with st.spinner("🤔 Thinking..."):
                    try:
                        result = st.session_state.retriever.query(
                            question=question,
                            max_results=max_results,
                            similarity_threshold=similarity_threshold,
                            doc_type_filter=doc_type_filter,
                            geographic_filter=geographic_filter,
                            topic_filter=topic_filter
                        )
                        
                        # Add to history
                        st.session_state.query_history.append({
                            'question': question,
                            'result': result,
                            'timestamp': time.time()
                        })
                        
                        # Display result
                        display_query_result(result)
                        
                    except Exception as e:
                        st.error(f"❌ Error processing query: {e}")
    
    with col2:
        if st.button("🗑️ Clear"):
            st.session_state.current_question = ""
            st.experimental_rerun()
    
    # Query history
    if st.session_state.query_history:
        st.header("📜 Query History")
        for i, entry in enumerate(reversed(st.session_state.query_history[-5:])):  # Show last 5
            with st.expander(f"Q: {entry['question'][:80]}{'...' if len(entry['question']) > 80 else ''}"):
                display_query_result(entry['result'])

def command_line_mode():
    """Handle command line execution mode"""
    parser = argparse.ArgumentParser(description="Ocean AI POC - Command Line Interface")
    parser.add_argument("--config", "-c", default="config.yaml", help="Configuration file path")
    parser.add_argument("--question", "-q", required=True, help="Question to ask")
    parser.add_argument("--max-results", type=int, default=5, help="Maximum results to retrieve")
    parser.add_argument("--similarity-threshold", type=float, default=0.4, help="Similarity threshold")
    parser.add_argument("--doc-type", help="Filter by document type")
    parser.add_argument("--geographic", help="Filter by geographic region")
    parser.add_argument("--topic", help="Filter by topic")
    parser.add_argument("--output-format", choices=["text", "json"], default="text", help="Output format")
    
    args = parser.parse_args()
    
    try:
        # Initialize retriever
        retriever = OceanRAGRetriever(args.config)
        
        # Execute query
        result = retriever.query(
            question=args.question,
            max_results=args.max_results,
            similarity_threshold=args.similarity_threshold,
            doc_type_filter=args.doc_type,
            geographic_filter=args.geographic,
            topic_filter=args.topic
        )
        
        # Output results
        if args.output_format == "json":
            import json
            print(json.dumps(result, indent=2))
        else:
            # Text format (similar to rag_retriever.py output)
            print(f"Question: {result['metadata']['question']}")
            print(f"\nAnswer: {result['answer']}")
            print(f"\nSources ({len(result['sources'])}):")
            for i, source in enumerate(result['sources'], 1):
                print(f"  {i}. {source['filename']} ({source['organization']}) - Similarity: {source['similarity_score']}")
            print(f"\nResults found: {result['metadata']['results_count']}")
    
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

def main():
    """Main entry point"""
    # Initialize session state
    init_session_state()
    
    # Check if running in command line mode
    if len(sys.argv) > 1 and "--question" in sys.argv:
        command_line_mode()
    else:
        # Run Streamlit interface
        main_interface()

if __name__ == "__main__":
    main()
