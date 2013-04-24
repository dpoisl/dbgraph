"""
Database Information Readers

This module contains readers for various databases
that return the database layout in a normalized form.
"""

__author__ = "David Poisl <david@poisl.at>"
__version__ = "0.1.0"


import json
import re


class Generic(object):
    """
    Base class for readers

    This class abstracts common behaviour used in various readers, eG
    querying the database and formatting the result, creating the layout
    structure from the query results, etc.

    Subclasses must set the following class variables:
    sql_schemas -- SQL statement to get all schemas from the database or None
             if the database doesn't support schemas.
    sql_tables -- SQL statement to get all tables for a schema or all tables in 
            the database f the database doesn't support schemas. The first 
            parameter to the query will be the schema name.
    sql_views -- SQL statement to get all views for a schema or all tables in 
            the database f the database doesn't support schemas. The first 
            parameter to the query will be the schema name.
    sql_columns -- SQL statement to fetch all columns for a table. The 
            parameters for this query are the schema name and table name.
    sql_foreign_keys -- SQL statement to fetch foreign keys for the whole 
            database. No parameters in this query.
    """
    db_type_map = {}
    sql_schemas = None
    sql_tables = None
    sql_views = None
    sql_columns = None
    sql_foreign_keys = None

    def __init__(self, *args, **kwargs):
        self._db = self.module.connect(*args, **kwargs)
    
    def get_db_information(self):
        """
        Get database layout

        Returns a dictionary containing:
            {schemas: {
                    schema_name: {
                        name: text,
                        description: text,
                        tables: {
                            table name: {
                                name: text,
                                description: text,
                                columns: {column name: {
                                    name: text,
                                    default: default value, 
                                    nullable: boolean, 
                                    type: data type}
                                , ... },
                                constraints: [ 
                                    {type: constraint type, 
                                    name: constraint name}
                                    , ... ]
                                }, ...
                            }
                        }, ...
                    }
                foreign_keys: [
                    {src_schema: source schema, src_table: source table, 
                     src_column: source column, src_nullable: boolean, 
                     src_indexed: boolean, dst_schema: destination schema, 
                     dst_table: destination table, 
                     dst_column: destination column, dst_indexed: boolean, 
                     constraint_schema: constraint schema, 
                     constraint_name: constraint name}, ... }
            }
        """
        schema_container = {}
        fkey_container = []
        result = {"schemas": schema_container, "foreign_keys": fkey_container}
        for schema in self.get_schemas():
            table_container = {}
            result["schemas"][schema["name"]] = {
                    "name": schema["name"], 
                    "description": schema["description"], 
                    "tables": table_container}
            
            for table in self.get_tables(schema["name"]):
                constraint_container = {}
                column_container = []
                table_container[table["name"]] = {
                        "columns": column_container, 
                        "constraints": constraint_container, 
                        "name": table["name"],
                        "description": table["description"]}
                
                for column in self.get_columns(schema["name"], table["name"]):
                    column_container.append(column)
                for constraint in self.get_constraints(schema["name"], 
                                                       table["name"]):
                    constraint_container.setdefault(constraint["type"], 
                            []).append(constraint["name"])

        for foreign_key in self.get_foreign_keys():
            fkey_container.append(foreign_key)
        
        return result

    def _query(self, statement, params=()):
        cursor = self._db.cursor()
        cursor.execute(statement, params)
        header = [x[0] for x in cursor.description]
        for row in cursor.fetchall():
            yield dict(zip(header, row))
        cursor.close()

    def get_schemas(self):
        return self._query(self.sql_schemas)

    def get_tables(self, schema):
        return self._query(self.sql_tables, (schema,))

    def get_views(self, schema):
        return self._query(self.sql_views, (schema,))

    def get_columns(self, schema, table):
        for row in self._query(self.sql_columns, (schema, table)):
            # map data types if required
            type_ = row["type"]
            row["type"] = self.db_type_map.get(type_, type_)
            yield row

    def get_foreign_keys(self):
        return self._query(self.sql_foreign_keys)

    def get_constraints(self, schema, table):
        return self._query(self.sql_constraints, (schema, table))


class Json(object):
    """load data from a file written by writer.Json"""
    def __init__(self, filename):
        self._filename = filename

    def get_db_information(self):
        with open(self._filename) as file_:
            return json.load(file_)


