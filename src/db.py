"""db.py — PostgreSQL connection helpers and reusable query utilities."""

import os
from contextlib import contextmanager
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# Load environment variables from .env
load_dotenv()

# Private global to cache the engine singleton
_engine = None

def get_engine():
    """
    Returns the SQLAlchemy engine singleton. Creates the engine on first call.

    Returns:
        sqlalchemy.engine.Engine: The database engine.
    
    Raises:
        RuntimeError: If connection URL parameters are missing or creation fails.
    """
    global _engine
    if _engine is None:
        db_host = os.getenv("DB_HOST", "localhost")
        db_port = os.getenv("DB_PORT", "5432")
        db_name = os.getenv("DB_NAME", "shockproof")
        db_user = os.getenv("DB_USER", "postgres")
        db_password = os.getenv("DB_PASSWORD", "postgres")
        
        db_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        try:
            _engine = create_engine(db_url)
        except SQLAlchemyError as e:
            raise RuntimeError(f"Failed to create SQLAlchemy engine for {db_url}: {e}") from e
    return _engine

@contextmanager
def get_connection():
    """
    Context manager yielding an open database connection, closing it cleanly on exit.

    Yields:
        sqlalchemy.engine.Connection: An active database connection.
    
    Raises:
        RuntimeError: Wraps any SQLAlchemyError occurring during connection.
    """
    engine = get_engine()
    conn = None
    try:
        conn = engine.connect()
        yield conn
    except SQLAlchemyError as e:
        raise RuntimeError(f"Database error during connection context: {e}") from e
    finally:
        if conn:
            conn.close()

def read_table(table_name, engine=None):
    """
    Reads an entire table into a pandas DataFrame.

    Args:
        table_name (str): The name of the target database table.
        engine (sqlalchemy.engine.Engine, optional): Database engine to use. If None, uses default.

    Returns:
        pd.DataFrame: DataFrame containing all columns and rows from the table.

    Raises:
        RuntimeError: Wraps any SQLAlchemyError occurring during read.
    """
    if engine is None:
        engine = get_engine()
    try:
        return pd.read_sql_table(table_name, con=engine)
    except SQLAlchemyError as e:
        raise RuntimeError(f"Failed to read table '{table_name}': {e}") from e

def read_query(sql, engine=None, params=None):
    """
    Executes a raw SQL query and returns the results in a DataFrame.

    Args:
        sql (str): Raw SQL query string.
        engine (sqlalchemy.engine.Engine, optional): Database engine to use. If None, uses default.
        params (dict, optional): Bind parameters for parameterizing the query.

    Returns:
        pd.DataFrame: DataFrame containing query results.

    Raises:
        RuntimeError: Wraps any SQLAlchemyError occurring during query execution.
    """
    if engine is None:
        engine = get_engine()
    try:
        query = text(sql)
        return pd.read_sql(query, con=engine, params=params)
    except SQLAlchemyError as e:
        raise RuntimeError(f"Failed to execute read query: {e}") from e

def write_dataframe(df, table_name, engine=None, if_exists='replace'):
    """
    Writes a pandas DataFrame to a database table using pandas to_sql.

    Args:
        df (pd.DataFrame): DataFrame to write to the database.
        table_name (str): Name of target table.
        engine (sqlalchemy.engine.Engine, optional): Database engine to use. If None, uses default.
        if_exists (str, optional): Behavior if table already exists ('fail', 'replace', 'append'). Default is 'replace'.

    Raises:
        RuntimeError: Wraps any SQLAlchemyError occurring during write.
    """
    if engine is None:
        engine = get_engine()
    try:
        df.to_sql(table_name, con=engine, if_exists=if_exists, index=False)
    except SQLAlchemyError as e:
        raise RuntimeError(f"Failed to write DataFrame to table '{table_name}': {e}") from e

def execute_statement(sql, engine=None, params=None):
    """
    Executes a non-returning SQL statement (such as INSERT, UPDATE, DELETE).
    Automatically commits changes on success.

    Args:
        sql (str): SQL statement to execute.
        engine (sqlalchemy.engine.Engine, optional): Database engine to use. If None, uses default.
        params (dict, optional): Bind parameters for parameterizing the statement.

    Raises:
        RuntimeError: Wraps any SQLAlchemyError occurring during statement execution.
    """
    if engine is None:
        engine = get_engine()
    try:
        with engine.begin() as conn:
            conn.execute(text(sql), params or {})
    except SQLAlchemyError as e:
        raise RuntimeError(f"Failed to execute statement: {e}") from e

def test_connection():
    """
    Performs a simple health check query (SELECT 1) and prints database connection status.
    """
    db_host = os.getenv("DB_HOST", "localhost")
    db_name = os.getenv("DB_NAME", "shockproof")
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print(f"Connection SUCCESSful to database '{db_name}' on host '{db_host}'.")
    except Exception as e:
        print(f"Connection FAILED to database '{db_name}' on host '{db_host}'. Error: {e}")

if __name__ == '__main__':
    test_connection()
