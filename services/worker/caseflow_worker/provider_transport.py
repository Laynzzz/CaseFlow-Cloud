"""Provider I/O in a disposable child with a parent-enforced elapsed-time deadline."""
import json
import os
import subprocess
import sys
from types import SimpleNamespace

DEADLINE_SECONDS=30
MAX_REQUEST_BYTES=262144
MAX_RESPONSE_BYTES=4*1024*1024


class ProviderBoundaryError(Exception):
    def __init__(self,code,status_code=None):
        super().__init__('Provider transport failed')
        self.code=code;self.status_code=status_code


def safe_error_code(error):
    code=getattr(error,'code',None);status=getattr(error,'status_code',None)
    if code in ('insufficient_quota','invalid_api_key','model_not_found','rate_limit_exceeded','provider_time_limit','provider_process_error'):
        return code.upper() if code.startswith('provider_') else 'PROVIDER_'+code.upper()
    return f'PROVIDER_HTTP_{status}' if type(status) is int and 400<=status<=599 else 'PROVIDER_UNAVAILABLE'


def child_environment():
    allowed={'path','systemroot','windir','systemdrive','temp','tmp','pathext','pythonpath','pythonhome',
             'home','userprofile','ssl_cert_file','ssl_cert_dir','https_proxy','http_proxy','no_proxy','openai_api_key'}
    return {key:value for key,value in os.environ.items() if key.lower() in allowed}


def run_child(command,payload,timeout=DEADLINE_SECONDS):
    wire=json.dumps(payload,ensure_ascii=True).encode()
    if len(wire)>MAX_REQUEST_BYTES:raise ProviderBoundaryError('provider_process_error')
    try:
        process=subprocess.run(command,input=wire,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
            timeout=timeout,check=False,env=child_environment(),
            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    except subprocess.TimeoutExpired:
        # subprocess.run kills and waits for its child before raising. Unknown billing stays reserved.
        raise ProviderBoundaryError('provider_time_limit') from None
    except OSError:
        raise ProviderBoundaryError('provider_process_error') from None
    if process.returncode!=0 or len(process.stdout)>MAX_RESPONSE_BYTES:
        raise ProviderBoundaryError('provider_process_error')
    try:return json.loads(process.stdout)
    except (ValueError,UnicodeError):raise ProviderBoundaryError('provider_process_error') from None


def as_object(value):
    if isinstance(value,dict):return SimpleNamespace(**{k:as_object(v) for k,v in value.items()})
    if isinstance(value,list):return [as_object(v) for v in value]
    return value


class Endpoint:
    def __init__(self,operation):self.operation=operation
    def create(self,**arguments):
        response=run_child([sys.executable,'-m','caseflow_worker.provider_process'],dict(operation=self.operation,arguments=arguments))
        if not isinstance(response,dict):raise ProviderBoundaryError('provider_process_error')
        if 'error' in response:
            error=response['error']
            if not isinstance(error,dict):raise ProviderBoundaryError('provider_process_error')
            raise ProviderBoundaryError(error.get('code'),error.get('status'))
        return as_object(response)


class BoundedProvider:
    def __init__(self):self.responses=Endpoint('responses');self.embeddings=Endpoint('embeddings')
    def close(self):pass