class PostgreSQL(Generic):
    db_type_map = {"timestamp without timezone": "timestamp", 
                   "character varying": "varchar"}
    
    default_value_regex = (
        (re.compile(r"nextval\((.+)::regclass\)"), r"nextval(\1)"),
        (re.compile(r"(.*)::timestamp without time zone"), r"\1::timestamp"),
        )

    sql_schemas = """
        SELECT nspname AS name, obj_description(pg_namespace.oid) AS description
        FROM   pg_namespace 
        WHERE  nspname NOT LIKE 'pg_%' AND nspname != 'information_schema';"""

    sql_tables = """
        SELECT relname AS name, obj_description(pg_class.oid) AS description
        FROM   pg_class
        JOIN   pg_namespace ON pg_namespace.oid = relnamespace
        WHERE  pg_namespace.nspname = %s AND relkind='r'
        ORDER BY 1"""

    sql_views = """
        SELECT table_name
        FROM   information_schema.views
        WHERE  table_schema=%s"""
    
    sql_columns = """
        SELECT column_name as name, column_default AS default, 
               is_nullable AS nullable, data_type AS type
        FROM   information_schema.columns
        WHERE  table_schema=%s AND table_name=%s
        ORDER BY ordinal_position"""

    sql_constraints = """
        SELECT constraint_type AS type, constraint_name AS name
        FROM  information_schema.table_constraints 
        WHERE table_schema=%s AND table_name=%s
        ORDER BY constraint_type, constraint_name"""
    
    sql_foreign_keys = """
        SELECT fkn.nspname AS src_schema, 
               fkr.relname AS src_table,
               fka.attname AS src_column, 
               NOT fka.attnotnull AS src_nullable,
               EXISTS (SELECT pg_index.indexrelid, pg_index.indrelid, 
                              pg_index.indkey, pg_index.indclass,
                              pg_index.indnatts, pg_index.indisunique, 
                              pg_index.indisprimary, pg_index.indisclustered, 
                              pg_index.indexprs, pg_index.indpred 
                        FROM  pg_index 
                        WHERE pg_index.indrelid = fkr.oid AND 
                              pg_index.indkey[0] = fka.attnum
                      ) AS src_indexed, 
               pkn.nspname AS dst_schema,
               pkr.relname AS dst_table, 
               pka.attname AS dst_column, 
               EXISTS (SELECT pg_index.indexrelid, pg_index.indrelid, 
                              pg_index.indkey, pg_index.indclass, 
                              pg_index.indnatts, pg_index.indisunique,
                              pg_index.indisprimary, pg_index.indisclustered, 
                              pg_index.indexprs, pg_index.indpred 
                       FROM   pg_index 
                       WHERE  pg_index.indrelid = pkr.oid AND 
                              pg_index.indkey[0] = pka.attnum
                      ) AS dst_indexed,
               c.confupdtype::text || c.confdeltype::text AS ud, 
               cn.nspname AS constraint_schema, 
               c.conname AS constraint_name 
        FROM   pg_constraint c 
        JOIN   pg_namespace cn ON cn.oid = c.connamespace
        JOIN   pg_class fkr ON fkr.oid = c.conrelid
        JOIN   pg_namespace fkn ON fkn.oid = fkr.relnamespace
        JOIN   pg_attribute fka ON fka.attrelid = c.conrelid AND 
               fka.attnum = ANY(c.conkey) 
        JOIN   pg_class pkr ON pkr.oid = c.confrelid
        JOIN   pg_namespace pkn ON pkn.oid = pkr.relnamespace
        JOIN   pg_attribute pka ON pka.attrelid = c.confrelid AND 
               pka.attnum = ANY(c.confkey)
        WHERE  c.contype = 'f';"""

    def __init__(self, *args, **kwargs):
        import pgdb
        self.module = pgdb
        super(PostgreSQL, self).__init__(*args, **kwargs)
    
    def get_columns(self, schema, table):
        for row in super(PostgreSQL, self).get_columns(schema, table):
            if isinstance(row["default"], basestring):
                for (regex, replacement) in self.default_value_regex:
                    row["default"] = regex.sub(replacement, row["default"])
            yield row
