"""An older database file (created before new columns existed) must keep working after an update."""
from sqlalchemy import inspect, text

from app.db import engine, init_db


def test_old_database_gets_new_columns_with_defaults(client):
    with engine.begin() as conn:
        conn.execute(text('DROP TABLE "emaildraft"'))
        conn.execute(text('CREATE TABLE "emaildraft" (id INTEGER PRIMARY KEY, client_id INTEGER, alert_ids JSON, '
                          'subject VARCHAR, body VARCHAR, status VARCHAR, created_at DATETIME, updated_at DATETIME)'))
        conn.execute(text("INSERT INTO emaildraft (client_id, alert_ids, subject, body, status) "
                          "VALUES (1, '[]', 'Old', 'Old body text', 'draft')"))
    init_db()
    cols = {c["name"] for c in inspect(engine).get_columns("emaildraft")}
    assert {"edited_by_user", "run_id"} <= cols
    with engine.connect() as conn:
        assert conn.execute(text("SELECT edited_by_user FROM emaildraft")).scalar() == 0
    assert client.get("/api/outreach").status_code == 200
