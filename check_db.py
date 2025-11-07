#!/usr/bin/env python3
"""
Simple Database Schema Checker
Quick check to see if the database tables exist with correct schema.
"""

import yaml
import psycopg2

def check_database():
    """Check if database schema is correct"""
    try:
        # Load config
        with open('config.yaml', 'r') as f:
            config = yaml.safe_load(f)
        
        db_config = config['postgres']
        
        # Connect to database
        conn = psycopg2.connect(
            host=db_config['host'],
            port=db_config['port'],
            dbname=db_config['dbname'],
            user=db_config['user'],
            password=db_config['password'],
            sslmode=db_config['sslmode']
        )
        cursor = conn.cursor()
        
        print("✅ Database connection successful")
        
        # Check if documents table exists with doc_type column
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'documents' AND column_name = 'doc_type';
        """)
        doc_type_exists = cursor.fetchone()
        
        if doc_type_exists:
            print("✅ documents table has doc_type column")
        else:
            print("❌ documents table missing doc_type column")
            print("   Solution: Run 'python database_setup.py'")
            return False
        
        # Check if chunks table exists
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_name = 'chunks';
        """)
        chunks_exists = cursor.fetchone()
        
        if chunks_exists:
            print("✅ chunks table exists")
        else:
            print("❌ chunks table missing")
            print("   Solution: Run 'python database_setup.py'")
            return False
        
        # Check pgvector extension
        cursor.execute("SELECT extname FROM pg_extension WHERE extname='vector';")
        vector_ext = cursor.fetchone()
        
        if vector_ext:
            print("✅ pgvector extension installed")
        else:
            print("❌ pgvector extension missing")
            print("   Solution: Run 'python database_setup.py'")
            return False
        
        cursor.close()
        conn.close()
        
        print("🎉 Database schema is correct!")
        return True
        
    except FileNotFoundError:
        print("❌ config.yaml not found")
        print("   Solution: Copy config.example.yaml to config.yaml and edit it")
        return False
    except psycopg2.OperationalError as e:
        print(f"❌ Database connection error: {e}")
        print("   Check your config.yaml database settings")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    print("🔍 Checking Ocean AI Database Schema...")
    check_database()