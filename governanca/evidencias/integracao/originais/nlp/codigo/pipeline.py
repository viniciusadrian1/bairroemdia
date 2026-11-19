"""Fábrica de corpus reprodutível, local e sem chave de API."""
from __future__ import annotations
import argparse, csv, hashlib, io, json, os, random, re, sys, unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if (ROOT / '.deps').exists():
    # append preserva bibliotecas do ambiente, evitando sobrescrever numpy global.
    sys.path.append(str(ROOT / '.deps'))
from bs4 import BeautifulSoup
from pypdf import PdfReader
from docx import Document
# Apenas tokenização: evita carregar frameworks de inferência desnecessários.
os.environ.setdefault('USE_TORCH','0')
os.environ.setdefault('USE_TF','0')
from transformers import AutoTokenizer
from seeds import QA_TSV, TEST_ROWS, REFUSALS

SOURCES = [
 dict(id='lbi',arquivo='lbi.pdf',titulo='Lei Brasileira de Inclusão da Pessoa com Deficiência',orgao='Brasil; Câmara dos Deputados (texto atualizado)',url='https://www2.camara.leg.br/legin/fed/lei/2015/lei-13146-6-julho-2015-781174-normaatualizada-pl.pdf',data_publicacao='2015-07-07',classificacao='mista: princípios estáveis; redação vigente consultada por RAG'),
 dict(id='lgpd',arquivo='lgpd.pdf',titulo='Lei Geral de Proteção de Dados Pessoais',orgao='Brasil; Câmara dos Deputados (texto atualizado)',url='https://www2.camara.leg.br/legin/fed/lei/2018/lei-13709-14-agosto-2018-787077-normaatualizada-pl.pdf',data_publicacao='2018-08-15',classificacao='mista: direitos gerais estáveis; redação e procedimentos consultados por RAG'),
 dict(id='servicos',arquivo='servicos.pdf',titulo='Lei de participação, proteção e defesa dos usuários dos serviços públicos',orgao='Brasil; Câmara dos Deputados (texto atualizado)',url='https://www2.camara.leg.br/legin/fed/lei/2017/lei-13460-26-junho-2017-785098-normaatualizada-pl.pdf',data_publicacao='2017-06-27',classificacao='mista: linguagem e direitos gerais estáveis; prazos e canais consultados por RAG'),
 dict(id='tapa_buraco',arquivo='tapa_buraco.html',titulo='Solicitar reparo na via pública - tapa buraco',orgao='Governo do Estado de São Paulo',url='https://servicos.sp.gov.br/fcarta/D18A19E4-BB91-4B65-830F-3A0C84D5A4A8',data_publicacao=None,data_atualizacao='2025-03-06',classificacao='volátil: canal, escopo territorial, etapas e prazos; confirmar cidade'),
 dict(id='emergencia',arquivo='emergencia.html',titulo='Emergência: você sabe para quem ligar quando precisa de ajuda?',orgao='Ministério das Comunicações',url='https://www.gov.br/mcom/pt-br/noticias/2026/setembro/emergencia-voce-sabe-para-quem-ligar-quando-precisa-de-ajuda',data_publicacao=None,classificacao='volátil: canais oficiais de emergência; confirmar atualidade'),
]

def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf8')

def jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in rows),encoding='utf8')

def normalize(text):
    return re.sub(r'\s+',' ',unicodedata.normalize('NFC',text).translate(str.maketrans({'“':'"','”':'"','‘':"'",'’':"'",'\u00a0':' '}))).strip()

