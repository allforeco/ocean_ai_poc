#!/usr/bin/env python3
"""
Database setup script for Ocean AI POC
Creates the necessary tables and extensions for the RAG system.
"""

import psycopg2
import yaml
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

def load_config():
    """Load configuration from config.yaml"""
    with open('config.yaml', 'r') as f:
        return yaml.safe_load(f)

def create_database_and_tables():
    """Set up the database with pgvector extension and required tables"""
    config = load_config()
    db_config = config['postgres']
    
    # Connect to PostgreSQL (to postgres database first)
    conn = psycopg2.connect(
        host=db_config['host'],
        port=db_config['port'],
        dbname='postgres',  # Connect to default postgres database first
        user=db_config['user'],
        password=db_config['password'],
        sslmode=db_config['sslmode']
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()
    
    # Create database if it doesn't exist
    try:
        cursor.execute(f"CREATE DATABASE {db_config['dbname']}")
        print(f"Database '{db_config['dbname']}' created successfully")
    except psycopg2.errors.DuplicateDatabase:
        print(f"Database '{db_config['dbname']}' already exists")
    except Exception as e:
        print(f"Database '{db_config['dbname']}' already exists or error: {e}")
    
    cursor.close()
    conn.close()
    
    # Connect to our target database
    conn = psycopg2.connect(
        host=db_config['host'],
        port=db_config['port'],
        dbname=db_config['dbname'],
        user=db_config['user'],
        password=db_config['password'],
        sslmode=db_config['sslmode']
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()
    
    # Create pgvector extension
    try:
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
        print("pgvector extension enabled")
    except Exception as e:
        print(f"Error creating pgvector extension: {e}")
    
    # Create documents table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id SERIAL PRIMARY KEY,
            filename VARCHAR(255) NOT NULL,
            doc_type VARCHAR(100),
            organization VARCHAR(255),
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            file_size INTEGER,
            metadata JSONB
        )
    """)
    print("Documents table created")
    
    # Create chunks table with vector embeddings
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            id SERIAL PRIMARY KEY,
            doc_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            embedding vector(1536),  -- OpenAI text-embedding-3-small dimension
            token_count INTEGER,
            metadata JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("Chunks table created")
    
    # Create index on embeddings for faster similarity search
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS chunks_embedding_idx 
        ON chunks USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    """)
    print("Vector index created")
    
    # Create indexes for better query performance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_documents_doc_type ON documents(doc_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_documents_organization ON documents(organization)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON chunks(doc_id)")
    
    print("Additional indexes created")
    
    cursor.close()
    conn.close()
    print("Database setup completed successfully!")

if __name__ == "__main__":
    create_database_and_tables()