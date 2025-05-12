from flask import Flask, render_template
import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__)

# Carrega as credenciais
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)

# Inicializa o Firestore
db = firestore.client()

@app.route('/')
def index():
    cursos_ref = db.collection("cursos")
    docs = cursos_ref.stream()
    cursos = [{**doc.to_dict(), "id": doc.id} for doc in docs] 
    return render_template("index.html", cursos=cursos)

@app.route("/curso/<curso_id>")
def detalhes_curso(curso_id):
    doc_ref = db.collection("cursos").document(curso_id)
    doc = doc_ref.get()
    if doc.exists:
        curso = doc.to_dict()
        return render_template("curso_detalhes.html", curso=curso, curso_id=curso_id)
    else:
        return "Curso não encontrado", 404

if __name__ == "__main__":
    app.run(debug=True)