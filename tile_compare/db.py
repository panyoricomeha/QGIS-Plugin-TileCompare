"""Read tables through database connections registered in QGIS."""
from qgis.PyQt.QtCore import QVariant
from qgis.core import QgsAbstractDatabaseProviderConnection, QgsProviderRegistry

PROVIDERS = [('mssql', 'SQL Server'), ('postgres', 'PostgreSQL'), ('oracle', 'Oracle'),
             ('hana', 'SAP HANA'), ('spatialite', 'SpatiaLite'), ('ogr', 'GeoPackage')]


def connections():
    """[(label, provider, connection)]"""
    found = []
    reg = QgsProviderRegistry.instance()
    for key, label in PROVIDERS:
        md = reg.providerMetadata(key)
        if md is None:
            continue
        try:
            conns = md.connections()
        except Exception:
            continue
        for name, conn in sorted(conns.items()):
            found.append((f'{label}: {name}', key, conn))
    return found


def schemas(conn):
    if conn.capabilities() & QgsAbstractDatabaseProviderConnection.Schemas:
        return conn.schemas()
    return ['']


def tables(conn, schema):
    return sorted(t.tableName() for t in conn.tables(schema))


def quote(provider, name):
    if provider == 'mssql':
        return '[' + name.replace(']', ']]') + ']'
    return '"' + name.replace('"', '""') + '"'


def select_sql(provider, schema, table):
    target = quote(provider, table)
    if schema:
        target = f'{quote(provider, schema)}.{target}'
    return f'SELECT * FROM {target}'


def _text(v):
    if v is None or (isinstance(v, QVariant) and v.isNull()):
        return ''
    if isinstance(v, float):
        return repr(v)
    if isinstance(v, (bytes, bytearray, memoryview)):
        return ''
    if hasattr(v, 'toString') and not isinstance(v, str):
        return v.toString()
    return str(v)


def query(conn, sql, fallback_fields=None, limit=None):
    """Run SQL and return (headers, rows) as strings. With limit, stop after that many rows."""
    if hasattr(conn, 'execSql'):  # QGIS 3.18+: column names and row-by-row reading
        res = conn.execSql(sql)
        headers = list(res.columns())
        rows = []
        while res.hasNextRow() and (limit is None or len(rows) < limit):
            rows.append([_text(v) for v in res.nextRow()])
    else:
        data = conn.executeSql(sql)
        width = len(data[0]) if data else 0
        headers = list(fallback_fields or [])[:width]
        headers += [f'col{i + 1}' for i in range(len(headers), width)]
        rows = [[_text(v) for v in r] for r in data[:limit]]
    if rows and not headers:
        headers = [f'col{i + 1}' for i in range(len(rows[0]))]
    return headers, rows


def field_names(conn, schema, table):
    try:
        return [f.name() for f in conn.fields(schema, table)]
    except Exception:
        return None
