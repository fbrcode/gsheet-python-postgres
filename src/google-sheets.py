"""
Read content from google sheets and transfer to structured postgres database.
Google sheets must be "shared with link" for this approach to work.
"""

import sys
import os
import pandas as pd
import psycopg2
import psycopg2.extras as extras
from dotenv import load_dotenv

def connect(params_dic):
    """ Connect to the PostgreSQL database server """
    conn = None
    try:
        conn = psycopg2.connect(**params_dic)
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
        sys.exit(1) 
    return conn

def restart_schema(conn, schema, dataframe_dict):
    """ (Re)create schema and structures based on schema/dataframe """
    init_schema = f"drop schema if exists {schema} cascade; create schema {schema};"
    ddl_create_table = []
    for k in dataframe_dict:
        ddl_create_table.append("drop table if exists {0}.{1}; create table {0}.{1} ({2} text);".format(
            schema, 
            k, 
            ' text, '.join(list(dataframe_dict[k].columns)))
        )
    cursor = conn.cursor()
    try:
        cursor.execute(init_schema)
        [cursor.execute(ddl) for ddl in ddl_create_table]
        conn.commit()
    except (Exception, psycopg2.DatabaseError) as error:
        print("Error: %s" % error)
        conn.rollback()
        cursor.close()
        return 1
    cursor.close()

def execute_batch(conn, schema, dataframe_dict, page_size=100):
    """ Using psycopg2.extras.execute_batch() to insert the dataframe """
    cursor = conn.cursor()
    try:
        for k in dataframe_dict:
            tuples = [tuple(x) for x in dataframe_dict[k].to_numpy()]
            cols = ','.join(list(dataframe_dict[k].columns))
            values = ','.join(['%s' for x in list(dataframe_dict[k].columns)])
            query  = "insert into {0}.{1} ({2}) values ({3})".format(schema, k, cols, values)
            extras.execute_batch(cursor, query, tuples, page_size)
            conn.commit()
    except (Exception, psycopg2.DatabaseError) as error:
        print("Error: %s" % error)
        conn.rollback()
        cursor.close()
        return 1
    cursor.close()

# load env vars
load_dotenv()

# get parameters
conn_dict = {
    "host"      : os.environ['PG_HOST'],
    "database"  : os.environ['PG_DB'],
    "user"      : os.environ['PG_USER'],
    "password"  : os.environ['PG_PWD'],
    "port"      : os.environ['PG_PORT']
}
db_schema = "gsheet_" + os.environ['PG_SCHEMA']
sheet_src = os.environ['GOOGLE_SHEET_SRC']
sheet_id = os.environ['GOOGLE_SHEET_ID']
sheet_tabs = os.environ['GOOGLE_SHEET_TABS']

# parsing, transformations and dataframe build up
sheet_split_dict = dict(x.split("=") for x in sheet_tabs.split(";"))
sheet_range_dict = { k: [int(i) for i in v.split(":")] for (k,v) in sheet_split_dict.items() }
sheet_link_dict = {k: sheet_src.format(sheet_id, k) for k in sheet_range_dict}
sheets_df = {k: pd.read_csv(tab).iloc[:, sheet_range_dict[k][0]:sheet_range_dict[k][1]] for k, tab in sheet_link_dict.items() }
for k in sheets_df:
    sheets_df[k].rename(columns=lambda s: s.replace(" ", "_").lower(), inplace=True)

# transfer dataframe data to postgres
conn = connect(conn_dict) 
restart_schema(conn, db_schema, sheets_df) 
execute_batch(conn, db_schema, sheets_df)
