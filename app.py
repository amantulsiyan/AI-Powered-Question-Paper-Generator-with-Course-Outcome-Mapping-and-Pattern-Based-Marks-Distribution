# app.py
import os
from flask import Flask, render_template, request, send_file
from werkzeug.utils import secure_filename

from mcq_core import (
    generate_mcqs_from_file,
    save_mcqs_txt,
    save_mcqs_pdf,
)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads/'
app.config['RESULTS_FOLDER'] = 'results/'
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'txt', 'docx'}

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['RESULTS_FOLDER'], exist_ok=True)

def allowed_file(filename: str) -> bool:
    return (
        '.' in filename and
        filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']
    )

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate_mcqs():
    if 'file' not in request.files:
        return "No file uploaded."

    file = request.files['file']
    if not file or not allowed_file(file.filename):
        return "Invalid file format or upload error."

    filename = secure_filename(file.filename)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)

    try:
        num_questions = int(request.form.get('num_questions', '5'))
    except ValueError:
        return "Invalid number of questions."

    try:
        mcqs = generate_mcqs_from_file(file_path, num_questions)
    except Exception as e:
        return f"Error while generating MCQs: {e}"

    base_name = filename.rsplit('.', 1)[0]
    txt_name = f"generated_mcqs_{base_name}.txt"
    pdf_name = f"generated_mcqs_{base_name}.pdf"

    txt_path = save_mcqs_txt(mcqs, app.config['RESULTS_FOLDER'], txt_name)
    pdf_path = save_mcqs_pdf(mcqs, app.config['RESULTS_FOLDER'], pdf_name)

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