def extract(data: bytes, name: str) -> list[dict]:
    """PDF, DOCX, HTML, TXT. Texto colado passa pelo formato TXT."""
    suffix=Path(name).suffix.lower()
    if suffix=='.pdf':
        return [{'secao':f'página {i+1}','text':p.extract_text() or ''} for i,p in enumerate(PdfReader(io.BytesIO(data)).pages)]
    if suffix=='.docx':
        doc=Document(io.BytesIO(data))
        text='\n\n'.join(p.text for p in doc.paragraphs)
        text+='\n'+'\n'.join(' | '.join(c.text for c in r.cells) for t in doc.tables for r in t.rows)
        return [{'secao':'documento DOCX','text':text}]
    if suffix in {'.html','.htm'}:
        soup=BeautifulSoup(data,'html.parser')
        for t in soup(['script','style','nav','header','footer','noscript']):t.decompose()
        for t in soup.select('s,strike,del'):t.decompose()
        content=soup.select_one('#content-core') or soup.select_one('#conteudo') or soup.select_one('main') or soup.body or soup
        for t in content.select('#secao-avaliacao,#modalAvaliacao,form,button'):t.decompose()
        return [{'secao':'conteúdo HTML','text':content.get_text('\n',strip=True)}]
    if suffix=='.txt':
        return [{'secao':'texto','text':data.decode('utf-8-sig')}]
    raise ValueError('Formato não aceito. Use PDF, DOCX, HTML ou TXT.')

