# -*- coding: utf-8 -*-
"""
Simple convenience wrapper for SQLite.

    db.init(":memory:", "CREATE TABLE test (id INTEGER PRIMARY KEY, val TEXT)")
    db.insert("test", val=None)
    for i in range(5): db.insert("test", {"val": i})
    db.fetch("test", id=1)
    db.fetchall("test", order="val", limit=3)
    db.update("test", {"val": "new"}, val=None)
    db.fetchall("test", val=("IN", range(3)))
    db.delete("test", id=5)
    db.execute("DROP TABLE test")


Keyword arguments are added to WHERE clause, or to VALUES clause for INSERT:

    myid = db.insert("test", val="oh")
    db.update("test", {"val": "ohyes"}, id=myid)
    db.fetch("test", val="ohyes")
    db.delete("test", val="ohyes")


WHERE clause supports simple equality match, binary operators,
collection lookups ("IN", "NOT IN") or raw SQL strings:

    db.fetchall("test", val="ciao")
    db.fetchall("test", where={"id": ("<", 10)})
    db.fetchall("test", id=("IN", range(5)))
    db.fetchall("test", val=("IS NOT", None))
    db.fetchall("test", where=[("LENGTH(val)", (">", 4)), ])


Function argument for key-value parameters, like WHERE or VALUES,
can be a dict, or a sequence of key-value pairs:

    db.update("test", values={"val": "ohyes"}, where=[("id", 1)])


Function argument for sequence parameters, like GROUP BY, ORDER BY, or LIMIT,
can be an iterable sequence like list or tuple, or a single value.

    db.fetchall("test", group="val", order=["id", ("val", False)], limit=3)


Module-level functions work on the first initialized connection, multiple databases
can be used by keeping a reference to the connection:

    d1 = db.init("file1.db", "CREATE TABLE foos (val text)")
    d2 = db.init("file2.db", "CREATE TABLE bars (val text)")
    d1.insert("foos", val="foo")
    d2.insert("bars", val="bar")


Default row factory is dict, can be overridden via Database.row_factory:

    mydb = db.init(":memory:")
    mydb.row_factory = sqlite3.Row


------------------------------------------------------------------------------
Released under the Creative Commons CC0 1.0 Universal Public Domain Dedication.

@author      Erki Suurjaak
@created     05.03.2014
@modified    26.09.2015
"""
import collections
import os
import re
import sqlite3


def init(path=None, init_statements=None):
    """
    Returns a Database object, creating one if path not already open.
    If path is None, returns the default database - the very first initialized.
    Module level functions use the default database.
    """
    return Database.get_database(path, init_statements)


def fetchall(table, cols="*", where=(), group=(), order=(), limit=(), **kwargs):
    """
    Convenience wrapper for database SELECT and fetch all.
    Keyword arguments are added to WHERE.
    """
    return init().fetchall(table, cols, where, group, order, limit, **kwargs)


def fetch(table, cols="*", where=(), group=(), order=(), limit=(), **kwargs):
    """
    Convenience wrapper for database SELECT and fetch one.
    Keyword arguments are added to WHERE.
    """
    return init().fetch(table, cols, where, group, order, limit, **kwargs)


def insert(table, values=(), **kwargs):
    """
    Convenience wrapper for database INSERT, returns inserted row ID.
    Keyword arguments are added to VALUES.
    """
    return init().insert(table, values, **kwargs)


def select(table, cols="*", where=(), group=(), order=(), limit=(), **kwargs):
    """
    Convenience wrapper for database SELECT, returns sqlite3.Cursor.
    Keyword arguments are added to WHERE.
    """
    return init().select(table, cols, where, group, order, limit, **kwargs)


def update(table, values, where=(), **kwargs):
    """
    Convenience wrapper for database UPDATE, returns affected row count.
    Keyword arguments are added to WHERE.
    """
    return init().update(table, values, where, **kwargs)


def delete(table, where=(), **kwargs):
    """
    Convenience wrapper for database DELETE, returns affected row count.
    Keyword arguments are added to WHERE.
    """
    return init().delete(table, where, **kwargs)


