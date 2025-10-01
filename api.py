from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
import os, json, re

# -------------------- Configuração --------------------
app = FastAPI()

# CORS - permitir chamadas do frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # você pode colocar seu site aqui
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# -------------------- Helpers JSON --------------------
def try_load_json(text):
    try:
        return json.loads(text)
    except:
        return None

def extract_between_brackets(text):
    first, last = text.find("["), text.rfind("]")
    if first != -1 and last != -1 and last > first:
        return text[first:last+1]
    return None

def fix_common_issues(text):
    s = text.replace("None", "null").replace("True", "true").replace("False", "false")
    s = re.sub(r"(?<!\\)'", '"', s)
    s = re.sub(r",\s*([\]\}])", r"\1", s)
    return s

def safe_parse_json(text):
    for variant in [text, extract_between_brackets(text) or "", fix_common_issues(text)]:
        try:
            return json.loads(variant)
        except:
            pass
    return None

# -------------------- Modelos --------------------
class QuizRequest(BaseModel):
    conteudo: str
    nivel: str
    n_questoes: int = 5

class RespostaRequest(BaseModel):
    pergunta: str
    resposta_aluno: str
    resposta_correta: str

# -------------------- Funções de Validação --------------------
def validar_questoes(questoes):
    questoes_validas = []
    for q in questoes:
        if (
            isinstance(q, dict)
            and "pergunta" in q
            and "opcoes" in q
            and "resposta_correta" in q
        ):
            # garante que resposta_correta esteja dentro de opcoes
            if q["resposta_correta"] not in q["opcoes"]:
                # tenta corrigir escolhendo a primeira opção como fallback
                q["resposta_correta"] = q["opcoes"][0]
            questoes_validas.append(q)
    return questoes_validas

# -------------------- Endpoints --------------------
@app.post("/gerar_questoes")
def gerar_questoes(data: QuizRequest):
    prompt = f"""
Gere {data.n_questoes} questões originais sobre o tema: "{data.conteudo}", no nível: "{data.nivel}".

⚠️ IMPORTANTE:
- Cada questão deve ter 1 resposta correta e 3 incorretas.
- O campo "resposta_correta" deve conter exatamente o TEXTO de uma das opções listadas em "opcoes".
- Nunca responda com apenas "A", "B", "C" ou "D". Sempre escreva o texto exato da alternativa correta.
- Retorne apenas JSON válido, sem explicações adicionais.

Formato JSON válido:
[
  {{
    "pergunta": "Texto completo da pergunta",
    "opcoes": ["Opção 1", "Opção 2", "Opção 3", "Opção 4"],
    "resposta_correta": "Texto exato de uma das opções"
  }}
]
"""
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"user","content":prompt}],
            temperature=0.4,
            max_tokens=1800
        )
        content = resp.choices[0].message.content
        parsed = safe_parse_json(content)
        if not parsed:
            return {"erro": "Não foi possível gerar JSON válido", "resposta": content}

        # validação das questões
        questoes_validas = validar_questoes(parsed)
        return questoes_validas
    except Exception as e:
        return {"erro": str(e)}

@app.post("/analisar_resposta")
def analisar_resposta(data: RespostaRequest):
    prompt = f"""
Explique resumidamente o possível erro do aluno nesta questão:
Pergunta: {data.pergunta}
Resposta correta: {data.resposta_correta}
Resposta do aluno: {data.resposta_aluno}
"""
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"user","content":prompt}],
            temperature=0
        )
        return {"feedback": resp.choices[0].message.content}
    except Exception as e:
        return {"erro": str(e)}

# -------------------- Configuração para Render --------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
