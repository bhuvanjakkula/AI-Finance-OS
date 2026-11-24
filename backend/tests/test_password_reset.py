from urllib.parse import urlparse, parse_qs
from test_platform import workspace


def test_forgot_and_reset_password_flow(workspace):
    c, h, _, _, slug = workspace

    # 1. Request reset link for registered user
    res = c.post('/auth/forgot-password', json={'email': 'owner@example.com', 'slug': slug})
    assert res.status_code == 200, res.text
    data = res.json()
    assert data['sent'] is True
    assert 'reset_url' in data
    token = parse_qs(urlparse(data['reset_url']).query)['reset_token'][0]

    # 2. Mismatched new password and confirmation password must fail
    bad = c.post('/auth/reset-password', json={
        'token': token,
        'new_password': 'New-Strong-Password-9999',
        'confirm_password': 'Different-Password-9999',
    })
    assert bad.status_code == 422

    # 3. Matching new password and confirmation password succeeds
    ok = c.post('/auth/reset-password', json={
        'token': token,
        'new_password': 'New-Strong-Password-9999',
        'confirm_password': 'New-Strong-Password-9999',
    })
    assert ok.status_code == 200, ok.text
    assert ok.json()['updated'] is True

    # 4. Old session is revoked and old password no longer works
    assert c.get('/auth/me', headers=h).status_code == 401
    assert c.post('/auth/login', json={'slug': slug, 'email': 'owner@example.com', 'password': 'Correct-horse-1234'}).status_code == 401

    # 5. New password works
    relogin = c.post('/auth/login', json={'slug': slug, 'email': 'owner@example.com', 'password': 'New-Strong-Password-9999'})
    assert relogin.status_code == 200, relogin.text

    # 6. Token cannot be reused
    reuse = c.post('/auth/reset-password', json={
        'token': token,
        'new_password': 'Another-Strong-Password-8888',
        'confirm_password': 'Another-Strong-Password-8888',
    })
    assert reuse.status_code == 400

    # 7. Unknown email still returns generic 200 without leaking user existence
    unknown = c.post('/auth/forgot-password', json={'email': 'nobody@example.com'})
    assert unknown.status_code == 200
    assert unknown.json()['sent'] is True
    assert 'reset_url' not in unknown.json()
