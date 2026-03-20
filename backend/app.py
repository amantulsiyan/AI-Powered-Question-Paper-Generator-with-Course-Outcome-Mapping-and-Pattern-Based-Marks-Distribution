import os
import sys
import json
import traceback
import requests as http_requests

sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from werkzeug.utils import secure_filename
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

from mcq_core import extract_text, generate_balanced_mcqs, save_mcqs_txt, save_mcqs_pdf

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
RESULTS_FOLDER = os.path.join(BASE_DIR, "results")
ALLOWED_EXTENSIONS = {"pdf", "txt", "docx"}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULTS_FOLDER, exist_ok=True)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def extract_text_from_url(url: str) -> str:
    try:
        resp = http_requests.get(url, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
            tag.extract()
        lines = [l.strip() for l in soup.get_text(separator="\n").splitlines() if l.strip()]
        return "\n".join(lines)
    except Exception as e:
        raise ValueError(f"Failed to extract data from URL: {e}")


def error(msg: str, status: int = 400):
    return JSONResponse({"error": msg}, status_code=status)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/generate")
async def generate_mcqs(
    url_input: str = Form(default=""),
    total_questions: int = Form(...),
    co_list: str = Form(...),
    file: UploadFile = File(default=None),
):
    try:
        if url_input.strip():
            try:
                text = extract_text_from_url(url_input.strip())
            except Exception as e:
                return error(f"Error fetching URL: {e}")
            base_name = "generated_from_url"
        else:
            if not file or not file.filename:
                return error("No file uploaded and no URL provided.")
            if not allowed_file(file.filename):
                return error("Invalid file type. Allowed: PDF, DOCX, TXT.")

            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            with open(filepath, "wb") as f:
                f.write(await file.read())

            try:
                text = extract_text(filepath)
            except Exception as e:
                return error(f"Error extracting text: {e}")

            base_name = filename.rsplit(".", 1)[0]

        co_entries = [line.strip() for line in co_list.split("\n") if line.strip()]
        if not co_entries or total_questions <= 0:
            return error("Please provide valid CO list and number of questions.")

        try:
            result = generate_balanced_mcqs(text, co_entries, total_questions)
            mcqs_raw = result.get("raw_text", "")
            mapped_mcqs = result.get("mapped_questions", [])
        except Exception as e:
            traceback.print_exc()
            err = str(e).lower()
            if "rate" in err:
                return error("AI rate limit reached. Please wait a minute and try again.", 429)
            return error("Error generating MCQs. Please try again or reduce question count.", 500)

        txt_name = f"generated_mcqs_{base_name}.txt"
        pdf_name = f"generated_mcqs_{base_name}.pdf"
        json_name = f"mapped_mcqs_{base_name}.json"

        save_mcqs_txt(mcqs_raw, RESULTS_FOLDER, txt_name)
        save_mcqs_pdf(mcqs_raw, RESULTS_FOLDER, pdf_name)
        with open(os.path.join(RESULTS_FOLDER, json_name), "w", encoding="utf-8") as f:
            json.dump(mapped_mcqs, f, indent=4)

        return JSONResponse({
            "mcqs_raw": mcqs_raw,
            "mapped_mcqs": mapped_mcqs,
            "txt_filename": txt_name,
            "pdf_filename": pdf_name,
            "json_filename": json_name,
        })

    except Exception:
        traceback.print_exc()
        return error("An unexpected error occurred.", 500)


@app.get("/download/{filename}")
async def download_file(filename: str):
    safe_name = secure_filename(filename)
    path = os.path.join(RESULTS_FOLDER, safe_name)
    if not os.path.exists(path):
        return JSONResponse({"error": "File not found."}, status_code=404)
    return FileResponse(path, media_type="application/octet-stream", filename=safe_name)
