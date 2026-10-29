import importlib.util
from pathlib import Path
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text

def test_messages_migration_round_trip_preserves_users():
    path=Path(__file__).resolve().parents[1]/'alembic/versions/c34d56e78f90_add_subscriber_messages.py'
    spec=importlib.util.spec_from_file_location('messages_migration',path)
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    engine=create_engine('sqlite://')
    with engine.begin() as conn:
        conn.execute(text('CREATE TABLE users (id CHAR(32) PRIMARY KEY, username VARCHAR(100))'))
        conn.execute(text("INSERT INTO users VALUES ('0123456789abcdef0123456789abcdef','existing')"))
        with Operations.context(MigrationContext.configure(conn)): migration.upgrade()
        assert {'chat_messages','chat_read_states'} <= set(inspect(conn).get_table_names())
        with Operations.context(MigrationContext.configure(conn)): migration.downgrade()
        assert inspect(conn).get_table_names()==['users']
        assert conn.execute(text('SELECT username FROM users')).scalar()=='existing'
