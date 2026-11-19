"""Robô gratuito via HTTP: entradas sintéticas → triagem → fila humana → protocolo.

Uma rodada importa; outra emite apenas os registros já aprovados na interface.
Não possui função de aprovação nem envia a autoridades.
"""
import argparse
import csv
import json
import hashlib
import time
from pathlib import Path
import requests


def call(method,url,payload=None):
    for attempt in range(3):
        try:
            r=requests.request(method,url,json=payload,timeout=(3,60))
            if r.status_code>=500 and method=='GET' and attempt<2:
                time.sleep(.25*(attempt+1)); continue
            r.raise_for_status()
            return r.json()
        except requests.ConnectionError:
            if method!='GET' or attempt==2: raise
            time.sleep(.25*(attempt+1))
    raise RuntimeError('Sem resposta')


def run(api,csv_path,log_path,checkpoint,batch_id='bairro-sintetico-v1'):
    log_path=Path(log_path); log_path.parent.mkdir(parents=True,exist_ok=True)
    checkpoint=Path(checkpoint)
    known=json.loads(checkpoint.read_text(encoding='utf-8')) if checkpoint.exists() else {}
    logs=[]
    def log(key,outcome,detail):
        logs.append({'at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'job':key,'outcome':outcome,'detail':detail})
    with Path(csv_path).open(encoding='utf-8-sig',newline='') as f:
        for row in csv.DictReader(f):
            key=row.get('job_id','')
            if not key:
                log('missing','invalid','job_id obrigatório'); continue
            if key in known:
                log(key,'skipped','Entrada já importada; checkpoint local'); continue
            try:
                if row.get('category')!='sound':
                    raise ValueError('Este lote de exemplo aceita relatos sonoros; fotos entram pela interface.')
                if row.get('location_confirmed','').lower()!='true':
                    raise ValueError('Localização não confirmada')
                payload={k:row[k] for k in ['description','neighborhood','category']}
                payload.update(latitude=float(row['latitude']),longitude=float(row['longitude']),location_confirmed=True)
                # Stable across a lost HTTP response or checkpoint write failure.
                payload['client_request_id']='rpa-'+hashlib.sha256(json.dumps([batch_id,key]).encode()).hexdigest()
                result=call('POST',api+'/reports',payload)
                known[key]=result['id']
                checkpoint.parent.mkdir(parents=True,exist_ok=True)
                checkpoint.write_text(json.dumps(known,indent=2),encoding='utf-8')
                log(key,'pending_review','Importado e triado; aguarda revisão na interface')
            except (ValueError,KeyError,requests.RequestException) as e:
                log(key,'failed',type(e).__name__)
    try:
        for report in call('GET',api+'/reports'):
            if report['id'] not in known.values(): continue
            if report['status']=='approved':
                result=call('POST',api+'/reports/'+report['id']+'/protocol')
                log(report['id'],'protocolled',result['protocol'])
    except requests.RequestException as e:
        log('approved_queue','failed',type(e).__name__)
    with log_path.open('a',encoding='utf-8') as f:
        for entry in logs:f.write(json.dumps(entry,ensure_ascii=False)+'\n')
    return logs


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--api',default='http://127.0.0.1:8000')
    p.add_argument('--input',default=str(Path(__file__).parent/'examples/lote-sintetico.csv'))
    p.add_argument('--log',default=str(Path(__file__).parent/'runtime/robot.jsonl'))
    p.add_argument('--checkpoint',default=str(Path(__file__).parent/'runtime/checkpoint.json'))
    p.add_argument('--batch-id',default='bairro-sintetico-v1',help='Identificador estável do lote; preserve ao repetir e use outro para um novo lote.')
    args=p.parse_args()
    print(json.dumps(run(args.api.rstrip('/'),args.input,args.log,args.checkpoint,args.batch_id),ensure_ascii=False,indent=2))
