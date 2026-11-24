"""LM Studio OpenAI-compatible REST client. Loopback-only by design."""
from __future__ import annotations

import json
import re
import socket
from urllib.parse import urlparse
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError

DEFAULT_URL = 'http://127.0.0.1:1234/v1'
# Non-streaming requests deliver nothing until generation completes, so the
# socket timeout bounds the WHOLE local generation. CPU-only inference (the
# recommended Vulkan fallback) routinely needs several minutes per pass.
DEFAULT_TIMEOUT = 600


class LMStudioError(RuntimeError):
    """LM Studio API failure (never modifies local forecasts on its own)."""


class LMStudioHTTPError(LMStudioError):
    def __init__(self, status, detail):
        self.status = int(status)
        self.detail = detail
        super().__init__(f'LM Studio HTTP {status}: {detail}')


class LMStudioTimeoutError(LMStudioError):
    """The server was reachable but did not finish inside the client timeout."""


class LMStudioContextError(LMStudioHTTPError):
    """The prompt plus reply did not fit the model's loaded context window."""

    def __init__(self, status, detail):
        LMStudioError.__init__(
            self,
            'LOCAL MODEL CONTEXT WINDOW EXCEEDED.\n'
            'The evidence packet plus the requested reply is larger than the context length '
            'the model was loaded with in LM Studio.\n\n'
            '1. Set OVERCAST\'s CONTEXT selector to the context length shown in LM Studio '
            '(8K, 16K or 32K). OVERCAST then shortens excerpts to fit.\n'
            '2. Or reload the model in LM Studio with a larger context length, if memory allows.\n'
            '3. Or select fewer headlines / a narrower scope.\n\n'
            f'Engine diagnostic (HTTP {status}): {detail[:900]}')
        self.status = int(status)
        self.detail = detail


class LMStudioDeviceLostError(LMStudioError):
    """GPU-side Vulkan failure. Never silently retry a failed compute submission."""

    def __init__(self, status, detail):
        self.status = int(status)
        self.detail = detail
        super().__init__(
            'VULKAN GPU DEVICE LOST (LM Studio inference engine).\n'
            'The GPU stopped responding while the local model was processing this request. '
            'This is not a news-source or forecast-validation error.\n\n'
            '1. Unload the affected model and restart LM Studio.\n'
            '2. Reload it with context length 8192, reduce GPU offload and leave memory headroom; '
            'then set OVERCAST\'s CONTEXT selector to 8K so prompts fit.\n'
            '3. Test a small Q4 model with a short prompt directly in LM Studio.\n'
            '4. If failures persist, test CPU-only inference or another supported backend/runtime '
            '(slower: OVERCAST waits up to 10 minutes per model call).\n'
            '5. Check LM Studio engine logs and your graphics driver if this also fails in its chat.\n\n'
            'OVERCAST stopped the analysis without automatically reissuing the crashed request. '
            'No incomplete forecast is saved.\n\n'
            f'Engine diagnostic (HTTP {status}): {detail[:1400]}'
        )


class LMStudioGPUMemoryError(LMStudioDeviceLostError):
    """GPU allocation failure. Subclasses device loss so pipelines fail fast too."""

    def __init__(self, status, detail):
        self.status = int(status)
        self.detail = detail
        LMStudioError.__init__(
            self,
            'GPU OUT OF MEMORY (LM Studio inference engine).\n'
            'The local model could not allocate graphics memory for this request.\n\n'
            '1. Reduce GPU offload layers or context length for this model in LM Studio.\n'
            '2. Set OVERCAST\'s CONTEXT selector to match (8K is lightest).\n'
            '3. Close other GPU-heavy programs, or use a smaller quantisation.\n\n'
            'OVERCAST stopped the analysis without retrying. No incomplete forecast is saved.\n\n'
            f'Engine diagnostic (HTTP {status}): {detail[:1200]}')


def _device_lost(detail):
    lower = detail.lower()
    return (('errordevicelost' in lower or 'device lost' in lower or 'device_lost' in lower)
            and ('vk::' in lower or 'vk:' in lower or 'vulkan' in lower or 'decode() failed' in lower))


