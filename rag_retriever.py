#!/usr/bin/env python3
"""
RAG Retrieval System for Ocean AI POC
Handles vector similarity search and context preparation for LLM responses.
"""

import yaml
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

import psycopg2
from psycopg2.extras import RealDictCursor
from openai import OpenAI
import numpy as np

@dataclass
class SearchResult:
    """Represents a search result from the vector database"""
    content: str
    doc_id: int
    chunk_id: int
    filename: str
    organization: str
    doc_type: str
    similarity_score: float
    metadata: Dict[str, Any]

class OceanRAGRetriever:
    def __init__(self, config_path: str = "config.yaml"):
        """Initialize the RAG retriever with configuration"""
        self.config = self.load_config(config_path)
        self.openai_client = OpenAI(api_key=self.config['openai']['api_key'])
        self.embedding_model = self.config['openai']['embedding_model']
        self.chat_model = self.config['openai']['chat_model']
        
    def load_config(self, config_path: str) -> dict:
        """Load configuration from YAML file"""
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def get_db_connection(self):
        """Get PostgreSQL database connection"""
        db_config = self.config['postgres']
        return psycopg2.connect(
            host=db_config['host'],
            port=db_config['port'],
            dbname=db_config['dbname'],
            user=db_config['user'],
            password=db_config['password'],
            sslmode=db_config['sslmode'],
            cursor_factory=RealDictCursor
        )
    
    def create_query_embedding(self, query: str) -> List[float]:
        """Create embedding for a query string"""
        try:
            response = self.openai_client.embeddings.create(
                input=[query],
                model=self.embedding_model
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"Error creating query embedding: {e}")
            return []
    
    def search_similar_chunks(self, 
                             query_embedding: List[float], 
                             limit: int = 5,
                             similarity_threshold: float = 0.0,
                             doc_type_filter: Optional[str] = None,
                             geographic_filter: Optional[str] = None,
                             topic_filter: Optional[str] = None) -> List[SearchResult]:
        """
        Search for similar chunks using vector similarity
        
        Args:
            query_embedding: The query vector
            limit: Maximum number of results to return
            similarity_threshold: Minimum similarity score (0-1)
            doc_type_filter: Filter by document type
            geographic_filter: Filter by geographic region
            topic_filter: Filter by topic
        """
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        # Build the SQL query with optional filters
        # Convert embedding list to string format for PostgreSQL vector casting
        embedding_str = "[" + ",".join(map(str, query_embedding)) + "]"
        
        # Simplified query without WHERE clause for debugging
        full_query = """
            SELECT 
                c.content,
                c.id as chunk_id,
                c.doc_id,
                c.metadata as chunk_metadata,
                d.filename,
                d.organization,
                d.doc_type,
                d.metadata as doc_metadata,
                1 - (c.embedding <=> %s::vector) as similarity_score
            FROM chunks c
            JOIN documents d ON c.doc_id = d.id
            ORDER BY similarity_score DESC 
            LIMIT %s
        """
        
        params = [embedding_str, limit]
        
        try:
            cursor.execute(full_query, params)
            results = cursor.fetchall()
            
            search_results = []
            for row in results:
                metadata = {}
                # Metadata columns are already parsed as dict by RealDictCursor
                if row['chunk_metadata']:
                    metadata.update(row['chunk_metadata'])
                if row['doc_metadata']:
                    metadata.update(row['doc_metadata'])
                
                search_results.append(SearchResult(
                    content=row['content'],
                    doc_id=row['doc_id'],
                    chunk_id=row['chunk_id'],
                    filename=row['filename'],
                    organization=row['organization'],
                    doc_type=row['doc_type'],
                    similarity_score=row['similarity_score'],
                    metadata=metadata
                ))
            
            return search_results
            
        except Exception as e:
            print(f"Error searching chunks: {e}")
            print(f"Query: {full_query}")
            print(f"Params: {params[:2]}")  # Don't print the embedding vector
            return []
        finally:
            cursor.close()
            conn.close()
    
    def prepare_context(self, search_results: List[SearchResult], max_tokens: int = 3000) -> str:
        """
        Prepare context string from search results, respecting token limits
        """
        if not search_results:
            return "No relevant information found."
        
        context_parts = []
        total_length = 0
        
        for result in search_results:
            # Create a formatted context entry
            source_info = f"[Source: {result.filename} - {result.organization}]"
            content_with_source = f"{source_info}\n{result.content}\n"
            
            # Rough token estimation (1 token ≈ 4 characters)
            estimated_tokens = len(content_with_source) // 4
            
            if total_length + estimated_tokens > max_tokens:
                break
            
            context_parts.append(content_with_source)
            total_length += estimated_tokens
        
        return "\n---\n".join(context_parts)
    
    def generate_response(self, question: str, context: str) -> Dict[str, Any]:
        """
        Generate response using OpenAI chat model with context
        """
        # Load the RAG prompt template
        try:
            with open('rag_prompt.md', 'r') as f:
                prompt_template = f.read()
        except FileNotFoundError:
            prompt_template = """You are an expert marine scientist and ocean sustainability specialist. Answer the user's question based on the provided context from ocean research documents.

Guidelines:
- Use only information from the provided context
- Be specific and cite sources when possible
- If the context doesn't contain relevant information, say so
- Focus on ocean sustainability, marine ecosystems, and environmental impacts
- Provide practical insights when available

Context:
{context}

Question: {question}

Answer:"""
        
        # Format the prompt
        formatted_prompt = prompt_template.format(context=context, question=question)
        
        try:
            response = self.openai_client.chat.completions.create(
                model=self.chat_model,
                messages=[
                    {"role": "system", "content": "You are an expert marine scientist and ocean sustainability specialist."},
                    {"role": "user", "content": formatted_prompt}
                ],
                temperature=0.7,
                max_tokens=1000
            )
            
            return {
                "answer": response.choices[0].message.content,
                "model": self.chat_model,
                "usage": response.usage.dict() if response.usage else {}
            }
            
        except Exception as e:
            return {
                "answer": f"Error generating response: {e}",
                "model": self.chat_model,
                "usage": {}
            }
    
    def query(self, 
              question: str,
              max_results: int = 5,
              similarity_threshold: float = 0.0,
              doc_type_filter: Optional[str] = None,
              geographic_filter: Optional[str] = None,
              topic_filter: Optional[str] = None) -> Dict[str, Any]:
        """
        Main query method that orchestrates the RAG pipeline
        
        Returns:
            Dictionary containing answer, sources, and metadata
        """
        # Create embedding for the question
        query_embedding = self.create_query_embedding(question)
        if not query_embedding:
            return {
                "answer": "Error creating query embedding",
                "sources": [],
                "context": "",
                "metadata": {}
            }
        
        # Search for similar chunks
        search_results = self.search_similar_chunks(
            query_embedding=query_embedding,
            limit=max_results,
            similarity_threshold=similarity_threshold,
            doc_type_filter=doc_type_filter,
            geographic_filter=geographic_filter,
            topic_filter=topic_filter
        )
        
        # Prepare context
        context = self.prepare_context(search_results)
        
        # Generate response
        response_data = self.generate_response(question, context)
        
        # Prepare source information
        sources = []
        for result in search_results:
            sources.append({
                "filename": result.filename,
                "organization": result.organization,
                "doc_type": result.doc_type,
                "similarity_score": round(result.similarity_score, 3),
                "geographic_focus": result.metadata.get('geographic_focus'),
                "topics": result.metadata.get('topics', [])
            })
        
        return {
            "answer": response_data["answer"],
            "sources": sources,
            "context": context,
            "metadata": {
                "question": question,
                "results_count": len(search_results),
                "model_usage": response_data.get("usage", {}),
                "filters_applied": {
                    "doc_type": doc_type_filter,
                    "geographic": geographic_filter,
                    "topic": topic_filter
                }
            }
        }

def main():
    """Test the RAG retriever with a sample query"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Ocean RAG Retriever")
    parser.add_argument("--question", "-q", required=True, help="Question to ask")
    parser.add_argument("--config", "-c", default="config.yaml", help="Configuration file")
    parser.add_argument("--max-results", type=int, default=5, help="Maximum results to retrieve")
    parser.add_argument("--doc-type", help="Filter by document type")
    parser.add_argument("--geographic", help="Filter by geographic region")
    parser.add_argument("--topic", help="Filter by topic")
    
    args = parser.parse_args()
    
    retriever = OceanRAGRetriever(args.config)
    
    result = retriever.query(
        question=args.question,
        max_results=args.max_results,
        doc_type_filter=args.doc_type,
        geographic_filter=args.geographic,
        topic_filter=args.topic
    )
    
    print(f"Question: {result['metadata']['question']}")
    print(f"\nAnswer: {result['answer']}")
    print(f"\nSources ({len(result['sources'])}):")
    for i, source in enumerate(result['sources'], 1):
        print(f"  {i}. {source['filename']} ({source['organization']}) - Similarity: {source['similarity_score']}")
    
    print(f"\nResults found: {result['metadata']['results_count']}")

if __name__ == "__main__":
    main()