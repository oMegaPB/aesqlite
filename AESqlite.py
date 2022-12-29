import base64
import sqlite3
import typing as t
from hashlib import md5
from enum import IntEnum

from Crypto.Cipher import AES

xInputDataT = t.Union[t.List[t.Dict[str, t.Any]], t.Dict[str, t.Any]]
xResponseValueT = t.Optional[t.Union[t.List[t.Dict[str, t.Any]], t.Dict[str, t.Any], int]]

class FetchMode(IntEnum):
    FETCH_ONE = 1
    FETCH_ALL = 2

class DataBaseException(Exception):
    ...

class Table:
    def __init__(self, name: str, db: "SqliteDatabase", *, created: t.Optional[bool] = None) -> None:
        with db.create_connection() as con:
            self.db = db
            cur = con.cursor()
            self.created = created
            self.name = name
            self._table_info = cur.execute(f"PRAGMA table_info({self.name});").fetchall()
            self._rows = cur.execute(f"SELECT * FROM {self.name}").fetchall()
    
    def __repr__(self) -> str:
        return f"<Table name={self.name} rows={len(self._rows)}>" 
    
    @property
    def exists(self) -> bool:
        with self.db.create_connection() as con:
            cur = con.cursor()
            try:
                return cur.execute(f"SELECT * FROM {self.name};") is not None
            except sqlite3.OperationalError:
                return False
    
    @property
    def rows(self) -> t.Optional[t.Dict[t.Any, t.Any]]:
        if not self.exists:
            return None
        tcolumns = [x[1] for x in self._table_info]
        data = {x: {tcolumns[z]: y[z] for z, _ in enumerate(tcolumns)} for x, y in enumerate(self._rows, start=1)}
        data["_types"] = {tcolumns[x]: y if y else "UNDEFINED" for x, y in enumerate([x[2] for x in self._table_info])} # type: ignore
        return data

    @property
    def columns(self) -> t.Optional[t.Dict[t.Any, t.Any]]:
        if not self.exists:
            return None
        return {int(x[0]) + 1: {x[1]: x[2] if x[2] else "UNDEFINED"} for x in self._table_info}
    
    @property
    def pretty_print(self) -> t.Optional[str]:
        if not self.exists:
            return None
        columns = "0. | " + " | ".join([x[1] + f": {x[2] if x[2] else 'UNDEFINED'}" for x in self._table_info]) + " |\n"
        for x, row in enumerate(self._rows):
            columns += f"{x + 1}. | " + f"{' | '.join([str(x) for x in row])}" + " |\n"
        return f"table {self.name}:\n" + "=" * 50 + "\n" + columns + "=" * 50
    
    def drop(self) -> bool:
        with self.db.create_connection() as con:
            cur = con.cursor()
            try:
                cur.execute(f"DROP TABLE {self.name};")
            except sqlite3.OperationalError:
                return False
            return True

class DataBaseResponse:
    def __init__(self, status: bool, value: t.Optional[xResponseValueT] = None) -> None:
        self.__status = status
        self.__value = value if value is not None else None
    
    def __repr__(self) -> str:
        return f'<DataBaseResponse status={self.__status}, value={self.__value}>'
    
    def __len__(self) -> int:
        return len(self.__value)  # type: ignore
    
    @property
    def status(self) -> bool:
        return self.__status
    
    @property
    def value(self) -> xResponseValueT:
        return self.__value

