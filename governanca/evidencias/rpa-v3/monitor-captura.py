"""Read-only execution monitor plus a fixed local run button for robot.py.

No approval function. Real robot and API; synthetic batch, separate checkpoint.
Bind only to loopback. This monitor is a demonstration aid, not the citizen UI.
"""
import csv
import importlib.util
import json
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

FOLDER=Path(__file__).resolve().parents[1]
RUNTIME=FOLDER/'runtime/video-rpa-movimento-20261119'
EVIDENCE=FOLDER/'evidencias/video-rpa-movimento-20261119'
RUNTIME.mkdir(parents=True,exist_ok=True)
EVIDENCE.mkdir(parents=True,exist_ok=True)
CSV=EVIDENCE/'lote-video.csv'
if not CSV.exists():
    with (FOLDER/'dados/lote-sintetico.csv').open(encoding='utf8') as f:
        reader=csv.DictReader(f); rows=list(reader); fields=reader.fieldnames
    for i,row in enumerate(rows):
        row['neighborhood']=f'Demo RPA movimento • {i+1:02d}'
        row['description']='Demonstração sintética para vídeo RPA. '+row['description']
    with CSV.open('w',encoding='utf8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)
spec=importlib.util.spec_from_file_location('robot_demo_original',FOLDER/'robot.py')
robot=importlib.util.module_from_spec(spec);spec.loader.exec_module(robot)
API='http://127.0.0.1:8000'
LOCK=threading.RLock()
state={'running':False,'run':0,'events':[],'result':[],'reports':[],'error':None}
previous=sorted(EVIDENCE.glob('execucao-*.json'))
if previous:
    saved=json.loads(previous[-1].read_text(encoding='utf8'))
    state.update({key:saved[key] for key in state if key in saved})
    state['running']=False
original_call=robot.call
def emit(text):
    with LOCK:state['events'].append({'time':datetime.now().strftime('%H:%M:%S'),'text':text})
def monitored_call(method,url,payload=None):
    route=urlparse(url).path
    if method=='POST' and route=='/reports':
        emit('IMPORTANDO  '+payload['neighborhood'])
    elif method=='POST':emit('EMITINDO PROTOCOLO  '+route.split('/')[2][:8])
    try:result=original_call(method,url,payload)
    except Exception as e:
        code=getattr(getattr(e,'response',None),'status_code',None)
        emit(f'ENTRADA RECUSADA  HTTP {code}' if code else f'FALHA  {type(e).__name__}')
        raise
    if method=='POST' and route=='/reports':emit('CRIADO  '+result['id'][:8]+'  • aguardando revisão')
    elif method=='POST':emit('PROTOCOLO  '+result['protocol'])
    return result
robot.call=monitored_call
def execute():
    started=time.time()
    emit('EXECUTANDO robot.py • API local • lote sintético')
    try:
        result=robot.run(API,CSV,EVIDENCE/'robot.jsonl',RUNTIME/'checkpoint.json','video-rpa-movimento-20261119-v2')
        known=json.loads((RUNTIME/'checkpoint.json').read_text()) if (RUNTIME/'checkpoint.json').exists() else {}
        reports=[{'id':r['id'],'status':r['status'],'protocol':r.get('protocol'),'neighborhood':r['neighborhood']} for r in original_call('GET',API+'/reports') if r['id'] in known.values()]
        with LOCK:state['result']=result;state['reports']=reports
        emit('CONCLUÍDO  • importados: '+str(sum(x['outcome']=='pending_review' for x in result))+' • já importados: '+str(sum(x['outcome']=='skipped' for x in result)))
        emit('PROTOCOLOS NESTA EXECUÇÃO: '+str(sum(x['outcome']=='protocolled' for x in result)))
    except Exception as e:
        with LOCK:state['error']=type(e).__name__
        emit('ERRO  '+type(e).__name__)
    finally:
        with LOCK:
            state['running']=False
            evidence={**state,'duration_seconds':time.time()-started,'at_utc':datetime.now(timezone.utc).isoformat(),'approval':'No approval performed by monitor or robot. UI demonstration is agent-assisted, not a human study.'}
            (EVIDENCE/f"execucao-{state['run']:02d}.json").write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf8')

HTML=r'''<!doctype html><html lang="pt-br"><meta charset="utf-8"><title>Bairro em Dia — execução RPA</title>
<style>*{box-sizing:border-box}body{margin:0;background:#fff5e5;color:#392d25;font:18px Segoe UI,Arial}main{max-width:1140px;margin:auto;padding:28px 32px}header{display:flex;justify-content:space-between;align-items:center;border-bottom:2px solid #ba422f;padding-bottom:14px}h1{font:italic bold 29px Georgia;margin:0;color:#ba422f}h2{font: bold 31px Georgia;margin:22px 0 12px}p{margin:10px 0}.tag{font-size:14px;color:#786c60}button{background:#ba422f;color:white;border:0;border-radius:8px;padding:13px 24px;font:bold 18px Segoe UI;cursor:pointer}button:disabled{opacity:.55}.row{display:flex;align-items:center;justify-content:space-between;margin:18px 0}.console{height:285px;overflow:auto;background:#262722;color:#edf1e5;border-radius:10px;padding:14px 18px;font:15px/1.6 Consolas,monospace;white-space:pre-wrap}table{width:100%;border-collapse:collapse;font-size:15px}td,th{text-align:left;padding:10px;border-bottom:1px solid #ddcdb8}th{font-weight:600}.counts{display:flex;gap:12px;margin:17px 0}.counts>div{background:#f1e4d1;padding:13px 20px;border-radius:8px;flex:1}.counts b{font-size:27px;color:#ba422f;display:block}.status{font-weight:600;color:#4b6942}.foot{font-size:14px;line-height:1.45;color:#76695c;margin-top:18px}</style>
<main><header><h1>bairro em dia</h1><span class="tag">MONITOR LOCAL • EXECUÇÃO REAL DO ROBÔ</span></header>
<h2>Da planilha à fila de revisão</h2><p>Lote sintético: 3 relatos válidos e 1 latitude inválida.</p>
<div class="row"><button id="run" onclick="start()">Executar robô</button><span id="status" class="status">Pronto para executar</span></div>
<div id="console" class="console">robot.py → API local → revisão → protocolo interno\n\nO robô não aprova ocorrências. A revisão acontece na aplicação.</div>
<div class="counts"><div><b id="valid">0</b>relatos no lote</div><div><b id="pending">0</b>aguardando revisão</div><div><b id="protocols">0</b>com protocolo interno</div></div>
<table><thead><tr><th>Registro</th><th>Situação real na API</th><th>Protocolo</th></tr></thead><tbody id="reports"></tbody></table>
<p class="foot">Este monitor executa o robot.py do projeto e mostra seus retornos reais. Dados sintéticos; nenhum envio a autoridades. A aprovação é feita separadamente na interface.</p></main>
<script>let last=''; const names={pending_review:'Aguardando revisão',approved:'Aprovado na interface',protocolled:'Protocolo interno criado'};
async function start(){document.getElementById('run').disabled=true;await fetch('/run',{method:'POST'});await refresh()}
async function refresh(){let s=await(await fetch('/state')).json();document.getElementById('run').disabled=s.running;document.getElementById('run').textContent=s.run?'Executar novamente':'Executar robô';document.getElementById('status').textContent=s.running?'Robô em execução…':(s.run?'Execução '+s.run+' concluída':'Pronto para executar');let txt=s.events.map(e=>e.time+'  '+e.text).join('\n');if(txt&&txt!==last){let c=document.getElementById('console');c.textContent=txt;c.scrollTop=c.scrollHeight;last=txt}document.getElementById('valid').textContent=s.reports.length;document.getElementById('pending').textContent=s.reports.filter(r=>r.status==='pending_review').length;document.getElementById('protocols').textContent=s.reports.filter(r=>r.protocol).length;let tb=document.getElementById('reports');tb.replaceChildren();for(let r of s.reports){let tr=document.createElement('tr');for(let val of [r.neighborhood,names[r.status]||r.status,r.protocol?r.protocol.slice(0,12)+'…':'Ainda não criado']){let td=document.createElement('td');td.textContent=val;tr.append(td)}tb.append(tr)}}setInterval(refresh,350);refresh();</script></html>'''
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def send(self,code,data,kind):
        self.send_response(code);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(data)
    def do_GET(self):
        if self.path=='/':self.send(200,HTML.encode(),'text/html; charset=utf-8')
        elif self.path=='/state':
            with LOCK:data=json.dumps(state,ensure_ascii=False).encode()
            self.send(200,data,'application/json')
        else:self.send(404,b'Not found','text/plain')
    def do_POST(self):
        if self.path!='/run' or self.headers.get('Origin','http://127.0.0.1:8766')!='http://127.0.0.1:8766':
            self.send(403,b'Forbidden','text/plain');return
        with LOCK:
            if state['running']:self.send(409,b'Running','text/plain');return
            state.update(running=True,run=state['run']+1,events=[],result=[],error=None)
            threading.Thread(target=execute,daemon=True).start()
        self.send(202,b'{}','application/json')
if __name__=='__main__':
    print('Monitor RPA http://127.0.0.1:8766',flush=True)
    ThreadingHTTPServer(('127.0.0.1',8766),Handler).serve_forever()

