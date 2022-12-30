**Sqlite3 DataBase wrapper with AES encryption support. Also supports base64 encoding.**
---
> **create new database and adding tables to it:**
```py
>>> db = SqliteDatabase(
        dbpath: t.Optional[str] = "test.db", 
        datamode: t.Literal["secure", "b64", "default"] = "default", 
        aespwd: t.Optional[str] = "test"
)
>>> table = db.table("test", "value TEXT", "smth INT")
<Table name="test" rows=0>
```
> **Using a SqliteDatabase.add method:**
```py
>>> db.add({"value": "smthfortest", "smth": 69420}, table.name)
<DataBaseResponse status=True, value={'value': 'smthfortest', 'smth': 69420}>
```
> **Using a SqliteDatabase.fetch method:**
```py
>>> db.fetch({"value": "smthfortest", "smth": 69420}, table.name, mode=FetchMode.FETCH_ALL) 
<DataBaseResponse status=True, value=[{'value': 'smthfortest', 'smth': 69420}]>
```
> **Using a SqliteDatabase.remove method:**
```py
>>> db.add({"value": "smthfortest", "smth": 69420}, table.name)
<DataBaseResponse status=True, value={'value': 'smthfortest', 'smth': 69420}>

>>> db.fetch({"value": "smthfortest", "smth": 69420}, table.name, mode=FetchMode.FETCH_ALL)
<DataBaseResponse status=True, value=[{'value': 'smthfortest', 'smth': 69420}]>

>>> db.remove({"value": "smthfortest", "smth": 69420}, table.name, mode=FetchMode.FETCH_ALL)
<DataBaseResponse status=True, value=1> # 1 row affected

>>> db.fetch({"value": "smthfortest", "smth": 69420}, table.name, mode=FetchMode.FETCH_ALL)
<DataBaseResponse status=False, value=None>
```
> **Using a SqliteDatabase.update method:**
```py
>>> db = SqliteDatabase("test.db")

>>> table = db.table("test", "value TEXT", "smth INT")
<Table name="test" rows=0>

>>> db.add({"value": "smthfortest", "smth": 69420}, table.name)
<DataBaseResponse status=True, value={'value': 'smthfortest', 'smth': 69420}>

>>> db.fetch({"value": "smthfortest", "smth": 69420}, table.name)
<DataBaseResponse status=True, value={'value': 'smthfortest', 'smth': 69420}>

>>> db.update({"value": "smthfortest", "smth": 69420}, {"value": "amogus", 'smth': 123456}, table.name)
<DataBaseResponse status=True, value=1> # 1 means 1 row affected

>>> db.fetch({"value": "smthfortest", "smth": 69420}, table.name)
<DataBaseResponse status=False, value=None>

>>> db.fetch({"value": "amogus", 'smth': 123456}, table.name)
<DataBaseResponse status=True, value={"value": "amogus", 'smth': 123456}>
```
**Now supports all data types**