class SqliteDatabase:
    def __init__(
        self, 
        dbpath: t.Optional[str] = None,
        datamode: t.Literal["b64", "aes", "default"] = "default",  
        aespwd: t.Optional[str] = None
    ) -> None:
        self.datamode = datamode.lower()
        assert self.datamode in ["b64", "aes", "default"], "Mode must be either b64 or AES or default."
        if self.datamode == "aes":
            assert aespwd, "AES mode requires a data-encryption password."
            self.pwd = md5(aespwd.encode()).digest()
        if aespwd:
            assert self.datamode == "aes"
        self.aespwd = aespwd
        self.dbpath = dbpath if dbpath else "sqlite.db"

    def create_connection(self, **kwargs) -> sqlite3.Connection:
        conn = sqlite3.connect(self.dbpath, **kwargs)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _encode(self, data: str) -> str:
        if self.datamode == "aes":
            return base64.b64encode(AES.new(self.pwd, AES.MODE_GCM, self.pwd).encrypt(str(data).encode())).decode('ascii')
        elif self.datamode == "b64":
            return base64.b64encode(str(data).encode()).decode("ascii")
        return data
    
    def _decode(self, data: str) -> str:
        if self.datamode == "aes":
            try:
                key = AES.new(self.pwd, AES.MODE_GCM, self.pwd)
                return key.decrypt(base64.b64decode(data.encode("ascii"))).decode()
            except UnicodeDecodeError as e:
                raise RuntimeError(f'Invalid AES decryption password. {e.__class__.__name__}')
        elif self.datamode == "b64":
            return base64.b64decode(data.encode()).decode("ascii")
        return data

    @property
    def tables(self) -> t.List[Table]:
        with self.create_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        return [Table(x[0], db=self) for x in cur.fetchall()]
    
    def table(self, name: str, *columns) -> "Table":
        with self.create_connection() as con:
            cur = con.cursor()
            columns = f"({','.join(columns)})"
            try:
                created = not cur.execute(f"SELECT * FROM {name};") is not None
            except sqlite3.OperationalError: # table is not exist
                created = True
            cur.execute(f"CREATE TABLE IF NOT EXISTS {name}{columns};")
        return Table(name, created=created, db=self)
    
    def drop_table(self, name: str) -> bool:
        return Table(name, self).drop()
    
    def execute(self, query: str) -> sqlite3.Cursor:
        with self.create_connection() as con:
            cur = con.cursor()
            cur.execute(query)
            data = [dict(x) for x in cur.fetchall()]
        return type("DataBaseResponse", (), {"status": not not data, "cursor": cur, "value": data, "query": query})
    
    def fetch(
        self, 
        data: t.Dict[str, t.Any], 
        table: str, 
        mode: int = FetchMode.FETCH_ONE
    ) -> DataBaseResponse:
        with self.create_connection() as con:
            data = {x: self._encode(y) for x, y in data.items()}
            cur = con.cursor()
            condition = " AND ".join([f"{x}=?" for x in data.keys()])
            sql = f"SELECT * FROM {table}{' WHERE ' + condition + ';' if data != {} else ';'}"
            cur.execute(sql, tuple([x for x in data.values()]))
            columns = {x: y for sub in [x for x in Table(table, db=self).columns.values()] for x, y in sub.items()} # type: ignore
            result = [{z: self._decode(y) for z, y in x.items()} for x in [dict(x) for x in cur.fetchall()]]
            result = [{z: int(j) if columns.get(z) == "INT" else j for z, j in x.items()} for x in result] # table type checkings
            result = result[0] if mode == 1 and result else result
        return DataBaseResponse(status=not not result, value=result if result else None)
    
    def remove(
        self, 
        data: xInputDataT, 
        table: str, 
        limit: t.Optional[int] = None
    ) -> DataBaseResponse:
        with self.create_connection() as con:
            if isinstance(data, list):
                for x in data:
                    self.remove(data=x, table=table, limit=limit)
                return DataBaseResponse(status=True, value=len(data))
            else:
                data = {x: self._encode(y) for x, y in data.items()}
                cur = con.cursor()
                condition = " AND ".join([f"{x}=?" for x in data.keys()])
                sql = f"DELETE FROM {table} {'WHERE ' + condition if data != {} else ''}" + (f" LIMIT {limit};" if limit else ";")
                cur.execute(sql, tuple([x for x in data.values()]))
                con.commit()
        return DataBaseResponse(status=not not cur.rowcount, value=cur.rowcount if cur.rowcount else None)
    
    def add(
        self, 
        data: xInputDataT, 
        table: str
    ) -> DataBaseResponse:
        with self.create_connection() as con:
            cur = con.cursor()
            raw_data = data
            if isinstance(data, dict):
                assert all([isinstance(x, str) for x in data.keys()]), "Only strings can be keys."
                data = {x: self._encode(y) for x, y in data.items()}
                values = f"{str(tuple([x for x in data.values()]))};".replace(",)", ")")
            else: # isinstance(data, list)
                assert all([isinstance(x, str) for sub in data for x in sub.keys()]), "Only strings can be keys."
                data = [{z: self._encode(y) for z, y in x.items()} for x in data]
                values = f"{str([tuple([x for x in x.values()]) for x in data])[1:-1]};".replace(",)", ")")
            columns = Table(table, db=self).columns
            if columns:
                columns = f"({', '.join([list(x.keys())[0] for x in columns.values()])})"
                sql = f"INSERT INTO {table} {columns} VALUES {values}"
                cur.execute(sql)
                con.commit()
                return DataBaseResponse(status=not not cur.rowcount, value=raw_data)
            raise DataBaseException(f"Table {table} does not exist")
    
    def update(
        self, 
        to_replace: t.Dict[str, t.Any], 
        data: t.Dict[str, t.Any], 
        table: str, 
        limit: t.Optional[int] = None
    ) -> DataBaseResponse:
        with self.create_connection() as con:
            to_replace = {x: self._encode(y) for x, y in to_replace.items()}
            assert all([isinstance(x, str) for x in to_replace.keys()]), "Only strings can be keys."
            data = {x: self._encode(y) for x, y in data.items()}
            assert all([isinstance(x, str) for x in data.keys()]), "Only strings can be keys."
            values = ", ".join([f"{x} = {y}" if isinstance(y, int) else f"{x} = '{y}'" for x, y in data.items()])
            if values:
                cur = con.cursor()
                condition = " AND ".join([f"{x}=?" for x in to_replace.keys()])
                sql = f"UPDATE {table} SET {values}{' WHERE ' + condition if condition else ''}{f' LIMIT {limit}' if limit else ''};"
                cur.execute(sql, tuple([x for x in to_replace.values()]))
                return DataBaseResponse(status=not not cur.rowcount, value=cur.rowcount)
            raise DataBaseException("Empty data to replace")
