from test_platform import workspace

def test_ai_readiness_without_secret_disclosure(workspace,monkeypatch):
    c,h,_,_,_=workspace
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    assert not c.get('/agents/status',headers=h).json()['configured']
    monkeypatch.setenv('OPENAI_API_KEY','test-secret-never-disclose')
    monkeypatch.setenv('OPENAI_MODEL','configured-test-model')
    response=c.get('/agents/status',headers=h)
    assert response.json()['configured']
    assert response.json()['model']=='configured-test-model'
    assert 'test-secret-never-disclose' not in response.text
    assert c.get('/agents/status').status_code==401
