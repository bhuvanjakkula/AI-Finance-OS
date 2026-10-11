from test_platform import workspace, member


def test_collection_aging_partial_reversal_excess_and_scope(workspace):
    c,h,e,_,slug=workspace
    for ref,due in [('PART','2026-08-01'),('PAID','2026-09-01'),('FUTURE','2026-10-01')]:
        assert c.post('/cash/payments',headers=h,json={'entity_id':e,'reference':ref,'due_date':due,'amount':'100','direction':'inflow'}).status_code==201
    assert c.post('/cash/payments',headers=h,json={'entity_id':e,'reference':'AP','due_date':'2026-08-01','amount':'100','direction':'outflow'}).status_code==201
    records=[('P1','PART','70.01','2026-09-01'),('P2','PART','-10.02','2026-09-02'),('P3','PAID','120','2026-09-03'),('P4','UNKNOWN','50','2026-09-03'),('P5','PART','40.01','2026-10-01')]
    r=c.post('/bank/import',headers=h,json={'entity_id':e,'transactions':[{'external_id':key,'reference':ref,'amount':value,'date':day,'currency':'USD'} for key,ref,value,day in records]})
    assert r.status_code==200,r.text
    params={'entity_id':e,'as_of':'2026-09-15'}
    r=c.get('/cash/collections',headers=h,params=params)
    assert r.status_code==200,r.text
    data=r.json();rows={r['reference']:r for r in data['rows']}
    assert len(rows)==3
    assert rows['PART']['outstanding']=='40.01'
    assert rows['PART']['net_bank_evidence']=='59.99'
    assert rows['PART']['bucket']=='31_60'
    assert len(rows['PART']['bank_ids'])==2
    assert rows['PAID']['outstanding']=='0.00'
    assert rows['PAID']['excess_receipts']=='20.00'
    assert rows['FUTURE']['bucket']=='not_due'
    assert data['outstanding']=='140.01' and data['overdue']=='40.01'
    assert len(data['unlinked_positive_bank_ids'])==1
    auditor,_=member(c,h,slug,'auditor')
    assert c.get('/cash/collections',headers=auditor,params=params).status_code==200
    assert c.get('/cash/collections',params=params).status_code==401
    assert c.get('/cash/collections',headers=h,params={**params,'entity_id':'foreign'}).status_code==404
    assert c.get('/cash/collections',headers=h,params={**params,'as_of':'2099-01-01'}).status_code==422