def clean(pages):
    counts=Counter(line.strip() for p in pages for line in set(p['text'].splitlines()) if line.strip())
    repeated={x for x,n in counts.items() if n>=max(3,len(pages)//2) and len(x)<130}
    result=[]
    for p in pages:
        s=re.sub(r'(\w)-\s*\n\s*(\w)',r'\1\2',p['text'])
        lines=[x.strip() for x in s.splitlines() if x.strip() not in repeated and not re.fullmatch(r'\s*\d+(?:\s*/\s*\d+)?\s*',x) and not re.fullmatch(r'\s*https?://\S+\s*',x)]
        # Retém parágrafos legais e incisos, juntando apenas quebras de diagramação.
        s='\n'.join(lines)
        s=re.sub(r'\n(?!(?:Art\. |[IVXLCDM]+\s*[-–]|§ |CAPÍTULO|TÍTULO|LIVRO|Parágrafo))',' ',s)
        result.append(dict(secao=p['secao'],text=unicodedata.normalize('NFC',s)))
    return result, sorted(repeated)

EXCEPTIONS={'Lei Maria da Penha','Fiocruz','Brasil','União','Constituição Federal','Congresso Nacional','Câmara dos Deputados','Senado Federal','Presidente da República','Presidenta da República','Poder Executivo','Poder Judiciário','Ministério Público','Defensoria Pública','Autoridade Nacional de Proteção de Dados','Agência Nacional de Proteção de Dados'}

class Anonymizer:
    def __init__(self):
        import spacy
        self.nlp=spacy.load('pt_core_news_sm',disable=['parser','lemmatizer'])
        self.nlp.max_length=2_000_000
    def __call__(self,text):
        text=re.sub(r'\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b','[CPF]',text)
        text=re.sub(r'\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b','[EMAIL]',text)
        text=re.sub(r'(?<!\w)(?:\+55\s*)?\(?\d{2}\)?[\s.-]*\d{4,5}[\s.-]*\d{4}(?!\w)','[TELEFONE]',text)
        doc=self.nlp(text)
        for ent in reversed(doc.ents):
            if ent.label_=='PER' and ent.text not in EXCEPTIONS:
                text=text[:ent.start_char]+'[NOME]'+text[ent.end_char:]
        return text

def tokenizer():
    return AutoTokenizer.from_pretrained(ROOT/'modelos/qwen-tokenizer',local_files_only=True)

def segment(pages,tok):
    """Sem overlap; fronteiras de frases/cláusulas. Sobras auditadas, nunca preenchidas."""
    units=[]
    for page in pages:
        for s in re.split(r'(?<=[.!?;])\s+|\n',page['text']):
            s=normalize(s)
            if s: units.append((s,page['secao']))
    size=lambda s:len(tok.encode(s,add_special_tokens=False))
    chunks=[]; current=[]; discarded=[]
    for unit in units:
        if size(unit[0])>512:
            discarded.append({'motivo':'frase maior que 512 tokens; exige edição humana','secao':unit[1],'tokens':size(unit[0])});continue
        candidate=' '.join(x[0] for x in current+[unit])
        if current and size(candidate)>512:
            if size(' '.join(x[0] for x in current))>=256:chunks.append(current)
            else:discarded.append({'motivo':'janela curta antes de frase longa','secao':current[0][1],'tokens':size(' '.join(x[0] for x in current))})
            current=[]
        current.append(unit)
    if current:
        if size(' '.join(x[0] for x in current))>=256:chunks.append(current)
        elif chunks:
            combined=chunks[-1]+current
            # Rebalanceia os dois últimos trechos sem cortar frases.
            split=next((i for i in range(1,len(combined)) if 256<=size(' '.join(x[0] for x in combined[:i]))<=512 and 256<=size(' '.join(x[0] for x in combined[i:]))<=512),None)
            if split:chunks[-1]=combined[:split];chunks.append(combined[split:])
            else:discarded.append({'motivo':'cauda menor que 256 tokens','secao':current[0][1],'tokens':size(' '.join(x[0] for x in current))})
        else:discarded.append({'motivo':'documento curto para janela mínima','secao':current[0][1],'tokens':size(' '.join(x[0] for x in current))})
    return [{'text':' '.join(x[0] for x in c),'secao':f'{c[0][1]} a {c[-1][1]}','tokens':size(' '.join(x[0] for x in c))} for c in chunks],discarded

def article(full,number):
    m=re.search(r'(?:^|\n)Art\.\s*'+re.escape(number)+r'(?:º|o|\.)?\s',full)
    if not m:raise ValueError(f'Artigo não encontrado: {number}')
    tail=full[m.start():]
    next_m=re.search(r'\nArt\.\s*\d',tail[1:])
    return normalize(tail[:next_m.start()+1] if next_m else tail)

def dedup(rows,key):
    seen=set();out=[]
    for r in rows:
        k=normalize(key(r)).casefold()
        if k not in seen:seen.add(k);out.append(r)
    return out,len(rows)-len(out)

def freeze_test():
    dest=ROOT/'artefatos/corpus_teste.jsonl'
    rows=[dict(pergunta=q,resposta_esperada=a,tipo=t,fonte=f,origem='curadoria assistida por IA; revisão humana pendente') for q,a,t,f in TEST_ROWS]
    payload=''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in rows).encode('utf8')
    if dest.exists() and dest.read_bytes()!=payload:raise RuntimeError('Teste congelado divergiu; não será sobrescrito.')
    if not dest.exists():dest.write_bytes(payload)
    sha=hashlib.sha256(payload).hexdigest()
    dump(ROOT/'artefatos/teste-congelado.json',{'sha256':sha,'fase':'gravado e verificado ANTES da geração de treino','data_contexto':'2026-11-10','questoes':len(rows)})
    return rows

def build():
    (ROOT/'artefatos').mkdir(exist_ok=True)
    tests=freeze_test()  # Ordem deliberada; a primeira escrita de corpus é sempre o teste.
    tok=tokenizer();anon=Anonymizer(); texts=[];documents={};manifest=[];discards=[]
    for source in SOURCES:
        path=ROOT/'fontes'/source['arquivo']
        if not path.exists():raise FileNotFoundError(path)
        pages=extract(path.read_bytes(),path.name);cleaned,removed=clean(pages)
        # Assinaturas públicas ao final das leis não ajudam o domínio; não entram no corpus.
        if path.suffix=='.pdf':
            for page in cleaned:
                page['text']=re.split(r'Brasília,?\s+\d',page['text'])[0]
            full='\n'.join(p['text'] for p in cleaned)
            full=re.split(r'Brasília,?\s+\d',full)[0]
            documents[source['id']]=full
        else:documents[source['id']]='\n'.join(p['text'] for p in cleaned)
        anonymized=[dict(secao=p['secao'],text=anon(p['text'])) for p in cleaned]
        chunks,excluded=segment(anonymized,tok)
        for i,c in enumerate(chunks):
            texts.append(dict(c,id=f"{source['id']}-{i+1:04d}",fonte=source['arquivo'],title=source['titulo'],url=source['url'],data=source['data_publicacao'],metadados={**source,'consulta':'2026-11-10','anonimizacao':'regex + spaCy pt_core_news_sm 3.8.0','tokenizador':'Qwen/Qwen2.5-0.5B-Instruct'}))
        manifest.append({**source,'consulta':'2026-11-10','sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'paginas':len(pages) if path.suffix=='.pdf' else None,'palavras_extraidas':sum(len(p['text'].split()) for p in pages),'palavras_limpas':sum(len(normalize(p['text']).split()) for p in cleaned),'trechos':len(chunks),'linhas_repetidas_removidas':removed})
        discards.extend({'fonte':source['arquivo'],**e} for e in excluded)
    qa=[]
    for line in QA_TSV.splitlines():
        doc,art,q,a=line.split('|')
        support=anon(article(documents[doc],art))
        qa.append(dict(instruction=q,input='',output=a,trecho=support,fonte=f'{doc}.pdf',secao=f'Art. {art}',origem='curadoria assistida por IA; revisão humana pendente'))
    # Conversas com segunda pergunta dependente da primeira e referência verificável.
    chats=[]
    selected=[*qa[:8],*qa[27:34],*qa[-5:]]
    for i,row in enumerate(selected):
        chats.append(dict(messages=[{'role':'system','content':'Você orienta sobre serviços públicos com linguagem simples. Use a fonte, proteja dados e não prometa resultado individual.'},{'role':'user','content':row['instruction']},{'role':'assistant','content':row['output']},{'role':'user','content':'e onde tá essa regra que vc explicou?' if i%2==0 else 'Qual é a fonte dessa informação?'},{'role':'assistant','content':f"Essa informação está em {row['fonte']}, {row['secao']}. Consulte a redação e a aplicação pelo canal oficial; este assistente não decide casos individuais."}],fonte=row['fonte'],trecho=row['trecho'],tipo='direta',origem='curadoria assistida por IA; revisão humana pendente'))
    for q,a,q2,a2,source,kind in REFUSALS:
        chats.append(dict(messages=[{'role':'system','content':'Você orienta sobre serviços públicos, protege dados e encaminha urgências aos canais oficiais.'},{'role':'user','content':q},{'role':'assistant','content':a},{'role':'user','content':q2},{'role':'assistant','content':a2}],fonte=source,tipo=kind,origem='curadoria assistida por IA; revisão humana pendente'))
    texts,dt=dedup(texts,lambda r:r['text']);qa,dq=dedup(qa,lambda r:r['instruction']);chats,dc=dedup(chats,lambda r:json.dumps(r['messages'],ensure_ascii=False))
    corpora={'texto':texts,'qa':qa,'chat':chats,'teste':tests}
    stats={};rng=random.Random(564962)
    for name,rows in corpora.items():
        if name!='teste':jsonl(ROOT/f'artefatos/corpus_{name}.jsonl',rows)
        token_sizes=[len(tok.encode(json.dumps(r,ensure_ascii=False),add_special_tokens=False)) for r in rows]
        questions=([r['instruction'] for r in rows] if name=='qa' else [m['content'] for r in rows for m in r['messages'] if m['role']=='user'] if name=='chat' else [r['pergunta'] for r in rows] if name=='teste' else [])
        informal=sum(bool(re.search(r'\b(oq|pra|tb|pq|vc|tá|q|né|tem|me|posso)\b|[?!]{2,}|[A-ZÁÉÍÓÚ]{5,}',q)) and (q[0].islower() or bool(re.search(r'\b(oq|pra|tb|pq|vc|tá|q|né)\b|[?!]{2,}|[A-ZÁÉÍÓÚ]{5,}',q))) for q in questions)
        stats[name]={'exemplos':len(rows),'media_tokens_registro_com_metadados':round(sum(token_sizes)/len(rows),2),'duplicatas_removidas':{'texto':dt,'qa':dq,'chat':dc,'teste':0}[name],'recusas_encaminhamentos':sum(r.get('tipo') in {'recusa','encaminhamento','urgencia','fora_do_tema'} for r in rows),'perguntas_usuario':len(questions),'perguntas_informais_regra_explicita':informal,'proporcao_informal':round(informal/len(questions),3) if questions else None,'cinco_exemplos_indices_1based':[i+1 for i in rng.sample(range(len(rows)),min(5,len(rows)))]}
        jsonl(ROOT/f'evidencias/amostra_{name}.jsonl',[rows[i-1] for i in stats[name]['cinco_exemplos_indices_1based']])
    training_questions={normalize(r['instruction']).casefold() for r in qa}|{normalize(m['content']).casefold() for r in chats for m in r['messages'] if m['role']=='user'}
    leaks=[r['pergunta'] for r in tests if normalize(r['pergunta']).casefold() in training_questions]
    assertions={'texto_min50':len(texts)>=50,'qa_min100':len(qa)>=100,'qa_min3fontes':len({x['fonte'] for x in qa})>=3,'chat_min30':len(chats)>=30,'teste_min20':len(tests)>=20,'texto_tokens_256_512':all(256<=r['tokens']<=512 for r in texts),'sem_questao_teste_no_treino':not leaks,'chat_duas_trocas':all(sum(m['role']=='user' for m in r['messages'])>=2 for r in chats),'informal_min30':all(stats[n]['proporcao_informal']>=.3 for n in ['qa','chat','teste'])}
    sample=rng.sample(range(len(qa)),20)
    automatic=[dict(linha=i+1,fonte=qa[i]['fonte'],secao=qa[i]['secao'],trecho_presente=bool(qa[i]['trecho']),julgamento_semantico_humano='PENDENTE',resposta=qa[i]['output'],trecho=qa[i]['trecho']) for i in sample]
    jsonl(ROOT/'evidencias/fidelidade_amostra20.jsonl',automatic)
    synthetic='Documento fictício. Maria Silva relatou um buraco. CPF: 123.456.789-09. E-mail: maria.sintetica@example.org. Telefone: (11) 99999-1234. A Lei Maria da Penha e a Fiocruz são exceções institucionais.'
    (ROOT/'fontes/documento_ficticio_EXCLUIDO.txt').write_text(synthetic,encoding='utf8')
    dump(ROOT/'evidencias/anonimizacao.json',{'antes_sintetico':synthetic,'depois':anon(synthetic),'entra_nos_corpus':False,'excecoes':sorted(EXCEPTIONS),'limitacao':'NER e regex podem falhar; mascaramento sem mapa não prova anonimização irreversível de texto livre. Revisão humana ainda necessária.'})
    dump(ROOT/'fontes/manifesto.json',manifest);dump(ROOT/'evidencias/trechos_excluidos.json',discards)
    dump(ROOT/'evidencias/qualidade.json',{'tokenizador':'Qwen/Qwen2.5-0.5B-Instruct','overlap':0,'estatisticas':stats,'verificacoes':assertions,'vazamentos_exatos':leaks,'paginas_pdf':sum(r['paginas'] or 0 for r in manifest),'palavras_extraidas_total':sum(r['palavras_extraidas'] for r in manifest),'fidelidade_humana':{'amostra_planejada':20,'conferidos':0,'fieis_confirmados':None},'revisao_humana':{'realizada':0,'minimo_20pct':{k:(len(v)+4)//5 for k,v in corpora.items()},'status':'PENDENTE'},'nota':'Checks automáticos não avaliam qualidade semântica, adequação jurídica ou remoção de todos os dados pessoais.'})
    review=ROOT/'artefatos/revisao.csv'
    if not review.exists():
        with review.open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.writer(f);w.writerow(['arquivo','linha','alterado','comentário'])
            for n,rows in corpora.items():
                for i in range((len(rows)+4)//5):w.writerow([f'corpus_{n}.jsonl',i+1,'','PENDENTE: preencher após leitura humana'])
    dump(ROOT/'artefatos/geracao.json',{'modelo_assistente':'Codex / GPT-6 (identidade informada pelo ambiente; sem versão de backend confirmada)','metodo':'perguntas e respostas curadas por assistente de IA e materializadas em seeds.py; build determinístico sem chamada LLM','prompt':'Produzir perguntas acessíveis em português sobre fontes oficiais, com respostas fiéis, artigos de apoio, variação informal e recusas; não inventar revisão humana. Ver seeds.py para conteúdo integral.','treino_executado':False,'revisao_humana':'pendente'})
    print(json.dumps({'verificacoes':assertions,'contagens':{k:len(v) for k,v in corpora.items()}},ensure_ascii=False,indent=2))
    if not all(assertions.values()):raise RuntimeError('Há verificações quantitativas não atendidas; consulte qualidade.json')
    return corpora

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=['build'],nargs='?',default='build');parser.parse_args();build()