def _gpu_memory(detail):
    lower = detail.lower()
    return any(term in lower for term in (
        'erroroutofdevicememory', 'out of device memory', 'cudaerrormemoryallocation',
        'cuda out of memory', 'failed to allocate vram', 'insufficient vram'))


def _context_overflow(detail):
    lower = detail.lower()
    return any(term in lower for term in (
        'context length', 'context window', 'context size', 'exceeds the context',
        'n_ctx', 'context overflow', 'maximum context', 'too many tokens',
        'prompt is too long', 'trying to keep the first'))


def _unsupported_json_format(error):
    """Only retry if the server specifically rejected structured output support."""
    detail = error.detail.lower()
    return error.status in (400, 422) and any(term in detail for term in (
        'response_format', 'json_object', 'json schema', 'json_schema',
        'grammar is not supported', 'unsupported grammar',
    ))


def is_chat_model(model_id):
    """LM Studio lists embedding models beside chat models; they cannot answer prompts."""
    lower = model_id.lower()
    return not ('embed' in lower or lower.startswith('text-embedding'))


class LMStudioClient:
    def __init__(self, base_url=DEFAULT_URL, timeout=DEFAULT_TIMEOUT):
        base_url=base_url.rstrip('/')
        parsed=urlparse(base_url)
        if parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1','localhost','::1') or parsed.path not in ('/v1','/v1/') or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('For privacy and safety, LM Studio must use a loopback HTTP URL ending in /v1.')
        if parsed.port is not None and not (1 <= parsed.port <= 65535):
            raise ValueError('Invalid local LM Studio port.')
        self.base_url=base_url
        self.timeout=timeout
        # Learned once per client: LM Studio rejects {"type":"json_object"}, so
        # later calls skip the doomed first request instead of repeating it.
        self._json_mode=True

    def _request(self, method, path, payload=None, timeout=None):
        body=None if payload is None else json.dumps(payload).encode('utf-8')
        req=Request(self.base_url+path,data=body,method=method,
                    headers={'Accept':'application/json','Content-Type':'application/json'})
        limit=timeout or self.timeout
        try:
            with urlopen(req,timeout=limit) as response:
                raw=response.read(4_000_001)
        except HTTPError as exc:
            detail=exc.read(8192).decode('utf-8',errors='replace')
            if _device_lost(detail):
                raise LMStudioDeviceLostError(exc.code, detail) from exc
            if _gpu_memory(detail):
                raise LMStudioGPUMemoryError(exc.code, detail) from exc
            if _context_overflow(detail):
                raise LMStudioContextError(exc.code, detail) from exc
            raise LMStudioHTTPError(exc.code, detail) from exc
        except (TimeoutError, socket.timeout) as exc:
            raise LMStudioTimeoutError(_timeout_message(limit)) from exc
        except URLError as exc:
            if isinstance(exc.reason,(TimeoutError,socket.timeout)):
                raise LMStudioTimeoutError(_timeout_message(limit)) from exc
            raise LMStudioError('Cannot reach LM Studio. Start the Local Server in LM Studio and load a model. '+str(exc)) from exc
        except OSError as exc:
            raise LMStudioError('Cannot reach LM Studio. Start the Local Server in LM Studio and load a model. '+str(exc)) from exc
        if len(raw)>4_000_000:
            raise LMStudioError('LM Studio response was unexpectedly large.')
        try:
            return json.loads(raw.decode('utf-8'))
        except (UnicodeDecodeError,ValueError) as exc:
            raise LMStudioError('LM Studio returned invalid JSON.') from exc

    def models(self):
        """Loaded/available model IDs, chat models first, embedding models last."""
        result=self._request('GET','/models',timeout=8)
        ids=[row['id'] for row in result.get('data',[]) if isinstance(row,dict) and row.get('id')]
        return sorted(ids,key=lambda m:not is_chat_model(m))

    def complete(self, model_id, system, user, max_tokens=1800, temperature=0.2):
        if not model_id:
            raise LMStudioError('Select a loaded model first.')
        if not is_chat_model(model_id):
            raise LMStudioError(f'{model_id!r} is an embedding model and cannot write reports. '
                                'Select a chat/instruction model in the LOCAL MODEL box.')
        temperature=min(max(float(temperature),0.0),1.5)
        payload={'model':model_id,'temperature':temperature,'max_tokens':max_tokens,'stream':False,
                 'messages':[{'role':'system','content':system},{'role':'user','content':user}]}
        if self._json_mode:
            payload['response_format']={'type':'json_object'}
        try:
            result=self._request('POST','/chat/completions',payload)
        except LMStudioHTTPError as exc:
            # Only a documented structured-output incompatibility merits a retry.
            # In particular, a GPU device loss wrapped inside HTTP 400 must not
            # re-run the inference request and risk another driver failure.
            if 'response_format' not in payload or not _unsupported_json_format(exc):
                raise
            self._json_mode=False
            payload.pop('response_format')
            result=self._request('POST','/chat/completions',payload)
        try:
            choice=result['choices'][0]
            content=choice['message']['content']
        except (KeyError,IndexError,TypeError) as exc:
            raise LMStudioError('LM Studio did not return message content (model may have exhausted its token budget).') from exc
        if isinstance(content,list):
            content='\n'.join(c.get('text','') for c in content if isinstance(c,dict))
        if content is None:
            content=''
        if not isinstance(content,str):
            raise LMStudioError('LM Studio returned no text content.')
        try:
            return parse_json_response(content)
        except LMStudioError:
            if isinstance(choice,dict) and choice.get('finish_reason')=='length':
                raise LMStudioError(
                    f'The local model ran out of its {max_tokens}-token reply budget before finishing '
                    'the JSON answer. Reasoning ("thinking") models often spend the budget on hidden '
                    'reasoning: disable thinking for this model in LM Studio, or choose a '
                    'non-reasoning instruction model.') from None
            raise


