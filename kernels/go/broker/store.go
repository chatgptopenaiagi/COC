package broker

import (
	"database/sql"
	"encoding/json"
	"fmt"
	_ "modernc.org/sqlite"
	"os"
	"path/filepath"
)

type Store struct{ DB *sql.DB }

func OpenStore(path string) (*Store, error) {
	if path != ":memory:" {
		if e := os.MkdirAll(filepath.Dir(path), 0700); e != nil {
			return nil, e
		}
	}
	db, e := sql.Open("sqlite", path)
	if e != nil {
		return nil, e
	}
	db.SetMaxOpenConns(1)
	_, e = db.Exec(`PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL; PRAGMA busy_timeout=5000;
 CREATE TABLE IF NOT EXISTS migrations(version INTEGER PRIMARY KEY, applied INTEGER NOT NULL);
 CREATE TABLE IF NOT EXISTS tokens(hash TEXT PRIMARY KEY, principal TEXT NOT NULL, scopes TEXT NOT NULL, expires INTEGER NOT NULL, revoked INTEGER NOT NULL DEFAULT 0, parent_hash TEXT NOT NULL DEFAULT '');
 CREATE TABLE IF NOT EXISTS objects(kind TEXT NOT NULL,id TEXT NOT NULL,body TEXT NOT NULL,PRIMARY KEY(kind,id));
 CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY, owner TEXT NOT NULL, host TEXT NOT NULL, root TEXT NOT NULL, parent TEXT NOT NULL, state TEXT NOT NULL, idem TEXT NOT NULL, fingerprint TEXT NOT NULL,body TEXT NOT NULL, UNIQUE(owner,idem));
 CREATE TABLE IF NOT EXISTS events(sequence INTEGER PRIMARY KEY AUTOINCREMENT,kind TEXT NOT NULL,task_id TEXT NOT NULL,principal TEXT NOT NULL,data TEXT NOT NULL,at INTEGER NOT NULL,previous_hash TEXT NOT NULL,hash TEXT NOT NULL);
 INSERT OR IGNORE INTO migrations VALUES(1,unixepoch());
 UPDATE tokens SET expires=expires*1000 WHERE expires<100000000000;
 INSERT OR IGNORE INTO migrations VALUES(2,unixepoch());`)
	if e != nil {
		db.Close()
		return nil, e
	}
	return &Store{db}, nil
}
func (s *Store) put(kind, id string, v any) error {
	b, e := json.Marshal(v)
	if e != nil {
		return e
	}
	_, e = s.DB.Exec("INSERT INTO objects VALUES(?,?,?) ON CONFLICT(kind,id) DO UPDATE SET body=excluded.body", kind, id, string(b))
	return e
}
func (s *Store) get(kind, id string, v any) error {
	var b string
	if e := s.DB.QueryRow("SELECT body FROM objects WHERE kind=? AND id=?", kind, id).Scan(&b); e != nil {
		return e
	}
	return json.Unmarshal([]byte(b), v)
}
func (s *Store) list(kind string) ([]Object, error) {
	rows, e := s.DB.Query("SELECT body FROM objects WHERE kind=? ORDER BY id", kind)
	if e != nil {
		return nil, e
	}
	defer rows.Close()
	out := []Object{}
	for rows.Next() {
		var b string
		if e = rows.Scan(&b); e != nil {
			return nil, e
		}
		v := Object{}
		if e = json.Unmarshal([]byte(b), &v); e != nil {
			return nil, e
		}
		out = append(out, v)
	}
	return out, rows.Err()
}
func (s *Store) task(id string) (Task, error) {
	var t Task
	var b string
	e := s.DB.QueryRow("SELECT body FROM tasks WHERE id=?", id).Scan(&b)
	if e != nil {
		return t, e
	}
	e = json.Unmarshal([]byte(b), &t)
	return t, e
}
func (s *Store) tasks() ([]Task, error) {
	rows, e := s.DB.Query("SELECT body FROM tasks ORDER BY rowid")
	if e != nil {
		return nil, e
	}
	defer rows.Close()
	out := []Task{}
	for rows.Next() {
		var b string
		var t Task
		if e = rows.Scan(&b); e != nil {
			return nil, e
		}
		if e = json.Unmarshal([]byte(b), &t); e != nil {
			return nil, e
		}
		out = append(out, t)
	}
	return out, rows.Err()
}
func appendEvent(tx *sql.Tx, kind, task, principal string, data Object) error {
	var prev string
	e := tx.QueryRow("SELECT hash FROM events ORDER BY sequence DESC LIMIT 1").Scan(&prev)
	if e != nil && e != sql.ErrNoRows {
		return e
	}
	ev := Event{Kind: kind, TaskID: task, Principal: principal, Data: data, At: now(), PreviousHash: prev}
	ev.Hash = digest(Object{"kind": kind, "task_id": task, "principal": principal, "data": data, "at": ev.At, "previous_hash": prev})
	b, _ := json.Marshal(data)
	_, e = tx.Exec("INSERT INTO events(kind,task_id,principal,data,at,previous_hash,hash) VALUES(?,?,?,?,?,?,?)", kind, task, principal, string(b), ev.At, prev, ev.Hash)
	return e
}
func (s *Store) event(kind, task, principal string, data Object) error {
	tx, e := s.DB.Begin()
	if e != nil {
		return e
	}
	defer tx.Rollback()
	if e = appendEvent(tx, kind, task, principal, data); e != nil {
		return e
	}
	return tx.Commit()
}
func (s *Store) saveTask(t Task, kind, actor string) error {
	tx, e := s.DB.Begin()
	if e != nil {
		return e
	}
	defer tx.Rollback()
	t.Updated = now()
	b, _ := json.Marshal(t)
	_, e = tx.Exec(`INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET state=excluded.state,body=excluded.body`, t.ID, t.Owner, t.HostID, t.RootID, t.ParentID, t.State, t.IdempotencyKey, t.Fingerprint, string(b))
	if e != nil {
		return e
	}
	if e = appendEvent(tx, kind, t.ID, actor, Object{"state": t.State, "attempt": t.Attempt, "task_digest": digest(t)}); e != nil {
		return e
	}
	return tx.Commit()
}
func (s *Store) events(after int64, limit int) ([]Event, error) {
	rows, e := s.DB.Query("SELECT sequence,kind,task_id,principal,data,at,previous_hash,hash FROM events WHERE sequence>? ORDER BY sequence LIMIT ?", after, limit)
	if e != nil {
		return nil, e
	}
	defer rows.Close()
	out := []Event{}
	for rows.Next() {
		var v Event
		var b string
		if e = rows.Scan(&v.Sequence, &v.Kind, &v.TaskID, &v.Principal, &b, &v.At, &v.PreviousHash, &v.Hash); e != nil {
			return nil, e
		}
		if e = json.Unmarshal([]byte(b), &v.Data); e != nil {
			return nil, e
		}
		out = append(out, v)
	}
	return out, rows.Err()
}
func (s *Store) verify() error {
	after := int64(0)
	prev := ""
	latest := map[string]string{}
	for {
		events, e := s.events(after, 1000)
		if e != nil {
			return e
		}
		if len(events) == 0 {
			tasks, er := s.tasks()
			if er != nil {
				return er
			}
			for _, task := range tasks {
				if expected, ok := latest[task.ID]; ok && expected != digest(task) {
					return fmt.Errorf("task integrity failure: %s", task.ID)
				}
			}
			return nil
		}
		for _, v := range events {
			if hash, ok := v.Data["task_digest"].(string); ok {
				latest[v.TaskID] = hash
			}
			h := digest(Object{"kind": v.Kind, "task_id": v.TaskID, "principal": v.Principal, "data": v.Data, "at": v.At, "previous_hash": v.PreviousHash})
			if v.PreviousHash != prev || h != v.Hash {
				return fmt.Errorf("event integrity failure at %d", v.Sequence)
			}
			prev = v.Hash
			after = v.Sequence
		}
	}
}
