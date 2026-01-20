# AI-Powered-Question-Paper-Generator-with-Course-Outcome-Mapping-and-Pattern-Based-Marks-Distribution

## Overview
This project is an AI-powered system that automatically generates Multiple Choice Questions (MCQs) from academic content and maps them to given Course Outcomes (COs). The main goal of the project is to reduce the manual effort involved in question paper preparation while ensuring that questions remain relevant, outcome-oriented, and academically meaningful.

The system accepts input in the form of PDF, DOCX, TXT files, or website URLs. From the extracted content, MCQs are generated using a Large Language Model (LLM). Each generated question is then analyzed and mapped to the most suitable Course Outcome using semantic similarity techniques. Additionally, Bloom’s Taxonomy levels are identified for every question to indicate its cognitive difficulty level.

This project was developed as a learning-oriented implementation to apply concepts from NLP, AI APIs, and software engineering in a practical academic use case.

---

## Features
- Upload academic content as PDF, DOCX, or TXT files  
- Provide a website URL as input for text extraction  
- Generate a fixed number of MCQs distributed evenly across all Course Outcomes  
- Automatic Course Outcome mapping using sentence embeddings  
- Bloom’s Taxonomy level detection for each question  
- Download generated MCQs in TXT, PDF, and JSON formats  
- Simple and interactive web interface with loading animation  

---

## Technology Stack

### Backend
- Python  
- Flask  
- Google Gemini API (for MCQ generation)  
- Sentence Transformers (semantic similarity)  
- PDFPlumber, python-docx (document parsing)  

### Frontend
- HTML, CSS  
- Bootstrap 5  
- Jinja2 templates  

---

## Project Structure
AI_MCQ_New/
|──src
    │── app.py # Flask application and routes
    │── mcq_core.py # Core logic for MCQ generation and mapping
    │── co_mapper.py # Standalone CO mapping utility
    │── main.py # CLI-based testing script
    │── test_gemini_models.py # Gemini model availability checker
    │── templates/
            |─ index.html # Input form UI
            |─ result.html # MCQ display and download page
│── uploads/ # Uploaded files
│── results/ # Generated outputs
│── requirements.txt
│── README.md

---

## System Workflow
1. The user provides a document or a website URL along with Course Outcomes and the required number of MCQs.
2. The system extracts readable text from the input source.
3. MCQs are generated separately for each Course Outcome using the Gemini LLM.
4. A balanced generation algorithm ensures equal distribution of questions across all COs.
5. Generated questions are parsed and mapped back to COs using Sentence Transformer embeddings.
6. Bloom’s Taxonomy level is detected using a hybrid keyword-based and semantic approach.
7. Final outputs are saved as TXT, PDF, and JSON files and made available for download.

---

## Bloom’s Taxonomy Handling
The system primarily focuses on **Apply**, **Analyze**, and **Evaluate** levels to maintain moderate academic difficulty. Keyword-based rules are applied first, followed by semantic similarity as a fallback. This hybrid approach approximates human judgment without requiring an additional LLM pass for Bloom level classification.

---

## Installation and Setup
1. Clone the repository  
2. Create and activate a virtual environment  
3. Install dependencies: pip install -r requirements.txt
4. Create a `.env` file and add: GEMINI_API_KEY=your_api_key_here
5. Run the application: python app.py


---

## Usage
- Open the browser and navigate to `http://127.0.0.1:5000`
- Upload a document or enter a website URL
- Enter Course Outcomes and the number of MCQs
- Click **Generate MCQs**
- View results and download files from the results page

---

## Learning Outcomes
Through this project, the following concepts were practically applied:
- Integration of LLM APIs into real applications  
- Semantic similarity using sentence embeddings  
- Automated Course Outcome mapping  
- Bloom’s Taxonomy-based question analysis  
- Full-stack development using Flask and HTML templates  

---

## Limitations
- Bloom level detection is approximate and rule-based  
- Quality depends on the input content and AI responses  
- Not optimized for high-scale production deployment  

---

## Future Improvements
- Support for Google Drive or cloud-based document links  
- Improved Bloom level classification using fine-tuned models  
- Admin dashboard for educators  
- Difficulty-level filtering and question quality scoring  

---


