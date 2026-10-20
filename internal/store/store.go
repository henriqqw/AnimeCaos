package store

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	_ "modernc.org/sqlite"
	"os"
	"path/filepath"
	"time"
)

type Store struct {
	DB  *sql.DB
	Dir string
	tx  *sql.Tx
}
type database interface {
	Exec(string, ...any) (sql.Result, error)
	Query(string, ...any) (*sql.Rows, error)
	QueryRow(string, ...any) *sql.Row
}

func (s *Store) sql() database {
	if s.tx != nil {
		return s.tx
	}
	return s.DB
}

func Open(dir string) (*Store, error) {
	if e := os.MkdirAll(dir, 0700); e != nil {
		return nil, e
	}
	db, e := sql.Open("sqlite", filepath.Join(dir, "state.db"))
	if e != nil {
		return nil, e
	}
	db.SetMaxOpenConns(1)
	var version int
	if e = db.QueryRow("PRAGMA user_version").Scan(&version); e != nil {
		db.Close()
		return nil, e
	}
	if version > 1 {
		db.Close()
		return nil, fmt.Errorf("dados da versão %d não são compatíveis com este aplicativo", version)
	}
	_, e = db.Exec(`PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000;
CREATE TABLE IF NOT EXISTS records (bucket TEXT NOT NULL, key TEXT NOT NULL, value BLOB NOT NULL, updated INTEGER NOT NULL, PRIMARY KEY(bucket,key));
CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value BLOB NOT NULL, soft INTEGER NOT NULL, hard INTEGER NOT NULL, accessed INTEGER NOT NULL);
PRAGMA user_version=1;`)
	if e != nil {
		db.Close()
		return nil, e
	}
	s := &Store{DB: db, Dir: dir}
	if e = s.ImportLegacy(); e != nil {
		db.Close()
		return nil, e
	}
	if e = s.Prune(); e != nil {
		db.Close()
		return nil, e
	}
	return s, nil
}
func (s *Store) Close() error { return s.DB.Close() }
func (s *Store) Put(bucket, key string, v any) error {
	b, e := json.Marshal(v)
	if e != nil {
		return e
	}
	_, e = s.sql().Exec(`INSERT INTO records VALUES(?,?,?,?) ON CONFLICT(bucket,key) DO UPDATE SET value=excluded.value,updated=excluded.updated`, bucket, key, b, time.Now().Unix())
	return e
}
func (s *Store) Get(bucket, key string, v any) error {
	var b []byte
	e := s.sql().QueryRow(`SELECT value FROM records WHERE bucket=? AND key=?`, bucket, key).Scan(&b)
	if e != nil {
		return e
	}
	return json.Unmarshal(b, v)
}
func (s *Store) Delete(bucket, key string) error {
	_, e := s.sql().Exec(`DELETE FROM records WHERE bucket=? AND key=?`, bucket, key)
	return e
}

// DeleteSensitive removes a credential record and asks SQLite to scrub the
// deleted bytes from the database and WAL. It is used only after the system
// credential vault confirms that the migrated value has been stored.
func (s *Store) DeleteSensitive(bucket, key string) error {
	ctx := context.Background()
	conn, e := s.DB.Conn(ctx)
	if e != nil {
		return e
	}
	defer conn.Close()
	if _, e = conn.ExecContext(ctx, `PRAGMA secure_delete=ON`); e != nil {
		return e
	}
	if _, e = conn.ExecContext(ctx, `DELETE FROM records WHERE bucket=? AND key=?`, bucket, key); e != nil {
		return e
	}
	var busy, logPages, checkpointedPages int
	if e = conn.QueryRowContext(ctx, `PRAGMA wal_checkpoint(TRUNCATE)`).Scan(&busy, &logPages, &checkpointedPages); e != nil {
		return e
	}
	if busy != 0 {
		return fmt.Errorf("não foi possível limpar o WAL de credenciais (busy=%d)", busy)
	}
	_, e = conn.ExecContext(ctx, `VACUUM`)
	return e
}
func (s *Store) List(bucket string) ([]json.RawMessage, error) {
	rows, e := s.sql().Query(`SELECT value FROM records WHERE bucket=? ORDER BY updated DESC,key`, bucket)
	if e != nil {
		return nil, e
	}
	defer rows.Close()
	out := []json.RawMessage{}
	for rows.Next() {
		var b []byte
		if e = rows.Scan(&b); e != nil {
			return nil, e
		}
		out = append(out, json.RawMessage(b))
	}
	return out, rows.Err()
}
func (s *Store) CacheGet(key string, v any) (bool, bool) {
	var b []byte
	var soft, hard int64
	if s.DB.QueryRow(`SELECT value,soft,hard FROM cache WHERE key=?`, key).Scan(&b, &soft, &hard) != nil {
		return false, false
	}
	now := time.Now().Unix()
	if now >= hard {
		return false, false
	}
	if json.Unmarshal(b, v) != nil {
		return false, false
	}
	s.DB.Exec(`UPDATE cache SET accessed=? WHERE key=?`, now, key)
	return true, now >= soft
}
func (s *Store) CachePut(key string, v any, soft, hard time.Duration) error {
	b, e := json.Marshal(v)
	if e != nil {
		return e
	}
	now := time.Now()
	_, e = s.DB.Exec(`INSERT INTO cache VALUES(?,?,?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,soft=excluded.soft,hard=excluded.hard,accessed=excluded.accessed`, key, b, now.Add(soft).Unix(), now.Add(hard).Unix(), now.Unix())
	return e
}
func (s *Store) Prune() error {
	_, e := s.DB.Exec(`DELETE FROM cache WHERE hard<? OR key IN (SELECT key FROM cache ORDER BY accessed DESC LIMIT -1 OFFSET 5000)`, time.Now().Unix())
	return e
}
func (s *Store) BackupFile(name string) error {
	src := filepath.Join(s.Dir, name)
	b, e := os.ReadFile(src)
	if os.IsNotExist(e) {
		b, e = os.ReadFile(filepath.Join(filepath.Dir(s.Dir), "animecaos", name))
	}
	if os.IsNotExist(e) {
		return nil
	}
	if e != nil {
		return e
	}
	dir := filepath.Join(s.Dir, "legacy-backup")
	if e = os.MkdirAll(dir, 0700); e != nil {
		return e
	}
	dst := filepath.Join(dir, name)
	f, e := os.OpenFile(dst, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0600)
	if os.IsExist(e) {
		return nil
	}
	if e != nil {
		return e
	}
	_, e = f.Write(b)
	ce := f.Close()
	if e != nil {
		return e
	}
	return ce
}
func DecodeList[T any](s *Store, bucket string) ([]T, error) {
	raw, e := s.List(bucket)
	out := []T{}
	if e != nil {
		return out, e
	}
	for _, b := range raw {
		var v T
		if e = json.Unmarshal(b, &v); e != nil {
			return nil, fmt.Errorf("%s: %w", bucket, e)
		}
		out = append(out, v)
	}
	return out, nil
}
