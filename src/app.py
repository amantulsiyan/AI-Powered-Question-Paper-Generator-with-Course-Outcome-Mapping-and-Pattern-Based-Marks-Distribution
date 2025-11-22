# app.py
import os
from flask import Flask, render_template, request, send_file
from werkzeug.utils import secure_filename

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


# ------------------- ROUTES ------------------- #

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/generate', methods=['POST'])
def generate_mcqs():
    # ---- File check ---- #
    if 'file' not in request.files:
        return "No file uploaded."

    file = request.files['file']
    if not file or not allowed_file(file.filename):
        return "Invalid file type. Upload a PDF / DOCX / TXT."

    filename = secure_filename(file.filename)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)

    # ---- Number of questions ---- #
    try:
        total_questions = int(request.form.get('num_questions', '5'))
    except ValueError:
        return "Invalid number of questions."

    # ---- CO input ---- #
    co_raw = request.form.get("co_descriptions", "").strip()
    if not co_raw:
        return "No COs provided."

    co_list = [co.strip() for co in co_raw.split("\n") if co.strip()]
    if len(co_list) == 0:
        return "No valid COs provided."

    # ---- Extract text ---- #
    try:
        text = extract_text(file_path)
    except Exception as e:
        return f"Error reading file: {e}"

    # ---- Generate Balanced MCQs per CO ---- #
    try:
        mcqs = generate_balanced_mcqs(text, co_list, total_questions)
    except Exception as e:
        return f"Error generating MCQs: {e}"

    # ---- Save output files ---- #
    base_name = filename.rsplit('.', 1)[0]
    txt_name = f"generated_mcqs_{base_name}.txt"
    pdf_name = f"generated_mcqs_{base_name}.pdf"

    txt_path = save_mcqs_txt(mcqs, app.config['RESULTS_FOLDER'], txt_name)
    pdf_path = save_mcqs_pdf(mcqs, app.config['RESULTS_FOLDER'], pdf_name)

    # ---- Render ---- #
    return render_template(
        'result.html',
        mcqs=mcqs,
        txt_filename=os.path.basename(txt_path),
        pdf_filename=os.path.basename(pdf_path)
    )


@app.route('/download/<filename>')
def download_file(filename):
    path = os.path.join(app.config['RESULTS_FOLDER'], filename)
    return send_file(path, as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True)
