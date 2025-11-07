#!/usr/bin/env python3
"""
Database Diagnostic Script
Checks database schema and helps troubleshoot common issues.
"""

import yaml
import psycopg2
from psycopg2.extras import RealDictCursor

def load_config():
    """Load configuration from config.yaml"""
    with open('config.yaml', 'r') as f:
        return yaml.safe_load(f)

def diagnose_database():
    """Diagnose database schema and connection issues"""
    try:
        config = load_config()
        db_config = config['postgres']
        
        print("🔍 Diagnosing Ocean AI Database...")
        print(f"Database: {db_config['dbname']}")
        print(f"Host: {db_config['host']}")
        print(f"Port: {db_config['port']}")
        print(f"User: {db_config['user']}")
        print()
        
        # Test connection
        try:
            conn = psycopg2.connect(
                host=db_config['host'],
                port=db_config['port'],
                dbname=db_config['dbname'],
                user=db_config['user'],
                password=db_config['password'],
                sslmode=db_config['sslmode'],
                cursor_factory=RealDictCursor
            )
            print("✅ Database connection successful")
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            return
        
        cursor = conn.cursor()
        
        # Check if pgvector extension exists
        cursor.execute("SELECT * FROM pg_extension WHERE extname='vector';")
        vector_ext = cursor.fetchall()
        if vector_ext:
            print("✅ pgvector extension is installed")
        else:
            print("❌ pgvector extension is NOT installed")
        
        # Check if documents table exists
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name = 'documents';
        """)
        documents_table = cursor.fetchall()
        
        if documents_table:
            print("✅ documents table exists")
            
            # Check columns in documents table
            cursor.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'documents' AND table_schema = 'public'
                ORDER BY ordinal_position;
            """)
            columns = cursor.fetchall()
            
            print("📋 documents table columns:")
            expected_columns = ['id', 'filename', 'doc_type', 'organization', 'upload_date', 'file_size', 'metadata']
            found_columns = [col['column_name'] for col in columns]
            
            for col in columns:
                status = "✅" if col['column_name'] in expected_columns else "⚠️"
                print(f"  {status} {col['column_name']} ({col['data_type']}) - nullable: {col['is_nullable']}")
            
            # Check for missing expected columns
            missing_columns = set(expected_columns) - set(found_columns)
            if missing_columns:
                print(f"❌ Missing columns: {', '.join(missing_columns)}")
            else:
                print("✅ All expected columns present")
                
        else:
            print("❌ documents table does NOT exist")
        
        # Check if chunks table exists
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name = 'chunks';
        """)
        chunks_table = cursor.fetchall()
        
        if chunks_table:
            print("✅ chunks table exists")
        else:
            print("❌ chunks table does NOT exist")
        
        # Check indexes
        cursor.execute("""
            SELECT indexname, tablename 
            FROM pg_indexes 
            WHERE tablename IN ('documents', 'chunks') AND schemaname = 'public';
        """)
        indexes = cursor.fetchall()
        
        if indexes:
            print("📋 Indexes found:")
            for idx in indexes:
                print(f"  ✅ {idx['indexname']} on {idx['tablename']}")
        else:
            print("❌ No indexes found")
        
        # Count existing documents
        if documents_table:
            try:
                cursor.execute("SELECT COUNT(*) as count FROM documents;")
                doc_count = cursor.fetchone()
                print(f"📊 Documents in database: {doc_count['count']}")
            except Exception as e:
                print(f"❌ Error counting documents: {e}")
        
        cursor.close()
        conn.close()
        
        print("\n🔧 Troubleshooting Steps:")
        if not documents_table:
            print("1. Run: python database_setup.py")
        elif missing_columns:
            print("1. Drop and recreate tables: DROP TABLE chunks, documents CASCADE; then run python database_setup.py")
        else:
            print("1. Database schema looks correct!")
            print("2. If still getting errors, check that your application is connecting to the same database")
            
    except FileNotFoundError:
        print("❌ config.yaml not found. Copy config.example.yaml to config.yaml and configure it.")
    except Exception as e:
        print(f"❌ Diagnostic error: {e}")

if __name__ == "__main__":
    diagnose_database()