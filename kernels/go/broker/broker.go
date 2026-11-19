package broker

import (
	"context"
	"encoding/json"
	"errors"
	"os"
	"runtime"
	"sync"
	"time"
)

type Broker struct {
	Store    *Store
	mu       sync.Mutex
	Schema   map[string]any
	Started  int64
	Shutdown chan struct{}
	once     sync.Once
}

func New(db, bootstrap string, schema Object) (*Broker, error) {
	if len(bootstrap) < 32 {
		return nil, errors.New("bootstrap token must contain at least 32 characters")
	}
	s, e := OpenStore(db)
	if e != nil {
		return nil, e
	}
	if e = s.verify(); e != nil {
		s.DB.Close()
		return nil, e
	}
	_, e = s.DB.Exec("INSERT INTO tokens(hash,principal,scopes,expires) VALUES(?,?,?,?) ON CONFLICT(hash) DO NOTHING", tokenHash(bootstrap), "operator", `["*"]`, time.Now().Add(30*24*time.Hour).UnixMilli())
	if e != nil {
		s.DB.Close()
		return nil, e
	}
	b := &Broker{Store: s, Schema: schema, Started: now(), Shutdown: make(chan struct{})}
	tasks, e := s.tasks()
	if e != nil {
		return nil, e
	}
	for _, t := range tasks {
		if t.State == "running" || t.State == "cancel_requested" {
			t.State = "outcome_unknown"
			if e = s.saveTask(t, "recovery.uncertain", "broker"); e != nil {
				return nil, e
			}
		}
	}
	return b, nil
}
func (b *Broker) Authenticate(token string) (Principal, error) {
	return b.authenticateHash(tokenHash(token))
}
func (b *Broker) authenticateHash(h string) (Principal, error) {
	p := Principal{}
	p.Hash = h
	var scopes string
	var revoked int
	e := b.Store.DB.QueryRow("SELECT principal,scopes,expires,revoked,parent_hash FROM tokens WHERE hash=?", h).Scan(&p.ID, &scopes, &p.Expires, &revoked, &p.ParentHash)
	if e != nil || revoked != 0 || p.Expires <= now() {
		return p, fault("UNAUTHORIZED", "invalid, expired or revoked credential")
	}
	if e = json.Unmarshal([]byte(scopes), &p.Scopes); e != nil {
		return p, e
	}
	ancestor := p.ParentHash
	seen := map[string]bool{}
	for ancestor != "" {
		if seen[ancestor] {
			return p, fault("UNAUTHORIZED", "credential ancestry cycle")
		}
		seen[ancestor] = true
		var parent string
		var expiry int64
		if e = b.Store.DB.QueryRow("SELECT revoked,expires,parent_hash FROM tokens WHERE hash=?", ancestor).Scan(&revoked, &expiry, &parent); e != nil || revoked != 0 || expiry <= now() {
			return p, fault("UNAUTHORIZED", "parent grant is no longer valid")
		}
		ancestor = parent
	}
	return p, nil
}
func (b *Broker) Dispatch(p Principal, r Request) (any, error) {
	b.mu.Lock()
	defer b.mu.Unlock()
	e := r.Params
	v := e.Payload
	if e.AgentID != p.ID {
		return nil, fault("IDENTITY_MISMATCH", "agent identity does not match credential")
	}
	switch r.Method {
	case "COC.HELLO":
		return Object{"protocol": Version, "methods": Methods, "instance_started": b.Started, "principal": p.ID}, nil
	case "COC.AUTHENTICATE":
		if str(v, "action") == "panel_ticket" {
			return b.panelTicket(p)
		}
		if str(v, "action") == "revoke" {
			if er := p.Require("auth:issue"); er != nil {
				return nil, er
			}
			h := str(v, "token_hash")
			if !p.Allows("*") {
				var parent string
				if er := b.Store.DB.QueryRow("SELECT parent_hash FROM tokens WHERE hash=?", h).Scan(&parent); er != nil || parent != p.Hash {
					return nil, fault("SCOPE_DENIED", "not a directly issued credential")
				}
			}
			_, er := b.Store.DB.Exec("UPDATE tokens SET revoked=1 WHERE hash=?", h)
			if er != nil {
				return nil, er
			}
			return Object{"revoked": true}, b.Store.event("credential.revoked", "", p.ID, Object{"token_hash": h})
		}
		if str(v, "action") == "inspect" {
			return p, nil
		}
		if er := p.Require("auth:issue"); er != nil {
			return nil, er
		}
		scopes := stringsOf(v["scopes"])
		if len(scopes) == 0 {
			return nil, fault("INVALID_ARGUMENT", "at least one scope required")
		}
		for _, s := range scopes {
			if !p.Allows(s) {
				return nil, fault("SCOPE_DENIED", "delegation cannot widen authority")
			}
		}
		id := str(v, "principal")
		if id == "" || id == "operator" {
			return nil, fault("INVALID_ARGUMENT", "distinct principal required")
		}
		var existing int
		if er := b.Store.DB.QueryRow("SELECT count(*) FROM tokens WHERE principal=?", id).Scan(&existing); er != nil {
			return nil, er
		}
		if existing > 0 && !p.Allows("*") {
			return nil, fault("SCOPE_DENIED", "only operator can rotate an existing principal credential")
		}
		ttl := number(v, "ttl_seconds", 300)
		if ttl < 1 || ttl > 86400 {
			return nil, fault("INVALID_ARGUMENT", "ttl must be 1..86400")
		}
		exp := now() + int64(ttl)*1000
		if exp > p.Expires {
			exp = p.Expires
		}
		token := ID() + ID()
		sc, _ := json.Marshal(scopes)
		_, er := b.Store.DB.Exec("INSERT INTO tokens(hash,principal,scopes,expires,parent_hash) VALUES(?,?,?,?,?)", tokenHash(token), id, string(sc), exp, p.Hash)
		if er != nil {
			return nil, er
		}
		if er = b.Store.event("credential.issued", "", p.ID, Object{"principal": id, "scopes": scopes, "expires": exp}); er != nil {
			return nil, er
		}
		return Object{"token": token, "token_hash": tokenHash(token), "principal": id, "scopes": scopes, "expires": exp}, nil
	case "COC.REGISTER":
		kind := str(v, "kind")
		if kind == "agent" {
			if er := p.Require("agent:register"); er != nil {
				return nil, er
			}
			record := Object{"id": p.ID, "name": str(v, "name"), "provider": str(v, "provider"), "last_seen": now()}
			return record, b.Store.put("agent", p.ID, record)
		}
		if er := p.Require("host:register"); er != nil {
			return nil, er
		}
		var h Host
		if er := decode(v, &h); er != nil {
			return nil, er
		}
		if h.ID == "" || len(h.Capabilities) == 0 {
			return nil, fault("INVALID_ARGUMENT", "host id and capabilities required")
		}
		old := Host{}
		if er := b.Store.get("host", h.ID, &old); er == nil && old.Owner != p.ID && !p.Allows("*") {
			return nil, fault("CONFLICT", "host belongs to another principal")
		}
		names := map[string]bool{}
		for _, c := range h.Capabilities {
			if c.Name == "" || names[c.Name] || c.InputSchema == nil || c.OutputSchema == nil {
				return nil, fault("INVALID_ARGUMENT", "unique names and schemas required")
			}
			names[c.Name] = true
			for _, schema := range []Object{c.InputSchema, c.OutputSchema} {
				if er := compileSchema(schema); er != nil {
					return nil, fault("SCHEMA_INVALID", er.Error())
				}
			}
		}
		h.Owner = p.ID
		h.LastSeen = now()
		h.Attached = true
		if er := b.Store.put("host", h.ID, h); er != nil {
			return nil, er
		}
		return h, b.Store.event("host.registered", "", p.ID, Object{"host_id": h.ID})
	case "COC.DISCOVER", "COC.CAPABILITIES":
		if str(v, "view") == "system" {
			return b.snapshot(p)
		}
		if er := p.Require("discover"); er != nil {
			return nil, er
		}
		hosts, er := b.Store.list("host")
		if er != nil {
			return nil, er
		}
		visible := []Host{}
		for _, raw := range hosts {
			var h Host
			decode(raw, &h)
			caps := []Capability{}
			for _, c := range h.Capabilities {
				if p.Allows("tool:"+h.ID+":"+c.Name) || h.Owner == p.ID {
					caps = append(caps, c)
				}
			}
			if len(caps) > 0 {
				h.Capabilities = caps
				visible = append(visible, h)
			}
		}
		return Object{"hosts": visible}, nil
	case "COC.ATTACH":
		if er := p.Require("session:attach"); er != nil {
			return nil, er
		}
		id := str(v, "session_id")
		if id == "" {
			id = ID()
		}
		old := Object{}
		if er := b.Store.get("session", id, &old); er == nil && str(old, "owner") != p.ID && !p.Allows("*") {
			return nil, fault("SCOPE_DENIED", "session is owned by another principal")
		}
		session := Object{"id": id, "owner": p.ID, "host_id": str(v, "host_id"), "codex_thread_id": str(v, "codex_thread_id"), "status": "attached", "updated": now()}
		return session, b.Store.put("session", id, session)
	case "COC.DELEGATE", "COC.TOOL_REQUEST":
		return b.submit(p, v)
	case "COC.TOOL_RESULT":
		return b.finish(p, v)
	case "COC.RECOVER":
		if str(v, "action") == "claim" {
			return b.claim(p, str(v, "host_id"))
		}
		if str(v, "action") == "retry" {
			return b.retry(p, str(v, "task_id"))
		}
		if str(v, "task_id") != "" {
			t, er := b.Store.task(str(v, "task_id"))
			if er != nil {
				return nil, fault("NOT_FOUND", "task not found")
			}
			if !b.canRead(p, t) {
				return nil, fault("SCOPE_DENIED", "task is not visible")
			}
			return t, nil
		}
		return b.snapshot(p)
	case "COC.CANCEL":
		return b.cancel(p, str(v, "task_id"))
	case "COC.HEARTBEAT":
		h, er := b.ownedHost(p, str(v, "host_id"))
		if er != nil {
			return nil, er
		}
		h.LastSeen = now()
		h.Attached = true
		if er = b.Store.put("host", h.ID, h); er != nil {
			return nil, er
		}
		ids := []string{}
		tasks, er := b.Store.tasks()
		if er != nil {
			return nil, er
		}
		for _, t := range tasks {
			if t.HostID != h.ID {
				continue
			}
			if t.State == "cancel_requested" || t.State == "outcome_unknown" {
				ids = append(ids, t.ID)
			}
			if t.State == "running" {
				t.LeaseUntil = now() + 10000
				if er = b.Store.saveTask(t, "task.lease_renewed", p.ID); er != nil {
					return nil, er
				}
			}
		}
		return Object{"cancel_task_ids": ids, "server_time": now()}, nil
	case "COC.EVENT", "COC.MESSAGE", "COC.ERROR":
		if er := p.Require("event:write"); er != nil {
			return nil, er
		}
		task := str(v, "task_id")
		if task != "" {
			t, er := b.Store.task(task)
			if er != nil || !b.canRead(p, t) {
				return nil, fault("SCOPE_DENIED", "task is not visible")
			}
		}
		if _, ok := v["token"]; ok {
			return nil, fault("INVALID_ARGUMENT", "secrets must not be logged")
		}
		return Object{"recorded": true}, b.Store.event(r.Method, task, p.ID, v)
	case "COC.DETACH":
		if id := str(v, "host_id"); id != "" {
			h, er := b.ownedHost(p, id)
			if er != nil {
				return nil, er
			}
			h.Attached = false
			return Object{"detached": id}, b.Store.put("host", id, h)
		}
		id := str(v, "session_id")
		s := Object{}
		if er := b.Store.get("session", id, &s); er != nil {
			return nil, fault("NOT_FOUND", "session not found")
		}
		if str(s, "owner") != p.ID && !p.Allows("*") {
			return nil, fault("SCOPE_DENIED", "session belongs to another principal")
		}
		s["status"] = "detached"
		return s, b.Store.put("session", id, s)
	case "COC.SHUTDOWN":
		if er := p.Require("system:shutdown"); er != nil {
			return nil, er
		}
		if er := b.Store.event("system.shutdown", "", p.ID, Object{}); er != nil {
			return nil, er
		}
		b.once.Do(func() { close(b.Shutdown) })
		return Object{"draining": true}, nil
	}
	return nil, fault("METHOD_NOT_FOUND", "unsupported method")
}
func (b *Broker) ownedHost(p Principal, id string) (Host, error) {
	var h Host
	if er := b.Store.get("host", id, &h); er != nil {
		return h, fault("NOT_FOUND", "host not found")
	}
	if h.Owner != p.ID && !p.Allows("*") {
		return h, fault("SCOPE_DENIED", "host belongs to another principal")
	}
	return h, nil
}
func (b *Broker) canRead(p Principal, t Task) bool {
	if p.Allows("system:read") || p.Allows("*") || p.ID == t.Owner {
		return true
	}
	var h Host
	return b.Store.get("host", t.HostID, &h) == nil && h.Owner == p.ID
}
func (b *Broker) snapshot(p Principal) (any, error) {
	if er := p.Require("system:read"); er != nil {
		return nil, er
	}
	hosts, e := b.Store.list("host")
	if e != nil {
		return nil, e
	}
	agents, e := b.Store.list("agent")
	if e != nil {
		return nil, e
	}
	sessions, e := b.Store.list("session")
	if e != nil {
		return nil, e
	}
	tasks, e := b.Store.tasks()
	if e != nil {
		return nil, e
	}
	for i := range tasks {
		tasks[i].ClaimID = ""
	}
	events, e := b.Store.events(0, 1000)
	if e != nil {
		return nil, e
	}
	var mem runtime.MemStats
	runtime.ReadMemStats(&mem)
	resources := processResources()
	resources["pid"] = os.Getpid()
	resources["uptime_ms"] = now() - b.Started
	resources["go_allocated_bytes"] = mem.Alloc
	resources["goroutines"] = runtime.NumGoroutine()
	resources["gpu_usage"] = nil
	return Object{"version": Version, "broker": resources, "hosts": hosts, "agents": agents, "sessions": sessions, "tasks": tasks, "events": events, "integrity_verified": b.Store.verify() == nil}, nil
}
func (b *Broker) Supervise(ctx context.Context) {
	ticker := time.NewTicker(time.Second)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			b.mu.Lock()
			tasks, e := b.Store.tasks()
			if e == nil {
				for _, t := range tasks {
					if terminal(t.State) || t.State == "outcome_unknown" {
						continue
					}
					changed := false
					if (t.State == "running" || t.State == "cancel_requested") && t.LeaseUntil < now() {
						t.State = "outcome_unknown"
						changed = true
					} else if t.Deadline < now() {
						if t.State == "queued" {
							t.State = "cancelled"
						} else {
							t.State = "cancel_requested"
						}
						changed = true
					}
					if changed {
						_ = b.Store.saveTask(t, "task.supervision", "broker")
					}
				}
			}
			b.mu.Unlock()
		}
	}
}
