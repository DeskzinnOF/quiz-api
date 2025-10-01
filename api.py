from fastapi import FastAPI
from pydantic import BaseModel
from openai import OpenAI
import json, re
import os

app = FastAPI()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ---------- helpers de JSON ----------
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
    s = text.replace("None","null").replace("True","true").replace("False","false")
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

# ---------- modelos ----------
class QuizRequest(BaseModel):
    conteudo: str
    nivel: str
    n_questoes: int = 5

class RespostaRequest(BaseModel):
    pergunta: str
    resposta_aluno: str
    resposta_correta: str

# ---------- endpoints ----------
@app.post("/gerar_questoes")
def gerar_questoes(data: QuizRequest):
    prompt = f"""
Gere {data.n_questoes} questões originais sobre o tema: "{data.conteudo}", no nível: "{data.nivel}".
Formato JSON:
[
  {{
    "pergunta": "Texto completo da pergunta",
    "opcoes": ["A", "B", "C", "D"],
    "resposta_correta": "A"
  }}
]
"""
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role":"user","content":prompt}],
        temperature=0.4,
        max_tokens=1800
    )
    content = resp.choices[0].message.content
    parsed = safe_parse_json(content)
    return parsed or {"erro":"Não foi possível gerar JSON válido", "resposta": content}

@app.post("/analisar_resposta")
def analisar_resposta(data: RespostaRequest):
    prompt = f"""
Explique resumidamente o possível erro do aluno nesta questão:
Pergunta: {data.pergunta}
Resposta correta: {data.resposta_correta}
Resposta do aluno: {data.resposta_aluno}
"""
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role":"user","content":prompt}],
        temperature=0
    )
    return {"feedback": resp.choices[0].message.content}
