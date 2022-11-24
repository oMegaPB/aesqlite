import json
import sqlite3
import typing as t
from hashlib import md5
import base64
from Crypto.Cipher import AES

xInputDictType = t.Dict[t.Union[str, int, bool, None, float], t.Union[str, int, bool, None, float]]
xInputDataT = t.Union[t.List[xInputDictType], xInputDictType]

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
    def rows(self) -> t.Optional[t.Dict[t.Any, t.Any]]:
        if not self.exists:
            return None
        tcolumns = [x[1] for x in self._table_info]
        data = {x: {tcolumns[z]: y[z] for z, _ in enumerate(tcolumns)} for x, y in enumerate(self._rows, start=1)}
        data["_types"] = {tcolumns[x]: y if y else "UNDEFINED" for x, y in enumerate([x[2] for x in self._table_info])}
        return json.dumps(data, indent=4)

    @property
    def columns(self) -> t.Optional[t.Dict[t.Any, t.Any]]:
        if not self.exists:
            return None
        return json.dumps({int(x[0]) + 1: {x[1]: x[2] if x[2] else "UNDEFINED"} for x in self._table_info}, indent=4)
    
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
    def __init__(self, status: bool, value: xInputDataT = None) -> None:
        self._status = status
        self._value = value if value is not None else None
    
    def __repr__(self) -> str:
        return f'<DataBaseResponse status={self._status}, value={self._value}>'
    
    def __len__(self) -> int:
        return len(self._value)
    
    @property
    def status(self) -> bool:
        return self._status
    
    @property
    def value(self) -> xInputDataT:
        return self._value

class SqlDatabase:
    def __init__(self, dbpath: str = None, aespwd: str = None) -> None:
        self.aes = False
        self.dbpath = dbpath
        self.privkey = None
        self.pubkey = None
        if aespwd is not None and isinstance(aespwd, str):
            self.aes = True
            self.pwd = md5(aespwd.encode()).digest()

    def create_connection(self, **kwargs) -> sqlite3.Connection:
        conn = sqlite3.connect(self.dbpath, **kwargs)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _aes_encrypt(self, data: str) -> str:
        return base64.b64encode(AES.new(self.pwd, AES.MODE_GCM, self.pwd).encrypt(data.encode())).decode('ascii')
    
    def _aes_decrypt(self, data: str) -> str:
        try:
            return AES.new(self.pwd, AES.MODE_GCM, self.pwd).decrypt(base64.b64decode(data.encode("ascii"))).decode()
        except UnicodeDecodeError as e:
            raise RuntimeError(f'Invalid AES encryption password. {e.__class__.__name__}')

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
            return cur
    
    def fetch(self, data: xInputDataT, table: str, mode: t.Literal[1, 2] = 1) -> DataBaseResponse:
        with self.create_connection() as con:
            if self.aes:
                data = {x: self._aes_encrypt(y) for x, y in data.items()}
            cur = con.cursor()
            condition = " AND ".join([f"{x}=?" for x in data.keys()])
            sql = f"SELECT * FROM {table} {'WHERE ' + condition + ';' if data != {} else ';'}"
            cur.execute(sql, tuple([x for x in data.values()]))
            result = [dict(x) for x in cur.fetchall()]
            if self.aes:
                result = [{z: self._aes_decrypt(y) for z, y in x.items()} for x in result]
            result = result[0] if mode == 1 and result else result
        return DataBaseResponse(status=bool(result), value=result if result else None)
    
    def remove(self, data: xInputDataT, table: str, limit: t.Optional[t.Union[int, bool]] = None) -> DataBaseResponse:
        with self.create_connection() as con:
            if isinstance(data, list):
                for x in data:
                    self.remove(data=x, table=table, limit=limit)
                return DataBaseResponse(status=True, value=len(data))
            cur = con.cursor()
            condition = " AND ".join([f"{x}=?" for x in data.keys()])
            sql = f"DELETE FROM {table} {'WHERE ' + condition if data != {} else ''}" + (f" LIMIT {limit};" if limit else ";")
            cur.execute(sql, tuple([x for x in data.values()]))
            con.commit()
        return DataBaseResponse(status=bool(cur.rowcount), value=cur.rowcount if cur.rowcount else None)
    
    def add(self, data: xInputDataT, table: str) -> DataBaseResponse:
        with self.create_connection() as con:
            cur = con.cursor()
            if self.aes:
                data = {x: self._aes_encrypt(y) for x, y in data.items()}
            columns = f"({', '.join([list(x.keys())[0] for x in json.loads(Table(table, db=self).columns).values()])})"
            if isinstance(data, list):
                values = f"{str([tuple([x for x in x.values()]) for x in data])[1:-1]};".replace(",)", ")")
            elif isinstance(data, dict):
                values = f"{str(tuple([x for x in data.values()]))};".replace(",)", ")")
            sql = f"INSERT INTO {table} {columns} VALUES {values}"
            cur.execute(sql)
            con.commit()
        return DataBaseResponse(status=bool(cur.rowcount), value=data)
    
    def update(self, to_replace: xInputDataT, data: xInputDataT, table: str, limit: t.Optional[t.Union[int, bool]] = None) -> DataBaseResponse:
        with self.create_connection() as conn:
            if self.aes:
                to_replace = {x: self._aes_encrypt(y) for x, y in to_replace.items()}
                data = {x: self._aes_encrypt(y) for x, y in data.items()}
            values = ", ".join([f"{x} = {y}" if isinstance(y, int) else f"{x} = '{y}'" for x, y in data.items()])
            if values:
                cur = conn.cursor()
                condition = " AND ".join([f"{x}=?" for x in to_replace.keys()])
                sql = f"UPDATE {table} SET {values}{' WHERE ' + condition if condition else ''}{f' LIMIT {limit}' if limit else ''};"
                cur.execute(sql, tuple([x for x in to_replace.values()]))
                return DataBaseResponse(status=bool(cur.rowcount), value=cur.rowcount)
            raise ValueError("empty data to replace")
