"""Bounded one-request legacy HTTP reading; no credential storage or retries."""
import http.client,urllib.request,urllib.error
VERSION='bounded-raw-http-v2'


def redact(raw,key,complete):
    secret=key.encode();changed=secret in raw
    raw=raw.replace(secret,b'[CREDENTIAL_REDACTED]')
    if not complete:
        for size in range(len(secret)-1,0,-1):
            if raw.endswith(secret[:size]):
                raw=raw[:-size]+b'[CREDENTIAL_REDACTED]';changed=True;break
    return raw,changed


def once(endpoint,data,timeout,key,redirect_handler,limit):
    if endpoint!='https://api.openai.com/v1/responses':raise ValueError('fixed endpoint only')
    request=urllib.request.Request(endpoint,data=data,headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),redirect_handler)
    try:response=opener.open(request,timeout=timeout)
    except urllib.error.HTTPError as error:response=error
    chunks=[];size=0;read_error=None
    with response:
        headers={k:response.headers.get(k) for k in ('x-request-id','openai-processing-ms','retry-after') if response.headers.get(k) is not None}
        code=response.status if hasattr(response,'status') else response.code
        reader=getattr(response,'read1',response.read)
        chunked=getattr(response,'chunked',False)
        declared=response.headers.get('Content-Length')
        declared=int(declared) if not chunked and isinstance(declared,str) and declared.isascii() and declared.isdecimal() else None
        while size<limit+1:
            try:
                piece=reader(min(65536,limit+1-size))
                if not isinstance(piece,bytes):raise ValueError('HTTP bytes required')
                if not piece:
                    # read1() can silently close a short Content-Length body.
                    remaining=getattr(response,'length',None)
                    if (isinstance(remaining,int) and remaining>0) or (declared is not None and size<declared):
                        read_error='read_failure'
                    elif chunked and (getattr(response,'chunk_left',None) is not None or not response.isclosed()):
                        read_error='read_failure'
                    break
                piece=piece[:limit+1-size];chunks.append(piece);size+=len(piece)
            except http.client.IncompleteRead as error:
                piece=error.partial[:limit+1-size];chunks.append(piece);size+=len(piece);read_error='read_failure';break
            except TimeoutError:read_error='timeout';break
            except urllib.error.URLError as error:
                read_error='timeout' if isinstance(error.reason,TimeoutError) else 'read_failure';break
            except Exception:read_error='read_failure';break
    complete=read_error is None and size<=limit
    raw,redacted=redact(b''.join(chunks),key,complete)
    headers={k:str(v).replace(key,'[CREDENTIAL_REDACTED]') for k,v in headers.items()}
    return code,headers,raw,complete,redacted,dict(version=VERSION,read_error=read_error)
