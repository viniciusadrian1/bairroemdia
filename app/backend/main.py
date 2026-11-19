import logging
import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from backend.routers.api import router

app=FastAPI(title='Bairro em Dia',version='0.3.0',description='Protótipo educacional; gestor e protocolos internos simulados.')
origins=[x.strip() for x in os.getenv('CORS_ORIGINS','http://localhost:8502,http://127.0.0.1:8502').split(',') if x.strip()]
if '*' in origins:
    raise RuntimeError('Configure origens explícitas em CORS_ORIGINS.')
app.add_middleware(CORSMiddleware,allow_origins=origins,allow_methods=['GET','POST'],allow_headers=['Content-Type'],allow_credentials=False)


@app.middleware('http')
async def limit_size(request:Request,call_next):
    # Also checks streamed requests; Content-Length alone is not trusted.
    limit=8_000_000
    if request.method in ('POST','PUT','PATCH'):
        body=bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body)>limit:
                return JSONResponse(status_code=413,content={'detail':'O envio deve ter até 8 MB.'})
        request._body=bytes(body)
    return await call_next(request)


@app.exception_handler(Exception)
async def unexpected(request,exc):
    logging.getLogger('bairro').error('Falha interna: %s',type(exc).__name__)
    return JSONResponse(status_code=500,content={'detail':'Não foi possível concluir. Tente novamente; nenhuma ação externa foi enviada.'})


app.include_router(router)