def execute(sql, args=None):
    """Executes the SQL and returns sqlite3.Cursor."""
    return init().execute(sql, args)


def close():
    """Closes the default database connection, if any."""
    try: init().close()
    except (sqlite3.Error, AttributeError): pass



class Database(object):
    """Convenience wrapper around sqlite3.Connection."""

    CACHE = collections.OrderedDict() # {path: Database}

    @staticmethod
    def get_database(path=None, statements=None):
        """
        Returns a new or cached Database, or first if path is None.
        For in-memory databases, only the first created one is cached.
        """
        if path is None:
            return next(iter(Database.CACHE.values()), None)
        path = os.path.abspath(path) if ":memory:" != path else path
        return Database.CACHE[path] if path in Database.CACHE \
               and ":memory:" != path else Database(path, statements)


    def __init__(self, path=":memory:", statements=None):
        """Creates a new SQLite connection, and executes given statements."""
        if ":memory:" != path and not os.path.exists(path):
            try: os.makedirs(os.path.dirname(path))
            except OSError: pass
        conn = sqlite3.connect(path, detect_types=sqlite3.PARSE_DECLTYPES,
            isolation_level=None, check_same_thread=False)
        self._path, self._connection = path, conn
        self._row_factory = lambda cursor, row: dict(sqlite3.Row(cursor, row))
        conn.row_factory = lambda cursor, row: self.row_factory(cursor, row)
        if isinstance(statements, basestring): statements = [statements]
        for sql in statements or []: conn.executescript(sql)
        if path not in Database.CACHE: Database.CACHE[path] = self


    def _get_factory(self): return self._row_factory
    def _set_factory(self, row_factory): self._row_factory = row_factory
    row_factory = property(_get_factory, _set_factory, doc="SQLite row factory.")


    def fetchall(self, table, cols="*", where=(), group=(), order=(), limit=(),
                 **kwargs):
        """
        Convenience wrapper for database SELECT and fetch all.
        Keyword arguments are added to WHERE.
        """
        cursor = self.select(table, cols, where, group, order, limit, **kwargs)
        return cursor.fetchall()


    def fetch(self, table, cols="*", where=(), group=(), order=(), limit=(),
              **kwargs):
        """
        Convenience wrapper for database SELECT and fetch one.
        Keyword arguments are added to WHERE.
        """
        cursor = self.select(table, cols, where, group, order, limit, **kwargs)
        return cursor.fetchone()


    def insert(self, table, values=(), **kwargs):
        """
        Convenience wrapper for database INSERT, returns inserted row ID.
        Keyword arguments are added to VALUES.
        """
        values = list(values.items() if isinstance(values, dict) else values)
        values += kwargs.items()
        sql, args = makeSQL("INSERT", table, values=values)
        return self.execute(sql, args).lastrowid


    def select(self, table, cols="*", where=(), group=(), order=(), limit=(),
               **kwargs):
        """
        Convenience wrapper for database SELECT, returns sqlite3.Cursor.
        Keyword arguments are added to WHERE.
        """
        where = list(where.items() if isinstance(where, dict) else where)
        where += kwargs.items()
        sql, args = makeSQL("SELECT", table, cols, where, group, order, limit)
        return self.execute(sql, args)


    def update(self, table, values, where=(), **kwargs):
        """
        Convenience wrapper for database UPDATE, returns affected row count.
        Keyword arguments are added to WHERE.
        """
        where = list(where.items() if isinstance(where, dict) else where)
        where += kwargs.items()
        sql, args = makeSQL("UPDATE", table, values=values, where=where)
        return self.execute(sql, args).rowcount


    def delete(self, table, where=(), **kwargs):
        """
        Convenience wrapper for database DELETE, returns affected row count.
        Keyword arguments are added to WHERE.
        """
        where = list(where.items() if isinstance(where, dict) else where)
        where += kwargs.items()
        sql, args = makeSQL("DELETE", table, where=where)
        return self.execute(sql, args).rowcount


    def execute(self, sql, args=None):
        """Executes the SQL and returns sqlite3.Cursor."""
        return self._connection.execute(sql, args or {})


    def close(self):
        """Closes the database connection."""
        try: self._connection.close()
        except Exception: pass
        if self in Database.CACHE.values(): Database.CACHE.pop(self._path)



