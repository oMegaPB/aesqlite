____
**Sqlite3 DataBase wrapper with AES-128 encryption support.**
___
> **create new database and adding tables to it:**
```py
>>> db = SqlDatabase(dbpath: t.Optional[str] = "test.db", aespwd: t.Optional[str] = "test")
```
> **Using a SqlDatabase.add method:**
```py
>>> db.add({"value": "smthfortest", "smth": 69420}, table.name)
<DataBaseResponse status=True, value={'value': 'smthfortest', 'smth': 69420}>
```
> **Using a SqlDatabase.fetch method:**
```py
>>> db.fetch({"value": "smthfortest", "smth": 69420}, table.name, mode=FetchMode.FETCH_ALL) 
<DataBaseResponse status=True, value=[{'value': 'smthfortest', 'smth': 69420}]>
```
> **Using a SqlDatabase.remove method:**
```py
>>> db.add({"value": "smthfortest", "smth": 69420}, table.name)
<DataBaseResponse status=True, value={'value': 'smthfortest', 'smth': 69420}>

>>> db.fetch({"value": "smthfortest", "smth": 69420}, table.name, mode=2)
<DataBaseResponse status=True, value=[{'value': 'smthfortest', 'smth': 69420}]>

>>> db.remove({"value": "smthfortest", "smth": 69420}, table.name, mode=2)
<DataBaseResponse status=True, value=1> # 1 row affected

>>> db.fetch({"value": "smthfortest", "smth": 69420}, table.name, mode=2)
<DataBaseResponse status=False, value=None>
```
> **Using a SqlDatabase.update method:**
```py
>>> db = SqlDatabase("test.db")

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
