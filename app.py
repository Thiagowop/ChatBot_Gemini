from flask import Flask, request, render_template, session
from markupsafe import escape
import os
from dotenv import load_dotenv
import google.generativeai as genai
import requests
import logging
import time

# Inicializa a aplicação Flask e configura as opções de segurança
app = Flask(__name__)
app.secret_key = os.urandom(24)  # Gera uma chave aleatória para sessões

# Configura o logging
logging.basicConfig(level=logging.INFO)

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    app.logger.error("GOOGLE_API_KEY não está definida no .env!")
    raise ValueError("GOOGLE_API_KEY não está definida no .env!")
genai.configure(api_key=api_key)

# Instancia o modelo desejado (no exemplo, gemini-1.5-pro)
try:
    model = genai.GenerativeModel("gemini-1.5-pro")
except ValueError as e:
    app.logger.error(f"Erro ao instanciar o modelo Gemini: {e}")
    raise ValueError(f"Erro ao instanciar o modelo Gemini: {e}")

def get_google_response(message):
    """
    Envia a mensagem do usuário à API do Google utilizando generate_content
    e retorna o texto da resposta gerada.
    Usa tratamento de exceção para capturar erros durante a comunicação.
    """
    tentativas = 0
    while tentativas < 3:  # Tenta até 3 vezes
        try:
            response = model.generate_content(message)
            if not response or not hasattr(response, "text") or not response.text:
                raise ValueError("Resposta da API Gemini inválida ou vazia.")
            return response.text
        except requests.exceptions.RequestException as e:
            if e.response is not None and e.response.status_code == 429:
                app.logger.warning("Limite de taxa excedido. Aguardando 15 segundos.")
                time.sleep(15)
                tentativas += 1
            else:
                app.logger.error(f"Erro de conexão com a API Gemini: {e}")
                raise ValueError("Erro de conexão com a API Gemini.")
        except Exception as e:
            app.logger.error(f"Erro ao comunicar com a API Gemini: {e}")
            raise ValueError("Erro ao comunicar com a API Gemini.")
    raise ValueError("Falha ao obter resposta da API Gemini após várias tentativas.")

@app.route("/", methods=["GET", "POST"])
def chat():
    # Inicializa a lista de mensagens na sessão, se necessário
    if "messages" not in session:
        session["messages"] = []

    if request.method == "POST":
        user_message = escape(request.form.get("message", ""))
        if user_message:
            try:
                answer = get_google_response(user_message)
                # Verifica se a resposta já foi adicionada
                if not session["messages"] or session["messages"][-1].get("a") != answer:
                    session["messages"].extend([
                        {"is_user": True, "q": user_message},
                        {"is_user": False, "a": answer}
                    ])
                    session.modified = True  # Informa o Flask que a sessão foi modificada
            except ValueError as e:
                app.logger.error(f"Erro na rota de chat: {e}")
                return render_template("index.html", messages=session["messages"], error=f"Ocorreu um erro: {e}")
    return render_template("index.html", messages=session["messages"])

@app.route("/reset", methods=["POST"])
def reset():
    session.pop("messages", None)
    return render_template("index.html", messages=[])

if __name__ == "__main__":
    
    app.run(debug=True)