def makeSQL(action, table, cols="*", where=(), group=(), order=(), limit=(),
            values=()):
    """Returns (SQL statement string, parameter dict)."""
    action = action.upper()
    cols   =    cols if isinstance(cols,  basestring) else ", ".join(cols)
    group  =   group if isinstance(group, basestring) else ", ".join(group)
    order  = [order] if isinstance(order, basestring) else order
    limit  = [limit] if isinstance(limit, (basestring, int)) else limit
    values = values if not isinstance(values, dict) else values.items()
    where  =  where if not isinstance(where, dict)  else where.items()
    sql = "SELECT %s FROM %s" % (cols, table) if "SELECT" == action else ""
    sql = "DELETE FROM %s"    % (table)       if "DELETE" == action else sql
    sql = "INSERT INTO %s"    % (table)       if "INSERT" == action else sql
    sql = "UPDATE %s"         % (table)       if "UPDATE" == action else sql
    args = {}
    if "INSERT" == action:
        args.update(values)
        cols, vals = (", ".join(x + k for k, v in values) for x in ("", ":"))
        sql += " (%s) VALUES (%s)" % (cols, vals)
    if "UPDATE" == action:
        sql += " SET "
        for i, (col, val) in enumerate(values):
            sql += (", " if i else "") + "%s = :%sU%s" % (col, col, i)
            args["%sU%s" % (col, i)] = val
    if where:
        sql += " WHERE "
        for i, (col, val) in enumerate(where):
            key = "%sW%s" % (re.sub("\\W", "_", col), i)
            dbval = val[1] if isinstance(val, (list, tuple)) else val
            op = "IS" if dbval == val else val[0]
            op = "=" if dbval is not None and "IS" == op.upper() else op
            if op.upper() in ("IN", "NOT IN"):
                keys = ["%sW%s_%s" % (re.sub("\\W", "_", col), i, j)
                        for j in range(len(dbval))]
                args.update(zip(keys, dbval))
                sql += (" AND " if i else "") + "%s %s (%s)" % (
                        col, op, ", ".join(":" + x for x in keys))
            else:
                args[key] = dbval
                sql += (" AND " if i else "") + "%s %s :%s" % (col, op, key)
    if group:
        sql += " GROUP BY " + group
    if order:
        get_direction = lambda c: (c if isinstance(c, basestring)
                                    else "DESC" if c else "ASC")
        sql += " ORDER BY "
        for i, col in enumerate(order):
            name = col[0] if isinstance(col, (list, tuple)) else col
            direction = "" if name == col else " " + get_direction(col[1])
            sql += (", " if i else "") + name + direction
    if limit:
        sql += " LIMIT %s" % (", ".join(map(str, limit)))
    return sql, args



if "__main__" == __name__:
    import db
    db.init(":memory:", "CREATE TABLE test (id INTEGER PRIMARY KEY, val TEXT)")

    print("Inserted ID %s." % db.insert("test", val=None))
    for i in range(5): print("Inserted ID %s." % db.insert("test", {"val": i}))
    print("Fetch ID 1: %s." % db.fetch("test", id=1))
    print("Fetch all up to 3, order by val: %s." % db.fetchall("test", order="val", limit=3))
    print("Updated %s row where val is NULL." % db.update("test", {"val": "new"}, val=None))
    print("Select where val IN [0, 1, 2]: %s." % db.fetchall("test", val=("IN", range(3))))
    print("Delete %s row where val=0." % db.delete("test", val=0))
    print("Fetch all, order by val: %s." % db.fetchall("test", order="val"))
    db.execute("DROP TABLE test")
    db.close()
