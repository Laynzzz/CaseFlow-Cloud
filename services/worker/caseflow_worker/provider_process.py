"""Private provider child. No database/object-store credentials or business commands."""
import json
import os
import sys
from .parser_process import limits

if __name__=='__main__':
    limits() # 512 MiB and one process; the parent also imposes an elapsed-time deadline.
    from openai import OpenAI
    from .provider_transport import MAX_REQUEST_BYTES,MAX_RESPONSE_BYTES
    try:
        raw=sys.stdin.buffer.read(MAX_REQUEST_BYTES+1)
        if len(raw)>MAX_REQUEST_BYTES:raise ValueError('Request too large')
        request=json.loads(raw);operation=request['operation'];arguments=request['arguments']
        if operation not in ('responses','embeddings'):raise ValueError('Unsupported operation')
        with OpenAI(api_key=os.environ['OPENAI_API_KEY'],base_url='https://api.openai.com/v1',max_retries=0,timeout=20.0) as client:
            if operation=='responses':
                result=client.responses.create(**arguments)
                usage=result.usage
                output=dict(status=result.status,model=result.model,output_text=result.output_text,
                            usage=dict(input_tokens=getattr(usage,'input_tokens',None),output_tokens=getattr(usage,'output_tokens',None)))
            else:
                result=client.embeddings.create(**arguments)
                output=dict(model=result.model,usage=dict(total_tokens=getattr(result.usage,'total_tokens',None)),
                            data=[dict(index=row.index,embedding=row.embedding) for row in result.data])
    except Exception as error:
        # Error bodies, exception text and HTTP headers may contain secrets; emit fixed codes only.
        code=getattr(error,'code',None)
        status=getattr(error,'status_code',None)
        if code not in ('insufficient_quota','invalid_api_key','model_not_found','rate_limit_exceeded'):
            code=None if type(status) is int and 400<=status<=599 else 'provider_process_error'
        output=dict(error=dict(code=code,status=status if type(status) is int and 400<=status<=599 else None))
    wire=json.dumps(output,ensure_ascii=True).encode()
    if len(wire)>MAX_RESPONSE_BYTES:sys.exit(2)
    sys.stdout.buffer.write(wire)
