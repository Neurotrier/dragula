from dragula.adapters.outbound.storage.sqlite.descriptions import SQLiteDescriptionStore
from dragula.adapters.outbound.storage.sqlite.runs import SQLiteIndexRunStore
from dragula.adapters.outbound.storage.sqlite.symbols import SQLiteSymbolStore


class SQLiteCodeDocumentRepository(
    SQLiteSymbolStore, SQLiteDescriptionStore, SQLiteIndexRunStore
):
    """Facade that preserves the existing repository API while delegating storage
    concerns to focused SQLite mixins.
    """

    pass
