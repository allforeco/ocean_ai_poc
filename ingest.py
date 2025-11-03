#!/usr/bin/env python3
"""
Document Ingestion Pipeline for Ocean AI POC
Processes PDFs and documents, creates embeddings, and stores in PostgreSQL with pgvector.
"""

import os
import argparse
import yaml
import hashlib
from typing import List, Dict, Any
from pathlib import Path
import json

import psycopg2
from psycopg2.extras import RealDictCursor
import PyPDF2
from openai import OpenAI
from langchain_text_splitters import RecursiveCharacterTextSplitter
import tiktoken

class DocumentIngestor:
    def __init__(self, config_path: str = "config.yaml"):
        """Initialize the document ingestor with configuration"""
        self.config = self.load_config(config_path)
        self.openai_client = OpenAI(api_key=self.config['openai']['api_key'])
        self.embedding_model = self.config['openai']['embedding_model']
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        self.encoding = tiktoken.get_encoding("cl100k_base")
        
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
    
    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract text content from PDF file"""
        text = ""
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
        except Exception as e:
            print(f"Error extracting text from {pdf_path}: {e}")
            return ""
        return text.strip()
    
    def extract_metadata_from_filename(self, filename: str) -> Dict[str, Any]:
        """Extract metadata from filename patterns"""
        metadata = {}
        filename_lower = filename.lower()
        
        # Document type detection
        if any(term in filename_lower for term in ['sustainability', 'esg', 'csr']):
            metadata['doc_type'] = 'sustainability_report'
        elif any(term in filename_lower for term in ['annual', 'quarterly', 'financial']):
            metadata['doc_type'] = 'company_report'
        elif 'esrs' in filename_lower or 'european sustainability reporting' in filename_lower:
            metadata['doc_type'] = 'esrs_document'
        else:
            metadata['doc_type'] = 'unknown'
        
        # Geographic focus detection
        geographic_terms = {
            'baltic': 'Baltic Sea',
            'north sea': 'North Sea',
            'mediterranean': 'Mediterranean Sea',
            'atlantic': 'Atlantic Ocean',
            'pacific': 'Pacific Ocean',
            'arctic': 'Arctic Ocean'
        }
        
        for term, region in geographic_terms.items():
            if term in filename_lower:
                metadata['geographic_focus'] = region
                break
        
        # Topic detection
        ocean_topics = {
            'seagrass': 'seagrass_restoration',
            'coral': 'coral_conservation',
            'biodiversity': 'marine_biodiversity',
            'carbon': 'blue_carbon',
            'plastic': 'marine_pollution',
            'fishing': 'sustainable_fisheries',
            'renewable': 'offshore_renewable_energy'
        }
        
        metadata['topics'] = []
        for term, topic in ocean_topics.items():
            if term in filename_lower:
                metadata['topics'].append(topic)
        
        return metadata
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in text using tiktoken"""
        return len(self.encoding.encode(text))
    
    def create_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Create embeddings for a list of texts using OpenAI"""
        try:
            response = self.openai_client.embeddings.create(
                input=texts,
                model=self.embedding_model
            )
            return [embedding.embedding for embedding in response.data]
        except Exception as e:
            print(f"Error creating embeddings: {e}")
            return []
    
    def document_exists(self, filename: str, file_size: int) -> bool:
        """Check if document already exists in database"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT id FROM documents WHERE filename = %s AND file_size = %s",
            (filename, file_size)
        )
        result = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        return result is not None
    
    def store_document(self, filename: str, doc_type: str, organization: str, 
                      file_size: int, metadata: Dict[str, Any]) -> int:
        """Store document metadata in database and return document ID"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO documents (filename, doc_type, organization, file_size, metadata)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """, (filename, doc_type, organization, file_size, json.dumps(metadata)))
        
        doc_id = cursor.fetchone()['id']
        conn.commit()
        cursor.close()
        conn.close()
        
        return doc_id
    
    def store_chunks(self, doc_id: int, chunks: List[str], embeddings: List[List[float]], 
                    chunk_metadata: List[Dict[str, Any]]):
        """Store document chunks and embeddings in database"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        for i, (chunk, embedding, metadata) in enumerate(zip(chunks, embeddings, chunk_metadata)):
            token_count = self.count_tokens(chunk)
            
            cursor.execute("""
                INSERT INTO chunks (doc_id, chunk_index, content, embedding, token_count, metadata)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (doc_id, i, chunk, embedding, token_count, json.dumps(metadata)))
        
        conn.commit()
        cursor.close()
        conn.close()
    
    def ingest_document(self, file_path: str, organization: str = None) -> bool:
        """Ingest a single document"""
        file_path = Path(file_path)
        
        if not file_path.exists():
            print(f"File not found: {file_path}")
            return False
        
        filename = file_path.name
        file_size = file_path.stat().st_size
        
        # Check if document already exists
        if self.document_exists(filename, file_size):
            print(f"Document {filename} already exists in database, skipping...")
            return True
        
        print(f"Ingesting document: {filename}")
        
        # Extract text based on file type
        if file_path.suffix.lower() == '.pdf':
            text = self.extract_text_from_pdf(str(file_path))
        else:
            # For other text files
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    text = f.read()
            except Exception as e:
                print(f"Error reading file {file_path}: {e}")
                return False
        
        if not text.strip():
            print(f"No text extracted from {filename}")
            return False
        
        # Extract metadata
        metadata = self.extract_metadata_from_filename(filename)
        doc_type = metadata.get('doc_type', 'unknown')
        
        # Store document metadata
        doc_id = self.store_document(filename, doc_type, organization, file_size, metadata)
        
        # Split text into chunks
        chunks = self.text_splitter.split_text(text)
        print(f"Created {len(chunks)} chunks from {filename}")
        
        # Create chunk metadata
        chunk_metadata = []
        for i, chunk in enumerate(chunks):
            chunk_meta = metadata.copy()
            chunk_meta['chunk_index'] = i
            chunk_meta['source_file'] = filename
            chunk_metadata.append(chunk_meta)
        
        # Create embeddings (batch process for efficiency)
        batch_size = 100  # OpenAI allows up to 2048 inputs per request
        all_embeddings = []
        
        for i in range(0, len(chunks), batch_size):
            batch_chunks = chunks[i:i + batch_size]
            batch_embeddings = self.create_embeddings(batch_chunks)
            all_embeddings.extend(batch_embeddings)
            print(f"Created embeddings for chunks {i+1}-{min(i+batch_size, len(chunks))}")
        
        if len(all_embeddings) != len(chunks):
            print(f"Error: Embedding count mismatch. Expected {len(chunks)}, got {len(all_embeddings)}")
            return False
        
        # Store chunks and embeddings
        self.store_chunks(doc_id, chunks, all_embeddings, chunk_metadata)
        
        print(f"Successfully ingested {filename} with {len(chunks)} chunks")
        return True
    
    def ingest_directory(self, directory_path: str, organization: str = None) -> int:
        """Ingest all supported documents in a directory"""
        directory_path = Path(directory_path)
        
        if not directory_path.exists():
            print(f"Directory not found: {directory_path}")
            return 0
        
        supported_extensions = {'.pdf', '.txt', '.md'}
        files = [f for f in directory_path.iterdir() 
                if f.is_file() and f.suffix.lower() in supported_extensions]
        
        successful_ingestions = 0
        
        for file_path in files:
            if self.ingest_document(file_path, organization):
                successful_ingestions += 1
        
        print(f"\nIngestion complete: {successful_ingestions}/{len(files)} files processed successfully")
        return successful_ingestions

def main():
    parser = argparse.ArgumentParser(description="Ingest documents into Ocean AI knowledge base")
    parser.add_argument("--file", "-f", help="Path to a single file to ingest")
    parser.add_argument("--directory", "-d", help="Path to directory containing files to ingest")
    parser.add_argument("--organization", "-o", help="Organization name for the documents")
    parser.add_argument("--config", "-c", default="config.yaml", help="Path to configuration file")
    
    args = parser.parse_args()
    
    if not args.file and not args.directory:
        print("Please specify either --file or --directory")
        return
    
    ingestor = DocumentIngestor(args.config)
    
    if args.file:
        ingestor.ingest_document(args.file, args.organization)
    elif args.directory:
        ingestor.ingest_directory(args.directory, args.organization)

if __name__ == "__main__":
    main()
