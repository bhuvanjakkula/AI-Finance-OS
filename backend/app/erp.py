"""Read-only ERP transports with bounded retries and safe pagination."""
import os, re, time, json
from urllib.parse import urlparse
from decimal import Decimal
from datetime import date
import httpx

class ConnectorError(Exception): pass

class ReadOnlyConnector:
    def __init__(self,config,secret,transport=None):
        self.config=config;self.secret=secret
        self.client=httpx.Client(timeout=20,transport=transport,follow_redirects=False)
    def close(self): self.client.close()
    def request(self,method,url,**kwargs):
        for attempt in range(3):
            try:
                response=self.client.request(method,url,**kwargs)
                if response.status_code in (429,500,502,503,504) and attempt<2:
                    time.sleep(.2*(2**attempt));continue
                if response.status_code>=400: raise ConnectorError(f'Provider returned HTTP {response.status_code}; check credentials, scopes and mapping')
                data=response.json()
                if not isinstance(data,dict): raise ConnectorError('Unexpected provider response')
                return data
            except (httpx.HTTPError,ValueError) as exc:
                if attempt==2: raise ConnectorError('Provider request failed or returned invalid JSON') from exc
        raise ConnectorError('Provider unavailable')

class BusinessCentralConnector(ReadOnlyConnector):
    def __init__(self,config,secret,transport=None):
        super().__init__(config,secret,transport)
        for field in ('tenant_id','company_id'):
            if not re.fullmatch(r'[0-9a-fA-F-]{36}',config.get(field,'')): raise ConnectorError(f'Invalid {field}')
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',config.get('environment','')): raise ConnectorError('Invalid environment')
        self.base=f"https://api.businesscentral.dynamics.com/v2.0/{config['tenant_id']}/{config['environment']}/api/v2.0/companies({config['company_id']})/"
    def token(self):
        try: credentials=json.loads(self.secret)
        except ValueError: return self.secret
        if credentials.get('access_token'): return credentials['access_token']
        for key in ('client_id','client_secret'):
            if not credentials.get(key): raise ConnectorError('Missing Entra client credentials')
        data=self.request('POST',f"https://login.microsoftonline.com/{self.config['tenant_id']}/oauth2/v2.0/token",data={'grant_type':'client_credentials','client_id':credentials['client_id'],'client_secret':credentials['client_secret'],'scope':'https://api.businesscentral.dynamics.com/.default'})
        if not data.get('access_token'): raise ConnectorError('Entra token response missing access token')
        return data['access_token']
    def fetch_page(self,cursor=None):
        url=cursor or self.base+'generalLedgerEntries?$top=1000&$orderby=entryNumber'
        parsed=urlparse(url);base=urlparse(self.base)
        if parsed.scheme!='https' or parsed.netloc!=base.netloc or not parsed.path.startswith(base.path): raise ConnectorError('Unsafe provider pagination URL')
        data=self.request('GET',url,headers={'Authorization':'Bearer '+self.token(),'Accept':'application/json'})
        rows=data.get('value',[])
        if not isinstance(rows,list): raise ConnectorError('Ledger response must be a list')
        return {'rows':rows,'cursor':data.get('@odata.nextLink')}
    def normalize(self,rows,currency):
        mapping=self.config.get('account_mapping',{});groups={}
        for row in rows:
            # Business Central amounts are signed: positive is debit.
            code=str(row['accountNumber']);mapped=mapping.get(code,code)
            key=f"{row['postingDate']}:{row['documentNumber']}"
            group=groups.setdefault(key,{'external_id':key,'posting_date':row['postingDate'],'currency':currency,'description':str(row.get('description',''))[:500],'lines':[]})
            value=Decimal(str(row['amount']))
            group['lines'].append({'account_code':mapped,'debit':str(max(value,Decimal('0'))),'credit':str(max(-value,Decimal('0'))),'reference':str(row.get('documentNumber',''))[:160]})
        return list(groups.values())

class NetSuiteConnector(ReadOnlyConnector):
    def __init__(self,config,secret,transport=None):
        super().__init__(config,secret,transport)
        if not re.fullmatch(r'[a-z0-9-]{1,80}',config.get('account_id','')): raise ConnectorError('Invalid NetSuite REST account hostname')
        self.base=f"https://{config['account_id']}.suitetalk.api.netsuite.com/services/rest/query/v1/suiteql"
    def fetch_page(self,cursor=None):
        query=os.getenv(self.config.get('query_env',''),'')
        # Deployment-controlled query; require explicit column aliases in normalized rows.
        if not query.strip().upper().startswith('SELECT ') or ';' in query: raise ConnectorError('Configure a single read-only SuiteQL SELECT in the query environment variable')
        offset=int(cursor or '0')
        if offset<0: raise ConnectorError('Invalid SuiteQL offset')
        data=self.request('POST',self.base,params={'limit':1000,'offset':offset},headers={'Authorization':'Bearer '+self.secret,'Prefer':'transient','Content-Type':'application/json'},json={'q':query})
        rows=data.get('items',[])
        if not isinstance(rows,list): raise ConnectorError('SuiteQL items must be a list')
        return {'rows':rows,'cursor':str(offset+len(rows)) if data.get('hasMore') else None}
    def normalize(self,rows,currency):
        groups={};mapping=self.config.get('account_mapping',{})
        for row in rows:
            key=str(row['external_id'])
            group=groups.setdefault(key,{'external_id':key,'posting_date':str(row['posting_date'])[:10],'currency':currency,'description':str(row.get('description',''))[:500],'lines':[]})
            code=str(row['account_code'])
            group['lines'].append({'account_code':mapping.get(code,code),'debit':str(row.get('debit') or '0'),'credit':str(row.get('credit') or '0'),'reference':str(row.get('reference') or key)[:160]})
        return list(groups.values())

CONNECTORS={'business_central':BusinessCentralConnector,'netsuite':NetSuiteConnector}
