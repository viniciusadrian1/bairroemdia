import json
import os
import re
import unicodedata
from pathlib import Path
from backend.providers import llm
from backend.schemas import AssistantResponse
from .privacy import mask

ROOT=Path(__file__).resolve().parents[2]
BASE=Path(__file__).resolve().parents[1]/'data'/'knowledge.json'
STOP=set('a o os as de do da dos das um uma que como qual quais e para por no na em eu meu minha voce posso pode favor'.split())


def normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFD',text.lower()) if unicodedata.category(c)!='Mn')


def tokens(text):
    return set(re.findall(r'\w+',normalize(text)))-STOP


def load_knowledge(with_warnings=False):
    rows=json.loads(BASE.read_text(encoding='utf-8'))
    warnings=[]
    path=Path(os.getenv('NLP_CORPUS_PATH',str(ROOT/'resources/corpus_texto.jsonl')))
    if path.exists():
        try:
            lines=path.read_text(encoding='utf-8-sig').splitlines()
        except (OSError,UnicodeError):
            lines=[]
            warnings.append('O corpus NLP não pôde ser lido; a base operacional continua disponível.')
        invalid=0
        for i,line in enumerate(lines):
            if not line.strip(): continue
            try:
                row=json.loads(line)
                if not isinstance(row,dict) or not isinstance(row.get('text'),str) or not row['text'].strip():
                    raise ValueError('Trecho inválido')
                meta=row.get('metadados',{})
                if not isinstance(meta,dict):raise ValueError('Metadados inválidos')
                rows.append({'id':f'nlp-{i+1}','title':str(row.get('fonte','NLP'))+' / '+str(row.get('secao','')),
                             'url':str(row.get('url',meta.get('url',meta.get('link','local://corpus_texto.jsonl')))),
                             'text':row['text']})
            except (ValueError,TypeError):
                invalid+=1
        if invalid:
            warnings.append(f'{invalid} trecho(s) inválido(s) do corpus NLP foram excluídos; a consulta usa a parte válida da base.')
    else:
        warnings.append('Corpus NLP não disponível; a consulta usa a base operacional.')
    return (rows,warnings) if with_warnings else rows


def retrieve(question, k=3, rows=None):
    query=tokens(question)
    ranked=[]
    for row in rows if rows is not None else load_knowledge():
        if malicious(row['text']): continue
        match=query & tokens(row['text']+' '+row['title'])
        score=len(match)/max(1,len(query))
        if score>=.25 and match:
            ranked.append((score, row))
    ranked.sort(key=lambda pair:pair[0], reverse=True)
    return [{'id':r['id'],'title':r['title'],'url':r['url'],'excerpt':r['text']} for _,r in ranked[:k]]


def malicious(text):
    s=normalize(text)
    return bool(re.search(r'ignore (as |todas |previous|instru)|revele.*(senha|prompt|segredo)|system prompt|api[_ -]?key|exfiltr|<script|ignore.*instruc',s))


def response(answer, sources=None, abstained=True, mode='policy', warnings=None):
    return AssistantResponse(answer=answer,sources=sources or [],abstained=abstained,
                             mode=mode,warnings=warnings or []).model_dump()


def answer(question, history=None):
    history=history or []
    question=mask(question)
    s=normalize(question)
    if malicious(question) or any(malicious(m['content']) for m in history):
        return response('Não posso seguir instruções para expor dados ou alterar as regras. Posso orientar sobre relatos de pavimentação e acessibilidade sonora.')
    if any(w in s for w in ['ferid','desmai','sangrand','risco imediato','incendio']):
        return response('Este protótipo não atende emergências. Afaste-se do risco e procure imediatamente o serviço de emergência competente da sua região. Não aguarde um protocolo interno.')
    if re.search(r'(dia exato|prazo exato|quando.*(consert|repar)|valor.*multa|quantos decibeis)',s):
        return response('A base não permite afirmar prazo de reparo, valor de multa ou medição de decibéis. Consulte o órgão competente; a análise requer verificação humana.')
    query=question
    # Follow-up retrieval uses only prior user turns, never generated answers as facts.
    if len(tokens(question))<=3 and history:
        prior=next((m['content'] for m in reversed(history) if m['role']=='user'),'')
        query=prior+' '+question
    if not tokens(query) & set('buraco buracos asfalto pavimentacao rua bairro protocolo sp156 som sonoro sonora campainha batida ambiente privacidade cpf foto localizacao dados solicitar'.split()):
        return response('Não encontrei uma pergunta específica sobre o Bairro em Dia. Descreva o problema de pavimentação ou acessibilidade sonora e indique sua dúvida.')
    rows,base_warnings=load_knowledge(with_warnings=True)
    sources=retrieve(query,rows=rows)
    if not sources:
        return response('Não há evidência suficiente na base para responder. Detalhe sua dúvida ou consulte a carta de serviços do seu município.')
    warnings=list(base_warnings)
    mode=os.getenv('LLM_MODE','extractive')
    if mode=='ollama':
        try:
            generated=llm.generate(question,[{**m,'content':mask(m['content'])} for m in history],sources)
            selected=[x for x in sources if x['id'] in generated.source_ids]
            valid_ids=set(generated.source_ids)<=set(x['id'] for x in sources)
            quotes_ok=all(q and any(q in x['excerpt'] for x in selected) for q in generated.evidence_quotes)
            if not generated.abstained and (not selected or not generated.evidence_quotes or not valid_ids or not quotes_ok):
                raise ValueError('Resposta sem sustentação verificável')
            return response(mask(generated.answer), selected,generated.abstained,'ollama',warnings+
                            ['Resposta gerada: confira as fontes e revise antes de agir. Citações válidas não garantem todas as afirmações.'])
        except Exception:
            warnings.append('O modelo não respondeu com evidências válidas. Exibimos a orientação documental disponível.')
    text='Orientação documental (sem geração por LLM):\n\n'+ '\n\n'.join(f"{x['excerpt']} [{x['id']}]" for x in sources[:2])
    return response(text,sources[:2],False,'extractive',warnings)
