from abc import ABC, abstractmethod
class ERPConnector(ABC):
    @abstractmethod
    async def validate_connection(self) -> dict: ...
    @abstractmethod
    async def fetch_journal_entries(self, cursor: str | None = None) -> dict: ...

class NetSuiteConnector(ERPConnector):
    async def validate_connection(self):
        raise NotImplementedError("Configure SuiteTalk OAuth and account-specific permissions")
    async def fetch_journal_entries(self, cursor=None):
        raise NotImplementedError("NetSuite adapter not implemented")

class BusinessCentralConnector(ERPConnector):
    async def validate_connection(self):
        raise NotImplementedError("Configure Microsoft Entra OAuth and API scopes")
    async def fetch_journal_entries(self, cursor=None):
        raise NotImplementedError("Business Central adapter not implemented")