_THINK = re.compile(r'<(think|thinking|reasoning)>.*?</\1>', re.IGNORECASE | re.DOTALL)


def parse_json_response(content):
    """Extract one JSON object from a local model reply.

    Handles markdown fences, reasoning-model <think> blocks (including an
    unterminated one) and prose before/after the object. Never repairs or
    invents fields: the first complete top-level object wins.
    """
    s=_THINK.sub('',content or '')
    lowered=s.lower()
    # A stray closing tag (opening tag consumed by the server): the answer follows it.
    for tag in ('</think>','</thinking>','</reasoning>'):
        pos=lowered.rfind(tag)
        if pos>=0:
            s=s[pos+len(tag):]
            lowered=s.lower()
    # An opening tag left unclosed means the model stopped mid-reasoning; anything
    # after it is unfinished reasoning, never an answer.
    for tag in ('<think>','<thinking>','<reasoning>'):
        pos=lowered.find(tag)
        if pos>=0:
            s=s[:pos]
            lowered=s.lower()
    s=s.strip()
    s=re.sub(r'^```(?:json)?\s*|\s*```$', '',s,flags=re.IGNORECASE).strip()
    try:
        value=json.loads(s)
    except json.JSONDecodeError:
        value=None
        decoder=json.JSONDecoder()
        for match in re.finditer(r'\{',s):
            try:
                candidate,_end=decoder.raw_decode(s,match.start())
            except json.JSONDecodeError:
                continue
            if isinstance(candidate,dict):
                value=candidate
                break
        if value is None:
            if '{' not in s:
                raise LMStudioError('Model did not return a JSON object. Try an instruction-following model.') from None
            raise LMStudioError('Model response was not valid JSON. Retry with a different model.') from None
    if not isinstance(value,dict):
        raise LMStudioError('Model returned JSON but not an object.')
    return value


def _timeout_message(seconds):
    return (f'LM Studio did not finish this request within {int(seconds)} seconds. '
            'The server is reachable, but the model is too slow for this request size '
            '(common with CPU-only inference or large models). Select fewer headlines, set '
            'MODEL CONTEXT to 8K, or use a smaller/faster model. Nothing was saved.')
