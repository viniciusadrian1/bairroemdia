"""Read-only offline checks of the V3 capture records. No network or new robot run."""
from pathlib import Path
import json,hashlib,collections
P=Path(__file__).resolve().parent
def verify():
 checks=[]
 def check(ok,label):
  if not ok:raise ValueError(label)
  checks.append(label)
 prov=json.loads((P/'proveniencia.json').read_text(encoding='utf8'))
 for row in prov['files']:
  check(hashlib.sha256((P/row['file']).read_bytes()).hexdigest()==row['sha256'],'Integridade: '+row['file'])
 runs=[json.loads((P/f'execucao-{i:02d}.json').read_text(encoding='utf8')) for i in [1,2,3]]
 check(all(r['error'] is None and not r['running'] for r in runs),'Três execuções concluídas sem falha global')
 check(all(len(r['reports'])==3 for r in runs),'Três relatos válidos em cada estado final')
 ids=[{x['id'] for x in r['reports']} for r in runs]
 check(ids[0]==ids[1]==ids[2],'Identificadores preservados nas retomadas')
 check(all(x['status']=='pending_review' and x['protocol'] is None for r in runs[:2] for x in r['reports']),'Nenhum protocolo antes da revisão')
 check(sum(x['outcome']=='pending_review' for x in runs[0]['result'])==3,'Primeira execução importou três relatos')
 check(sum(x['outcome']=='skipped' for x in runs[1]['result'])==3,'Segunda execução retomou sem importar novamente')
 check(all(sum(x['outcome']=='failed' for x in r['result'])==1 for r in runs),'Entrada inválida recusada em cada tentativa')
 check(all(any('HTTP 422' in x['text'] for x in r['events']) for r in runs),'Validação HTTP 422 registrada')
 last=runs[2]['reports'];counts=collections.Counter(x['status'] for x in last)
 check(counts=={'pending_review':2,'protocolled':1},'Estado final: um protocolado e dois pendentes')
 check(sum(x['protocol'] is not None for x in last)==1,'Um único protocolo no estado final')
 check(sum(x['outcome']=='protocolled' for x in runs[2]['result'])==1,'Terceira execução emitiu um protocolo')
 return {'status':'passed','checks':checks,'capture':'V3, 19/11/2026','final_states':dict(counts),'limits':['Conferência dos registros preservados, sem reexecutar robô ou modelos.','Revisão assistida na interface; não é estudo com usuários.','V3 não demonstra rejeição nem nova repetição após emitir protocolo; ensaio anterior está em ../rpa/.']}
if __name__=='__main__':print(json.dumps(verify(),ensure_ascii=False,indent=2))
