# app.py
import os
import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template, request, send_file
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import traceback

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
        '.' in filename
        and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']
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
    # error_message is optional; index.html will handle if it's missing
    return render_template('index.html')


@app.route('/generate', methods=['POST'])
def generate_mcqs():

    try:
        # ---- Detect if URL was provided ---- #
        url_input = request.form.get("url_input", "").strip()

        # ---- CASE 1 — URL INPUT ---- #
        if url_input:
            try:
                text = extract_text_from_url(url_input)
            except Exception as e:
                return render_template('index.html', error_message=f"Error while fetching URL: {e}")
            filename = None

        else:
            # ---- CASE 2 — FILE UPLOAD ---- #
            if 'file' not in request.files:
                return render_template('index.html', error_message="No file uploaded and no URL provided.")

            file = request.files['file']

            if file.filename == '':
                return render_template('index.html', error_message="No selected file.")

            if not allowed_file(file.filename):
                return render_template(
                    'index.html',
                    error_message="Invalid file type. Allowed: PDF, DOCX, TXT."
                )

            # ---- Save uploaded file ---- #
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            try:
                file.save(filepath)
            except Exception as e:
                traceback.print_exc()
                return render_template('index.html', error_message=f"Failed to save uploaded file: {e}")

            # ---- Extract text from the file ---- #
            try:
                text = extract_text(filepath)
            except Exception as e:
                traceback.print_exc()
                return render_template('index.html', error_message=f"Error extracting text: {e}")

        # ---- Get CO list ---- #
        raw_co_text = request.form.get('co_list[]', "").strip()
        co_list = [line.strip() for line in raw_co_text.split("\n") if line.strip()]

        # validate questions count
        try:
            total_questions = int(request.form.get('total_questions', 0))
        except ValueError:
            return render_template('index.html', error_message="Invalid number for total questions.")

        if not co_list or total_questions <= 0:
            return render_template(
                'index.html',
                error_message="Please provide valid CO list and number of questions."
            )

        # ---- Generate Balanced MCQs ---- #
        try:
            result = generate_balanced_mcqs(text, co_list, total_questions)
            mcqs_raw = result.get("raw_text", "")
            mapped_mcqs = result.get("mapped_questions", [])
        except Exception as e:
            traceback.print_exc()  # full JSON still goes to console

            err = str(e).lower()

            if "rate_limit_exceeded" in err or "rate limit" in err:
                friendly = (
                    "The AI service has reached its usage limit for now. "
                    "Please try again after some time or with fewer questions."
                )
            else:
                friendly = (
                    "Error generating MCQs. Please try again later "
                    "or reduce the number of questions."
                )

            return render_template('index.html', error_message=friendly)


        # ---- Save outputs ---- #
        base_name = "generated_from_url" if url_input else filename.rsplit('.', 1)[0]

        txt_name = f"generated_mcqs_{base_name}.txt"
        pdf_name = f"generated_mcqs_{base_name}.pdf"
        json_name = f"mapped_mcqs_{base_name}.json"

        try:
            txt_path = save_mcqs_txt(mcqs_raw, app.config['RESULTS_FOLDER'], txt_name)
            pdf_path = save_mcqs_pdf(mcqs_raw, app.config['RESULTS_FOLDER'], pdf_name)
        except Exception as e:
            traceback.print_exc()
            return render_template('index.html', error_message=f"Failed to save result files: {e}")

        import json
        json_path = os.path.join(app.config['RESULTS_FOLDER'], json_name)
        try:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(mapped_mcqs, f, indent=4)
        except Exception as e:
            traceback.print_exc()
            return render_template('index.html', error_message=f"Failed to save mapping JSON: {e}")

        return render_template(
            'result.html',
            mcqs=mcqs_raw,
            mapped_mcqs=mapped_mcqs,
            txt_filename=os.path.basename(txt_path),
            pdf_filename=os.path.basename(pdf_path),
            json_filename=json_name
        )

    except Exception as outer_e:
        traceback.print_exc()
        return render_template('index.html', error_message="An unexpected error occurred. Please check the server logs.")


@app.route('/download/<filename>')
def download_file(filename):
    path = os.path.join(app.config['RESULTS_FOLDER'], filename)
    if not os.path.exists(path):
        return render_template('index.html', error_message="Requested file not found.")
    return send_file(path, as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True)
