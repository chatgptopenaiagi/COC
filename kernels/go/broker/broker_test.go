package broker

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
	"time"
)

func setup(t *testing.T) (*Broker, Principal) {
	t.Helper()
	raw, e := os.ReadFile("../../../specifications/schemas/message.schema.json")
	if e != nil {
		t.Fatal(e)
	}
	schema := Object{}
	json.Unmarshal(raw, &schema)
	b, e := New(filepath.Join(t.TempDir(), "test.sqlite"), "012345678901234567890123456789012345", schema)
	if e != nil {
		t.Fatal(e)
	}
	t.Cleanup(func() { b.Store.DB.Close() })
	p, e := b.Authenticate("012345678901234567890123456789012345")
	if e != nil {
		t.Fatal(e)
	}
	return b, p
}
func call(t *testing.T, b *Broker, p Principal, method string, v Object) any {
	t.Helper()
	result, e := b.Dispatch(p, Request{Method: method, Params: NewEnvelope(p.ID, v)})
	if e != nil {
		t.Fatal(e)
	}
	return result
}
func register(t *testing.T, b *Broker, p Principal) {
	t.Helper()
	call(t, b, p, "COC.REGISTER", Object{"id": "test", "name": "test", "capabilities": []Capability{{Name: "sum", InputSchema: Object{"type": "object"}, OutputSchema: Object{"type": "object"}, Idempotent: true}}})
}
func submit(t *testing.T, b *Broker, p Principal, key string) Task {
	return call(t, b, p, "COC.TOOL_REQUEST", Object{"host_id": "test", "tool": "sum", "arguments": Object{"x": 1}, "idempotency_key": key}).(Task)
}
func TestIdempotentAdmissionAndConflict(t *testing.T) {
	b, p := setup(t)
	register(t, b, p)
	a := submit(t, b, p, "one")
	again := submit(t, b, p, "one")
	if a.ID != again.ID {
		t.Fatal("idempotency lost")
	}
	_, e := b.Dispatch(p, Request{Method: "COC.TOOL_REQUEST", Params: NewEnvelope(p.ID, Object{"host_id": "test", "tool": "sum", "arguments": Object{"x": 2}, "idempotency_key": "one"})})
	if e == nil {
		t.Fatal("argument mismatch accepted")
	}
	if e = b.Store.verify(); e != nil {
		t.Fatal(e)
	}
}
func TestScopeAttenuationAndIdentity(t *testing.T) {
	b, p := setup(t)
	register(t, b, p)
	grant := call(t, b, p, "COC.AUTHENTICATE", Object{"principal": "reader", "scopes": []any{"discover"}}).(Object)
	reader, e := b.Authenticate(grant["token"].(string))
	if e != nil {
		t.Fatal(e)
	}
	_, e = b.Dispatch(reader, Request{Method: "COC.TOOL_REQUEST", Params: NewEnvelope("reader", Object{"host_id": "test", "tool": "sum"})})
	if e == nil {
		t.Fatal("unauthorized tool call")
	}
	_, e = b.Dispatch(reader, Request{Method: "COC.HELLO", Params: NewEnvelope("operator", Object{})})
	if e == nil {
		t.Fatal("forged identity accepted")
	}
}
func TestResultClaimAndReceipt(t *testing.T) {
	b, p := setup(t)
	register(t, b, p)
	task := submit(t, b, p, "one")
	claimed := call(t, b, p, "COC.RECOVER", Object{"action": "claim", "host_id": "test"}).(Object)["task"].(Task)
	if claimed.ID != task.ID {
		t.Fatal("task identity changed")
	}
	data := Object{"task_id": task.ID, "claim_id": "incorrect", "outcome": "succeeded", "result": Object{"answer": 2}}
	_, e := b.Dispatch(p, Request{Method: "COC.TOOL_RESULT", Params: NewEnvelope(p.ID, data)})
	if e == nil {
		t.Fatal("stale claim accepted")
	}
	data["claim_id"] = claimed.ClaimID
	finished := call(t, b, p, "COC.TOOL_RESULT", data).(Task)
	if finished.Receipt == nil || finished.Receipt.InputDigest != digest(task.Arguments) {
		t.Fatal("invalid receipt")
	}
	call(t, b, p, "COC.TOOL_RESULT", data)
}
func TestRestartPreservesUncertainTask(t *testing.T) {
	b, p := setup(t)
	register(t, b, p)
	task := submit(t, b, p, "one")
	call(t, b, p, "COC.RECOVER", Object{"action": "claim", "host_id": "test"})
	var dbpath string
	if e := b.Store.DB.QueryRow("SELECT file FROM pragma_database_list WHERE name='main'").Scan(&dbpath); e != nil {
		t.Fatal(e)
	}
	b.Store.DB.Close()
	fresh, e := New(dbpath, "012345678901234567890123456789012345", b.Schema)
	if e != nil {
		t.Fatal(e)
	}
	defer fresh.Store.DB.Close()
	recovered, e := fresh.Store.task(task.ID)
	if e != nil || recovered.State != "outcome_unknown" {
		t.Fatalf("recovery: %v %#v", e, recovered)
	}
	retried := call(t, fresh, p, "COC.RECOVER", Object{"action": "retry", "task_id": task.ID}).(Task)
	if retried.ID != task.ID || retried.State != "queued" {
		t.Fatal("retry lost identity")
	}
}
func TestCancellationAndDepth(t *testing.T) {
	b, p := setup(t)
	register(t, b, p)
	root := submit(t, b, p, "root")
	child := call(t, b, p, "COC.DELEGATE", Object{"host_id": "test", "tool": "sum", "arguments": Object{"x": 2}, "idempotency_key": "child", "parent_id": root.ID}).(Task)
	grand := call(t, b, p, "COC.DELEGATE", Object{"host_id": "test", "tool": "sum", "arguments": Object{"x": 3}, "idempotency_key": "grand", "parent_id": child.ID}).(Task)
	_, e := b.Dispatch(p, Request{Method: "COC.DELEGATE", Params: NewEnvelope(p.ID, Object{"host_id": "test", "tool": "sum", "arguments": Object{"x": 4}, "idempotency_key": "too-deep", "parent_id": grand.ID})})
	if e == nil {
		t.Fatal("depth exceeded")
	}
	start := time.Now()
	call(t, b, p, "COC.CANCEL", Object{"task_id": root.ID})
	if time.Since(start) > 250*time.Millisecond {
		t.Fatal("local cancel exceeded target")
	}
	for _, id := range []string{root.ID, child.ID, grand.ID} {
		got, _ := b.Store.task(id)
		if got.State != "cancelled" {
			t.Fatal("descendant survived")
		}
	}
}
func TestRevocationAndTamperDetection(t *testing.T) {
	b, p := setup(t)
	grant := call(t, b, p, "COC.AUTHENTICATE", Object{"principal": "limited", "scopes": []any{"discover"}}).(Object)
	call(t, b, p, "COC.AUTHENTICATE", Object{"action": "revoke", "token_hash": grant["token_hash"]})
	if _, e := b.Authenticate(grant["token"].(string)); e == nil {
		t.Fatal("revoked token accepted")
	}
	b.Store.DB.Exec("UPDATE events SET principal='tampered' WHERE sequence=1")
	if e := b.Store.verify(); e == nil {
		t.Fatal("tampered ledger accepted")
	}
}
