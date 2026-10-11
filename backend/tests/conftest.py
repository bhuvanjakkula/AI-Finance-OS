import os, tempfile
_test_directory=tempfile.TemporaryDirectory(prefix='finance-platform-tests-')
os.environ['DATABASE_URL']='sqlite:///'+os.path.join(_test_directory.name,'test.db')
os.environ['ALLOW_REGISTRATION']='true'
os.environ['FINANCE_KEYRING_FILE']=os.path.join(_test_directory.name,'test-keyring-not-initialized.json')
os.environ['FINANCE_ENV']='development'
os.environ['FINANCE_REQUIRE_ENCRYPTION']='false'


def pytest_sessionfinish(session,exitstatus):
    from app.database import engine
    engine.dispose()
    _test_directory.cleanup()
