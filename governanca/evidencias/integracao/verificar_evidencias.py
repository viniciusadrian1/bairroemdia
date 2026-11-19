"""Recalcula evidências históricas sem rede, modelos, banco ou dependências externas.

Execute com Python 3.10+ a partir de qualquer diretório. Não executa novas
inferências e não avalia a fidelidade semântica do corpus ou das respostas.
"""
from pathlib import Path
from collections import Counter
from statistics import mean
import csv
import hashlib
import json
import math
import sys
import unicodedata

ROOT = Path(__file__).resolve().parent
ORIG = ROOT/'originais'

def require(condition, message):
    if not condition:
        raise ValueError(message)

def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def rows(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def lines(path):
    return [json.loads(s) for s in path.read_text(encoding='utf8').splitlines() if s.strip()]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def close(a,b,label):
    require(math.isclose(a,b,rel_tol=1e-8,abs_tol=1e-8),label)

def norm(s):
    return ' '.join(unicodedata.normalize('NFKC',s).casefold().split())

def iou(a,b):
    intersection=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
    union=(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-intersection
    return intersection/union if union else 0

def verify():
    provenance=read(ROOT/'proveniencia.json')['files']
    for item in provenance:
        p=ROOT/item['path']
        require(p.is_file() and sha(p)==item['sha256'],f"Integridade: {item['path']}")
    result={'scope':'Recalculation of historical records; no new inference or human evaluation',
            'original_files_sha256_verified':len(provenance)}

    # Reconstruct reference boxes, then independently match saved detections.
    predictions=read(ORIG/'visao/predictions.json')
    metrics=read(ORIG/'visao/metrics.json')
    gt={}; selected=[]
    for r in predictions:
        boxes=[]
        for line in (ORIG/'visao/labels'/(Path(r['image']).stem+'.txt')).read_text().splitlines():
            cls,x,y,w,h=map(float,line.split())
            require(cls==0,'Classe de referência inesperada')
            boxes.append([(x-w/2)*r['width'],(y-h/2)*r['height'],(x+w/2)*r['width'],(y+h/2)*r['height']])
        require(len(boxes)==r['ground_truth_count'],'Contagem de referência')
        gt[r['image']]=boxes
        selected.extend((r['image'],d) for d in r['detections'] if d['confidence']>=metrics['operating_confidence'])
    matched={name:set() for name in gt}; tp=0
    for name,d in sorted(selected,key=lambda x:x[1]['confidence'],reverse=True):
        overlap,index=max(((iou(d['bbox'],b),i) for i,b in enumerate(gt[name]) if i not in matched[name]),default=(0,-1))
        if overlap>=metrics['operating_iou']:
            matched[name].add(index); tp+=1
    total=sum(map(len,gt.values())); fp=len(selected)-tp; fn=total-tp
    computed={'tp':tp,'fp':fp,'fn':fn,'precision':tp/len(selected),'recall':tp/total}
    for k,v in computed.items(): close(v,metrics['operating_metrics'][k],'Visão: '+k)
    require(len(gt)==12 and total==27,'Amostra de visão')
    result['visao']={'images':len(gt),'reference_boxes':total,**computed}

    nlp=ORIG/'nlp'
    corpus=lines(ROOT.parents[2]/'app/resources/corpus_texto.jsonl')
    qa=lines(nlp/'corpus_qa.jsonl'); chat=lines(nlp/'corpus_chat.jsonl'); test=lines(nlp/'corpus_teste.jsonl')
    quality=read(nlp/'qualidade.json')
    counts={'texto':len(corpus),'qa':len(qa),'chat':len(chat),'teste':len(test)}
    for k,v in counts.items(): require(v==quality['estatisticas'][k]['exemplos'],'NLP: '+k)
    training={norm(r['instruction']) for r in qa}
    training.update(norm(m['content']) for r in chat for m in r['messages'] if m['role']=='user')
    leaked=training & {norm(r['pergunta']) for r in test}
    require(not leaked,'Pergunta de teste repetida no treino')
    require(sha(nlp/'corpus_teste.jsonl')==read(nlp/'teste-congelado.json')['sha256'],'Hash do teste congelado')
    require(all(256<=r['tokens']<=512 for r in corpus),'Metadados de tokens')
    require(all(r['fonte'] and r['secao'] and r['url'] for r in corpus),'Metadados de origem')
    result['nlp']={**counts,'exact_test_questions_in_training':len(leaked),
                   'token_check':'recorded metadata only; tokenizer not rerun',
                   'human_review':quality['revisao_humana']['status']}

    capacity=read(ORIG/'capacidade/resultados-integracao.json')
    times={}
    for s in capacity['scenarios']:
        model=ORIG/'capacidade/models'/Path(s['model']).name
        require(sha(model)==s['model_sha256'],'Hash modelo iSPD')
        runs=sorted((ORIG/'capacidade/results').glob(s['id']+'_run*.json'))
        require(len(runs)==3,'Três repetições por cenário')
        observed=[]
        for p in runs:
            r=read(p); tasks=r['tasks']
            require(len(tasks)==120 and len({t['id'] for t in tasks})==120,'120 tarefas distintas')
            require(all(t['completed'] for t in tasks),'Tarefa incompleta')
            counts=Counter(t['resource_node_number'] for t in tasks)
            require(len(counts)==s['workers'] and set(counts.values())=={120//s['workers']},'Distribuição de tarefas')
            close(sum(t['compute_mflop'] for t in tasks),7200000,'Conservação do trabalho')
            duration=r['global']['TempoSimulacao']
            close(duration,s['total_simulated_time_s'],'Tempo simulado')
            require(max(max(t['processing_finish_s']) for t in tasks)<=duration,'Tarefa após fim da simulação')
            observed.append(duration)
        times[str(s['workers'])]=mean(observed)
    reduction=100*(1-times['4']/times['2']); ratio=times['2']/times['4']
    close(reduction,capacity['derived']['reduction_percent'],'Redução simulada')
    close(ratio,capacity['derived']['ratio_t2_t4'],'Razão simulada')
    result['capacidade']={'runs':6,'simulated_seconds':times,'reduction_percent':reduction,'ratio':ratio}

    perf=ORIG/'desempenho/visao-real'
    calls=rows(perf/'chamadas.csv'); runs=rows(perf/'execucoes.csv')
    require(len(calls)==153 and len(runs)==27,'Amostra de desempenho')
    require(all(c['status']=='ok' and c['detections_equal_reference']=='True' for c in calls),'Inferência divergente')
    for r in runs:
        batch=[c for c in calls if c['run_id']==r['run_id']]
        require(len(batch)==int(r['batch_calls']),'Tamanho de lote')
        close(mean(float(c['model_lock_wait_ms']) for c in batch),float(r['model_lock_wait_mean_ms']),'Espera por bloqueio')
    waits={}
    for threads in [1,4]:
        subset=[r for r in runs if r['batch_calls']=='12' and int(r['threads'])==threads]
        require(len(subset)==3,'Repetições do lote 12')
        waits[str(threads)]=mean(float(r['model_lock_wait_mean_ms']) for r in subset)
    for summary in rows(perf/'resumo.csv'):
        subset=[r for r in runs if r['batch_calls']==summary['batch_calls'] and r['threads']==summary['threads']]
        close(mean(float(r['model_lock_wait_mean_ms']) for r in subset),float(summary['model_lock_wait_mean_ms']),'Resumo do bloqueio')
    http=ORIG/'desempenho/http-visao-real'
    hc=rows(http/'chamadas.csv'); hr=rows(http/'execucoes.csv')
    require(len(hc)==51 and len(hr)==9,'Amostra HTTP')
    require(all(c['http_status']=='200' and c['mode']=='model' for c in hc),'Falha HTTP')
    result['desempenho']={'inferences':len(calls),'batches':len(runs),'batch_12_mean_lock_wait_ms':waits,'http_successes':len(hc)}

    assistant=read(ORIG/'assistente/avaliacao-final.json')
    require(len(assistant['cases'])==13 and assistant['model']=='qwen2.5:3b','Avaliação histórica do assistente')
    result['assistente']={'cases':len(assistant['cases']),'model':assistant['model'],'semantic_quality':'not established by this checker'}
    sound=read(ORIG/'som/results-20261118T225238Z.json')
    samples={s['id']:s for s in read(ORIG/'som/manifest.json')['files']}
    outcomes=[]
    for r in sound['results']:
        sample=samples[r['sample']['id']]; event=r['event']; analysis=event['analysis']
        require(event['audio_sha256']==sample['wav_sha256'],'Hash da entrada sonora')
        predicted=analysis['neighborhood_source']['label']
        agrees=predicted==sample['expected']
        require(agrees==r['prediction_matches_reference'],'Concordância sonora')
        outcomes.append({'expected':sample['expected'],'predicted':predicted,'matches':agrees})
    require(len(outcomes)==3,'Três exemplos de áudio')
    result['som']={'exploratory_examples':outcomes,'note':'Not a general accuracy estimate; no decibel measurement'}
    return {'status':'passed',**result}

if __name__=='__main__':
    try:
        print(json.dumps(verify(),ensure_ascii=True,indent=2))
    except (ValueError,KeyError,OSError,ZeroDivisionError) as exc:
        print(json.dumps({'status':'failed','error':str(exc)},ensure_ascii=True),file=sys.stderr)
        sys.exit(1)
