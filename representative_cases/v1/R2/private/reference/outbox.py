import json
import math
import sqlite3

class ConflictError(ValueError):
    pass

def number(value, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or (value <= 0 if positive else value < 0):
        raise ValueError('invalid time')

class Outbox:
    def __init__(self, path):
        self.db = sqlite3.connect(path, timeout=5)
        self.db.row_factory = sqlite3.Row
        self.db.execute("""CREATE TABLE IF NOT EXISTS messages (
          id INTEGER PRIMARY KEY AUTOINCREMENT, tenant TEXT NOT NULL,
          key TEXT NOT NULL, payload TEXT NOT NULL, state TEXT NOT NULL,
          available_at REAL NOT NULL DEFAULT 0, lease_until REAL,
          attempts INTEGER NOT NULL DEFAULT 0, UNIQUE(tenant,key))""")
        self.db.commit()
    def enqueue(self, tenant, key, payload):
        if not isinstance(tenant, str) or not tenant or not isinstance(key, str) or not key:
            raise ValueError('tenant and key required')
        try:
            encoded = json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ValueError('invalid payload') from exc
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            row = self.db.execute('SELECT id,payload FROM messages WHERE tenant=? AND key=?', (tenant, key)).fetchone()
            if row:
                if row['payload'] != encoded:
                    raise ConflictError('key already has a different payload')
                return row['id']
            return self.db.execute("INSERT INTO messages(tenant,key,payload,state) VALUES(?,?,?,'pending')", (tenant,key,encoded)).lastrowid
    def claim(self, tenant, now, lease_seconds, limit):
        if not isinstance(tenant, str) or not tenant:
            raise ValueError('tenant required')
        number(now); number(lease_seconds, True)
        if isinstance(limit,bool) or not isinstance(limit,int) or limit <= 0:
            raise ValueError('invalid limit')
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            rows = self.db.execute("SELECT * FROM messages WHERE tenant=? AND ((state='pending' AND available_at<=?) OR (state='leased' AND lease_until<=?)) ORDER BY id LIMIT ?", (tenant,now,now,limit)).fetchall()
            result=[]
            for row in rows:
                self.db.execute("UPDATE messages SET state='leased',lease_until=?,attempts=attempts+1 WHERE id=?", (now+lease_seconds,row['id']))
                result.append({'id':row['id'],'key':row['key'],'payload':json.loads(row['payload']),'attempts':row['attempts']+1})
            return result
    def complete(self, tenant, message_id):
        with self.db:
            return self.db.execute("UPDATE messages SET state='done',lease_until=NULL WHERE tenant=? AND id=? AND state='leased'", (tenant,message_id)).rowcount == 1
    def retry(self, tenant, message_id, available_at):
        number(available_at)
        with self.db:
            return self.db.execute("UPDATE messages SET state='pending',available_at=?,lease_until=NULL WHERE tenant=? AND id=? AND state='leased'", (available_at,tenant,message_id)).rowcount == 1
    def close(self):
        self.db.close()
