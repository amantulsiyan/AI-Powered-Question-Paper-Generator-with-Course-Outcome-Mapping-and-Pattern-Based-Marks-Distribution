# app.py
import os
import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template, request, send_file
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
load_dotenv()

from mcq_core import (
    extract_text,
    generate_balanced_mcqs,
    save_mcqs_txt,
    save_mcqs_pdf,
)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads/'
app.config['RESULTS_FOLDER'] = 'results/'
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'txt', 'docx'}

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['RESULTS_FOLDER'], exist_ok=True)


# ------------------- UTIL ------------------- #

def allowed_file(filename: str) -> bool:
    return (
        '.' in filename and 
        filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']
    )


def extract_text_from_url(url: str) -> str:
    """Fetch and extract readable text from a URL."""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Remove scripts, styles, nav bars, etc.
        for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
            tag.extract()

        text = soup.get_text(separator="\n")

        # Clean text
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return "\n".join(lines)

    except Exception as e:
        raise ValueError(f"Failed to extract data from URL: {e}")


# ------------------- ROUTES ------------------- #

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/generate', methods=['POST'])
def generate_mcqs():

    # ---- Detect if URL was provided ---- #
    url_input = request.form.get("url_input", "").strip()

    # ---- CASE 1 — URL INPUT ---- #
    if url_input:
        try:
            text = extract_text_from_url(url_input)
        except Exception as e:
            return f"Error while fetching URL: {e}"

    else:
        # ---- CASE 2 — FILE UPLOAD ---- #
        if 'file' not in request.files:
            return "No file uploaded and no URL provided."

        file = request.files['file']

        if file.filename == '':
            return "No selected file."

        if not allowed_file(file.filename):
            return "Invalid file type. Allowed: PDF, DOCX, TXT."

        # ---- Save uploaded file ---- #
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # ---- Extract text from the file ---- #
        try:
            text = extract_text(filepath)
        except Exception as e:
            return f"Error extracting text: {e}"

    # ---- Get CO list ---- #
    raw_co_text = request.form.get('co_list[]', "").strip()
    co_list = [line.strip() for line in raw_co_text.split("\n") if line.strip()]

    total_questions = int(request.form.get('total_questions', 0))

    if not co_list or total_questions <= 0:
        return "Please provide valid CO list and number of questions."

    # ---- Generate Balanced MCQs ---- #
    try:
        result = generate_balanced_mcqs(text, co_list, total_questions)
        mcqs_raw = result["raw_text"]
        mapped_mcqs = result["mapped_questions"]
    except Exception as e:
        return f"Error generating MCQs: {e}"

    # ---- Save outputs ---- #
    base_name = "generated_from_url" if url_input else filename.rsplit('.', 1)[0]

    txt_name = f"generated_mcqs_{base_name}.txt"
    pdf_name = f"generated_mcqs_{base_name}.pdf"
    json_name = f"mapped_mcqs_{base_name}.json"

    txt_path = save_mcqs_txt(mcqs_raw, app.config['RESULTS_FOLDER'], txt_name)
    pdf_path = save_mcqs_pdf(mcqs_raw, app.config['RESULTS_FOLDER'], pdf_name)

    import json
    json_path = os.path.join(app.config['RESULTS_FOLDER'], json_name)
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(mapped_mcqs, f, indent=4)

    return render_template(
        'result.html',
        mcqs=mcqs_raw,
        mapped_mcqs=mapped_mcqs,
        txt_filename=os.path.basename(txt_path),
        pdf_filename=os.path.basename(pdf_path),
        json_filename=json_name
    )


@app.route('/download/<filename>')
def download_file(filename):
    path = os.path.join(app.config['RESULTS_FOLDER'], filename)
    return send_file(path, as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True)
