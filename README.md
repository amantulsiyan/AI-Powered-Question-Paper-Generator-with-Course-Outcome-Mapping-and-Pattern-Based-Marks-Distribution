# AI-Powered-Question-Paper-Generator-with-Course-Outcome-Mapping-and-Pattern-Based-Marks-Distribution

## Overview
This project is an AI-powered system that automatically generates Multiple Choice Questions (MCQs) from academic content and maps them to given Course Outcomes (COs). The main goal of the project is to reduce the manual effort involved in question paper preparation while ensuring that questions remain relevant, outcome-oriented, and academically meaningful.

The system accepts input in the form of PDF, DOCX, TXT files, or website URLs. From the extracted content, MCQs are generated using a Large Language Model (LLM). Each generated question is then analyzed and mapped to the most suitable Course Outcome using keyword-based similarity techniques. Additionally, Bloom's Taxonomy levels are identified for every question to indicate its cognitive difficulty level.

This project was developed as a learning-oriented implementation to apply concepts from NLP, AI APIs, and software engineering in a practical academic use case.

---

## Features
- Upload academic content as PDF, DOCX, or TXT files  
- Provide a website URL as input for text extraction  
- Optional topic name for custom filename generation
- Generate a fixed number of MCQs distributed evenly across all Course Outcomes  
- Automatic Course Outcome mapping using keyword-based Jaccard similarity  
- Bloom's Taxonomy level detection for each question  
- Download generated MCQs in TXT, PDF, and JSON formats  
- Filenames formatted as `{topic_name}_{YYYYMMDD}`
- Answers displayed separately at the end in all outputs
- Simple and interactive web interface with loading animation  
- Dual deployment architecture (FastAPI backend + static frontend)

---

## Technology Stack

### Backend
- Python  
- FastAPI  
- Groq API with Llama 3.3 70B (for MCQ generation)  
- Keyword-based Jaccard similarity (for CO mapping)  
- PDFPlumber, python-docx (document parsing)  
- BeautifulSoup4 (URL scraping)  
- FPDF2 (PDF generation)  

### Frontend
- HTML, CSS, JavaScript  
- Bootstrap 5  
- Fetch API for backend communication  

### Deployment
- Backend: Render (free tier)  
- Frontend: Netlify (auto-deploy from GitHub)

---

## Project Structure

```text
AI MCQ/
├── backend/
│   ├── app.py                  # FastAPI application and routes
│   └── mcq_core.py             # Core logic for MCQ generation and mapping
├── frontend/
│   └── templates/
│       ├── index.html          # Input form UI
│       └── result.html         # MCQ display and download page
├── uploads/                    # Uploaded files (created at runtime)
├── results/                    # Generated outputs (created at runtime)
├── requirements.txt            # Python dependencies
├── Procfile                    # Render deployment config
├── netlify.toml                # Netlify deployment config
├── .env                        # Environment variables (not in git)
└── README.md
```

---

## System Workflow
1. The user provides a document or a website URL along with Course Outcomes, optional topic name, and the required number of MCQs.
2. The system extracts readable text from the input source.
3. MCQs are generated separately for each Course Outcome using the Groq API (Llama 3.3 70B).
4. A balanced generation algorithm ensures equal distribution of questions across all COs.
5. Generated questions are parsed and mapped back to COs using keyword-based Jaccard similarity.
6. Bloom's Taxonomy level is detected using a hybrid keyword-based approach.
7. Final outputs are saved as TXT, PDF, and JSON files with format `{topic_name}_{YYYYMMDD}` and made available for download.
8. Results are displayed on the web interface with answers shown separately at the end.

---

## Bloom's Taxonomy Handling
The system primarily focuses on **Apply**, **Analyze**, and **Evaluate** levels to maintain moderate academic difficulty. Keyword-based rules are applied to detect Bloom levels without requiring additional LLM calls.

---

## Installation and Setup

### Local Development
1. Clone the repository  
2. Create and activate a virtual environment  
3. Install dependencies: `pip install -r requirements.txt`
4. Create a `.env` file and add: `GROQ_API_KEY=your_api_key_here`
5. Run the backend: `uvicorn backend.app:app --reload`
6. Open `frontend/templates/index.html` in a browser or serve it locally

### Deployment

**Backend (Render):**
1. Connect your GitHub repository to Render
2. Set environment variable: `GROQ_API_KEY`
3. Render will use `Procfile` for deployment

**Frontend (Netlify):**
1. Connect your GitHub repository to Netlify
2. Set publish directory: `frontend/templates`
3. Auto-deploys on every push to main branch

---

## Usage
- Open the deployed frontend URL (or `frontend/templates/index.html` locally)
- Upload a document or enter a website URL
- Optionally enter a topic name for custom filenames
- Enter Course Outcomes (one per line) and the number of MCQs
- Click **Generate MCQs**
- View results with answers displayed separately at the end
- Download files in TXT, PDF, or JSON format (named as `{topic_name}_{date}`)

---

## Learning Outcomes
Through this project, the following concepts were practically applied:
- Integration of LLM APIs (Groq) into real applications  
- Keyword-based similarity algorithms (Jaccard index)  
- Automated Course Outcome mapping  
- Bloom's Taxonomy-based question analysis  
- Full-stack development using FastAPI and static HTML/JavaScript  
- Dual deployment architecture (Render + Netlify)  
- Memory-optimized implementation for free-tier hosting

---

## Limitations
- Bloom level detection is approximate and rule-based  
- CO mapping uses simple keyword similarity (no deep semantic understanding)  
- Quality depends on the input content and AI responses  
- Free tier rate limits apply (Groq: 30 requests/minute)  
- Optimized for free-tier deployment (512MB RAM on Render)

---

## Future Improvements
- Support for Google Drive or cloud-based document links  
- Improved CO mapping using fine-tuned embeddings  
- Admin dashboard for educators  
- Difficulty-level filtering and question quality scoring  
- Support for different question types (True/False, Short Answer)  
- Batch processing for multiple documents

---
