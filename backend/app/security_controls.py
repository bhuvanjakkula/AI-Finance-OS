"""HTTP defence in depth and fail-closed production prerequisites."""
import os
from fastapi import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from .pqc_security import keys

def validate_production():
    if os.getenv('FINANCE_ENV')!='production': return
    if os.getenv('FINANCE_LOCAL_OWNER_ACCESS','false').lower()=='true': raise RuntimeError('Passwordless local owner access must be disabled in production')
    if not os.getenv('FINANCE_KEYRING_FILE'): raise RuntimeError('Production requires explicit managed keyring path')
    keys()
    if os.getenv('ALLOW_REGISTRATION','false').lower()=='true': raise RuntimeError('Disable public registration before production startup')
    if os.getenv('FINANCE_AUTO_CREATE','true').lower()=='true': raise RuntimeError('Production requires explicit migrations')
    if not os.getenv('FINANCE_ALLOWED_HOSTS'): raise RuntimeError('Production requires explicit trusted hosts')
    if os.getenv('FINANCE_REQUIRE_HTTPS','true').lower()!='true': raise RuntimeError('Production requires HTTPS')

class SecurityHeaders(BaseHTTPMiddleware):
    async def dispatch(self,request,call_next):
        if os.getenv('FINANCE_ENV')=='production' and request.url.scheme!='https':
            response=JSONResponse({'detail':'HTTPS required'},status_code=400)
        else:
            length=request.headers.get('content-length')
            if length and (not length.isdecimal() or int(length)>8_000_000):
                response=JSONResponse({'detail':'Request body too large or invalid length'},status_code=413)
            else:
                chunks=[];size=0
                async for chunk in request.stream():
                    size+=len(chunk)
                    if size>8_000_000: break
                    chunks.append(chunk)
                if size>8_000_000: response=JSONResponse({'detail':'Request body too large'},status_code=413)
                else:
                    request._body=b''.join(chunks)
                    response=await call_next(request)
        response.headers.update({'X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY','Referrer-Policy':'no-referrer','Permissions-Policy':'camera=(), microphone=(), geolocation=()','Cache-Control':'no-store'})
        if request.url.scheme=='https': response.headers['Strict-Transport-Security']='max-age=31536000'
        if request.url.path not in ('/docs','/redoc','/docs/oauth2-redirect'): response.headers['Content-Security-Policy']="default-src 'none'; frame-ancestors 'none'"
        return response
