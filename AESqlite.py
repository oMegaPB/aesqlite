import base64
import sqlite3
import typing as t
from enum import IntEnum
from hashlib import md5

from Crypto.Cipher import AES

xInputDataT = t.Union[t.List[t.Dict[str, t.Any]], t.Dict[str, t.Any]]
xResponseValueT = t.Optional[t.Union[t.List[t.Dict[str, t.Any]], t.Dict[str, t.Any], int]]

class DataBaseException(Exception):
    pass

class FetchMode(IntEnum):
    FETCH_ONE = 1
    FETCH_ALL = 2

class Table:
    def __init__(self, name: str, db: "SqlDatabase", *, created: t.Optional[bool] = None) -> None:
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
    def rows(self) -> t.Dict[t.Any, t.Any]:
        tcolumns = [x[1] for x in self._table_info]
        data = {x: {tcolumns[z]: y[z] for z, _ in enumerate(tcolumns)} for x, y in enumerate(self._rows, start=1)}
        data["_types"] = {tcolumns[x]: y if y else "UNDEFINED" for x, y in enumerate([x[2] for x in self._table_info])} # type: ignore
        data.update({})
        return data

    @property
    def columns(self) -> t.Dict[t.Any, t.Any]:
        return {x[1]: x[2] if x[2] else "UNDEFINED" for x in self._table_info}
    
    @property
    def pretty_print(self) -> str:
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

class SqlDatabase:
    def __init__(self, dbpath: t.Optional[str] = None, aespwd: t.Optional[str] = None) -> None:
        self.aes = False
        self.dbpath = dbpath if dbpath else "sqlite.db"
        if aespwd is not None and isinstance(aespwd, str):
            self.aes = True
            self.pwd = md5(aespwd.encode()).digest()

    def create_connection(self, **kwargs) -> sqlite3.Connection:
        """
        Create a connection for a given database with sqlite3.Row row factory
        """
        conn = sqlite3.connect(self.dbpath, **kwargs)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _aes_encrypt(self, data: str) -> str:
        return base64.b64encode(AES.new(self.pwd, AES.MODE_GCM, self.pwd).encrypt(data.encode())).decode('ascii')
    
    def _aes_decrypt(self, data: str) -> str:
        try:
            return AES.new(self.pwd, AES.MODE_GCM, self.pwd).decrypt(base64.b64decode(data.encode("ascii"))).decode()
        except UnicodeDecodeError as e:
            raise RuntimeError(f'Invalid AES decryption password. {e.__class__.__name__}')
        except Exception:
            raise

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
        """
        Executes Custom SQL query
        """
        with self.create_connection() as con:
            cur = con.cursor()
            cur.execute(query)
            return cur
    
    def fetch(
        self, 
        data: t.Dict[str, t.Any], 
        table: str, 
        mode: t.Literal[FetchMode.FETCH_ONE, FetchMode.FETCH_ALL] = FetchMode.FETCH_ONE
    ) -> DataBaseResponse:
        with self.create_connection() as con:
            if self.aes:
                data = {x: self._aes_encrypt(str(y)) for x, y in data.items()}
            cur = con.cursor()
            condition = " AND ".join([f"{x}=?" for x in data.keys()])
            sql = f"SELECT * FROM {table}{' WHERE ' + condition + ';' if data != {} else ';'}"
            cur.execute(sql, tuple([x for x in data.values()]))
            result = [dict(x) for x in cur.fetchall()]
            if self.aes:
                result = [{z: int(self._aes_decrypt(y)) if Table(table, db=self).columns.get(z) == "INT" else self._aes_decrypt(y) for z, y in x.items()} for x in result]
            result = result[0] if mode == 1 and result else result
        return DataBaseResponse(status=bool(result), value=result if result else None)
    
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
                cur = con.cursor()
                condition = " AND ".join([f"{x}=?" for x in data.keys()])
                sql = f"DELETE FROM {table} {'WHERE ' + condition if data != {} else ''}" + (f" LIMIT {limit};" if limit else ";")
                cur.execute(sql, tuple([x for x in data.values()]))
                con.commit()
        return DataBaseResponse(status=bool(cur.rowcount), value=cur.rowcount if cur.rowcount else None)
    
    def add(
        self, 
        data: xInputDataT, 
        table: str
    ) -> DataBaseResponse:
        with self.create_connection() as con:
            cur = con.cursor()
            raw_data = data
            if self.aes:
                if isinstance(data, dict):
                    data = {x: self._aes_encrypt(str(y)) for x, y in data.items()}
                else: # isinstance(data, list)
                    data = [{z: self._aes_encrypt(str(y)) for z, y in x.items()} for x in data]
            if isinstance(data, list):
                values = f"{str([tuple([x for x in x.values()]) for x in data])[1:-1]};".replace(",)", ")")
            else: # isinstance(data, dict)
                values = f"{str(tuple([x for x in data.values()]))};".replace(",)", ")")
            columns = Table(table, db=self).columns
            columns = f"({', '.join(list(Table(table, db=self).columns.keys()))})"
            sql = f"INSERT INTO {table} {columns} VALUES {values}"
            cur.execute(sql)
            con.commit()
            return DataBaseResponse(status=bool(cur.rowcount), value=raw_data)
    
    def update(
        self, 
        to_replace: t.Dict[str, t.Any], 
        data: t.Dict[str, t.Any], 
        table: str, 
        limit: t.Optional[int] = None
    ) -> DataBaseResponse:
        with self.create_connection() as con:
            if self.aes:
                to_replace = {x: self._aes_encrypt(str(y)) for x, y in to_replace.items()}
                data = {x: self._aes_encrypt(str(y)) for x, y in data.items()}
            values = ", ".join([f"{x} = {y}" if isinstance(y, int) else f"{x} = '{y}'" for x, y in data.items()])
            if values:
                cur = con.cursor()
                condition = " AND ".join([f"{x}=?" for x in to_replace.keys()])
                sql = f"UPDATE {table} SET {values}{' WHERE ' + condition if condition else ''}{f' LIMIT {limit}' if limit else ''};"
                cur.execute(sql, tuple([x for x in to_replace.values()]))
                return DataBaseResponse(status=bool(cur.rowcount), value=cur.rowcount)
            raise DataBaseException("Empty data to replace")
