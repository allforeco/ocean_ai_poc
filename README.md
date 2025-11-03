# Ocean AI POC 🌊

A Retrieval-Augmented Generation (RAG) system for ocean sustainability research, powered by OpenAI embeddings and PostgreSQL with pgvector.

## Overview

The Ocean AI POC enables researchers and sustainability professionals to query ocean-related documents using natural language. The system:

- **Ingests** PDF and text documents about ocean sustainability, seagrass restoration, marine biodiversity, etc.
- **Chunks** documents and creates vector embeddings using OpenAI's text-embedding-3-small
- **Stores** embeddings in PostgreSQL with pgvector for efficient similarity search
- **Provides** both web UI (Streamlit) and command-line interfaces for querying
- **Generates** contextual answers using OpenAI GPT-4o-mini with retrieved document context

## Requirements

- Python 3.8+
- PostgreSQL 14+ with pgvector extension
- OpenAI API key
- macOS/Linux (tested on macOS)

## Installation

### 1. Clone and Setup Python Environment

```bash
git clone <your-repo-url>
cd ocean_ai_poc

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. PostgreSQL Setup

Install PostgreSQL and the pgvector extension:

```bash
# macOS with Homebrew
brew install postgresql pgvector

# Start PostgreSQL
brew services start postgresql

# Create database
createdb oceanai
```

Install pgvector extension:
```sql
-- Connect to your database
psql -d oceanai

-- Install extension
CREATE EXTENSION IF NOT EXISTS vector;
```

### 3. Configuration

Copy and configure the settings:

```bash
cp config.example.yaml config.yaml
```

Edit `config.yaml` with your settings:

```yaml
openai:
  api_key: "your-openai-api-key-here"
  embedding_model: "text-embedding-3-small"
  chat_model: "gpt-4o-mini"

postgres:
  host: "localhost"
  port: 5432
  dbname: "oceanai"
  user: "your-username"
  password: "your-password"  # optional
  sslmode: "prefer"
```

### 4. Initialize Database Schema

```bash
python database_setup.py
```

This creates the `documents` and `chunks` tables with proper vector indexing.

## Usage

### Document Ingestion

Add documents to your knowledge base:

#### Single File
```bash
python ingest.py --file path/to/report.pdf --organization "Ocean Research Institute"
```

#### Directory of Files
```bash
python ingest.py --directory ./sample_docs --organization "Marine Foundation"
```

**Supported formats:** PDF, TXT, MD

**What happens during ingestion:**
- Text extraction from PDFs
- Smart chunking (1000 tokens with 200 overlap)
- Metadata extraction from filenames
- OpenAI embedding generation
- Storage in PostgreSQL with vector indexing

### Web Interface (Streamlit)

Start the web server:

```bash
# Option 1: Direct command
streamlit run app_streamlit.py

# Option 2: Using the convenience script
./run-streamlit

# Option 3: With virtual environment
./.venv/bin/python -m streamlit run app_streamlit.py
```

The interface will be available at `http://localhost:8501`

**Web UI Features:**
- Natural language question input
- Real-time similarity search
- Adjustable similarity thresholds
- Document type and geographic filters
- Source attribution with similarity scores
- Query history
- Example questions to get started

### Command Line Interface

Query directly from the terminal:

```bash
# Basic query
python app_streamlit.py --config config.yaml --question "What are seagrass restoration methods?"

# With parameters
python app_streamlit.py \
  --question "List Baltic Sea restoration techniques" \
  --max-results 3 \
  --similarity-threshold 0.6 \
  --output-format json
```

**Available options:**
- `--config`: Configuration file path (default: config.yaml)
- `--question`: Your question (required)
- `--max-results`: Maximum results to return (default: 5)
- `--similarity-threshold`: Minimum similarity score (default: 0.4)
- `--doc-type`: Filter by document type
- `--geographic`: Filter by geographic region
- `--topic`: Filter by topic
- `--output-format`: text or json (default: text)

## Example Queries

Try these example questions:

- "What are seagrass restoration methods?"
- "What is the success rate of transplantation methods in the Baltic Sea?"
- "How effective is seed broadcasting for seagrass restoration?"
- "What monitoring techniques are used in seagrass restoration?"
- "What are the carbon sequestration benefits of seagrass meadows?"

## Adding More Documents

### Document Organization

Create organized directories for your documents:

```
ocean_docs/
├── reports/
│   ├── baltic_seagrass_report.pdf
│   └── marine_biodiversity_2024.pdf
├── research_papers/
│   ├── coral_restoration_methods.pdf
│   └── blue_carbon_initiatives.pdf
└── policy_documents/
    ├── eu_marine_strategy.pdf
    └── sustainable_fisheries_framework.pdf
```

### Batch Ingestion

```bash
# Ingest all documents in a directory
python ingest.py --directory ocean_docs/reports --organization "Marine Research Center"

# Ingest from multiple directories
python ingest.py --directory ocean_docs/research_papers --organization "Academic Consortium"
python ingest.py --directory ocean_docs/policy_documents --organization "EU Commission"
```

### Document Metadata

The system automatically extracts metadata from filenames:

**Document Types:**
- `sustainability_report`: Files containing "sustainability", "esg", "csr"
- `company_report`: Files containing "annual", "quarterly", "financial"
- `esrs_document`: Files containing "esrs" or "european sustainability reporting"

**Geographic Focus:**
- Baltic Sea, North Sea, Mediterranean Sea, Atlantic Ocean, etc.

**Topics:**
- seagrass_restoration, coral_conservation, marine_biodiversity, blue_carbon, etc.

### Checking Ingestion Status

```bash
# Check what documents are in the database
psql -d oceanai -c "SELECT filename, organization, doc_type FROM documents;"

# Count chunks per document
psql -d oceanai -c "
SELECT d.filename, COUNT(*) as chunks 
FROM documents d 
JOIN chunks c ON c.doc_id = d.id 
GROUP BY d.filename;
"
```

## Performance Optimization

### Install Watchdog (Recommended)

For better Streamlit performance with file change detection:

```bash
# Install developer tools (macOS)
xcode-select --install

# Install watchdog
pip install watchdog
```

### Large Document Collections

For processing many documents:

1. **Batch processing**: Ingest documents in smaller batches to manage API rate limits
2. **Monitor costs**: OpenAI embedding API costs scale with document volume
3. **Database optimization**: The pgvector index automatically optimizes similarity search

## Troubleshooting

### Common Issues

**"No results found"**: 
- Check similarity threshold (try lowering to 0.2-0.4)
- Verify documents are properly ingested
- Try broader/different query terms

**OpenAI API errors**:
- Verify API key in config.yaml
- Check API quota/billing status
- Ensure internet connectivity

**PostgreSQL connection errors**:
- Verify PostgreSQL is running: `brew services list | grep postgresql`
- Check database exists: `psql -l | grep oceanai`
- Verify pgvector extension: `psql -d oceanai -c "SELECT * FROM pg_extension WHERE extname='vector';"`

**Embedding dimension errors**:
- Ensure consistent embedding model across ingestion and querying
- text-embedding-3-small produces 1536-dimensional vectors

### Debug Mode

Enable debug output:

```bash
# View retrieved context in web UI
# Check "Show Context (Debug)" checkbox in the interface

# Command line with full context
python rag_retriever.py --question "your question here"
```

## File Structure

```
ocean_ai_poc/
├── app_streamlit.py          # Streamlit web interface + CLI
├── rag_retriever.py          # Core RAG retrieval logic
├── ingest.py                 # Document ingestion pipeline
├── database_setup.py         # Database schema initialization
├── config.yaml               # Configuration (create from example)
├── config.example.yaml       # Configuration template
├── rag_prompt.md            # System prompt for LLM
├── requirements.txt          # Python dependencies
├── sample_docs/              # Example documents
└── README.md                # This file
```

## API Reference

### RAG Retriever Class

```python
from rag_retriever import OceanRAGRetriever

retriever = OceanRAGRetriever("config.yaml")

result = retriever.query(
    question="What are seagrass restoration methods?",
    max_results=5,
    similarity_threshold=0.4,
    doc_type_filter="report",
    geographic_filter="Baltic Sea",
    topic_filter="seagrass_restoration"
)

print(result['answer'])
print(f"Sources: {len(result['sources'])}")
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

## License

[Add your license here]

## Support

For questions or issues:
- Check the troubleshooting section above
- Review the example queries
- Verify configuration settings

---

**Next Steps:**
- Add more ocean sustainability documents to expand the knowledge base
- Experiment with different similarity thresholds for your use cases
- Explore geographic and topic filtering for targeted searches
