#!/usr/bin/env python3
"""
Reset Database Tables
Drops existing tables and recreates the schema from scratch.
"""

import yaml
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

def load_config():
    """Load configuration from config.yaml"""
    with open('config.yaml', 'r') as f:
        return yaml.safe_load(f)

def reset_tables():
    """Drop existing tables and recreate schema"""
    try:
        config = load_config()
        db_config = config['postgres']
        
        print(f"🔄 Resetting tables in database: {db_config['dbname']}")
        
        # Connect to database
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
        
        # Drop tables in correct order (chunks first due to foreign key)
        print("🗑️  Dropping existing tables...")
        cursor.execute("DROP TABLE IF EXISTS chunks CASCADE;")
        print("   ✅ Dropped chunks table")
        
        cursor.execute("DROP TABLE IF EXISTS documents CASCADE;")
        print("   ✅ Dropped documents table")
        
        # Drop any existing indexes that might remain
        cursor.execute("DROP INDEX IF EXISTS chunks_embedding_idx;")
        cursor.execute("DROP INDEX IF EXISTS idx_documents_doc_type;")
        cursor.execute("DROP INDEX IF EXISTS idx_documents_organization;")
        cursor.execute("DROP INDEX IF EXISTS idx_chunks_doc_id;")
        print("   ✅ Dropped indexes")
        
        cursor.close()
        conn.close()
        
        print("🏗️  Running database setup to recreate tables...")
        
        # Import and run the database setup
        from database_setup import create_database_and_tables
        create_database_and_tables()
        
        print("🎉 Database reset complete!")
        print("💡 You can now run document ingestion again.")
        
    except FileNotFoundError:
        print("❌ config.yaml not found. Copy config.example.yaml to config.yaml first.")
    except Exception as e:
        print(f"❌ Error resetting database: {e}")
        print("💡 Try manual reset with psql commands (see README)")

if __name__ == "__main__":
    response = input("⚠️  This will DELETE ALL data in the Ocean AI database. Continue? (y/N): ")
    if response.lower() == 'y':
        reset_tables()
    else:
        print("❌ Reset cancelled")