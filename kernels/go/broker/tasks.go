package broker

import (
	"database/sql"
)

func (b *Broker) submit(p Principal, v Object) (any, error) {
	host, tool := str(v, "host_id"), str(v, "tool")
	scope := "tool:" + host + ":" + tool
	if e := p.Require(scope); e != nil {
		return nil, e
	}
	var h Host
	if e := b.Store.get("host", host, &h); e != nil {
		return nil, fault("NOT_FOUND", "host not registered")
	}
	var cap *Capability
	for i := range h.Capabilities {
		if h.Capabilities[i].Name == tool {
			cap = &h.Capabilities[i]
		}
	}
	if cap == nil {
		return nil, fault("NOT_FOUND", "tool not registered")
	}
	args := obj(v, "arguments")
	if e := validateSchema(cap.InputSchema, args); e != nil {
		return nil, fault("SCHEMA_INVALID", e.Error())
	}
	key := str(v, "idempotency_key")
	if key == "" || len(key) > 128 {
		return nil, fault("INVALID_ARGUMENT", "idempotency_key required, maximum 128 characters")
	}
	parentID := str(v, "parent_id")
	fp := digest(Object{"host": host, "tool": tool, "arguments": args, "parent": parentID})
	var oldID string
	e := b.Store.DB.QueryRow("SELECT id FROM tasks WHERE owner=? AND idem=?", p.ID, key).Scan(&oldID)
	if e == nil {
		old, er := b.Store.task(oldID)
		if er != nil {
			return nil, er
		}
		if old.Fingerprint != fp {
			return nil, fault("CONFLICT", "idempotency key reused with different operation")
		}
		return old, nil
	}
	if e != sql.ErrNoRows {
		return nil, e
	}
	budget := Budget{MaxDepth: 2, MaxTasks: 16, MaxConcurrent: 4, TokenLimit: 8192}
	if raw := obj(v, "budget"); len(raw) > 0 {
		budget.MaxDepth = number(raw, "max_depth", 2)
		budget.MaxTasks = number(raw, "max_tasks", 16)
		budget.MaxConcurrent = number(raw, "max_concurrent", 4)
		budget.TokenLimit = number(raw, "token_limit", 8192)
		budget.ReservedTokens = number(raw, "reserved_tokens", 0)
	}
	if budget.MaxDepth < 0 || budget.MaxDepth > 64 || budget.MaxTasks < 1 || budget.MaxTasks > 10000 || budget.MaxConcurrent < 1 || budget.MaxConcurrent > 128 || budget.TokenLimit < 0 || budget.TokenLimit > 1000000 || budget.ReservedTokens < 0 {
		return nil, fault("INVALID_ARGUMENT", "budget outside configured admission limits")
	}
	if budget.ReservedTokens > budget.TokenLimit {
		return nil, fault("BUDGET_EXCEEDED", "reservation exceeds task token limit")
	}
	ttl := number(v, "timeout_seconds", 120)
	if ttl < 1 || ttl > 86400 {
		return nil, fault("INVALID_ARGUMENT", "timeout must be 1..86400 seconds")
	}
	t := Task{ID: ID(), Owner: p.ID, HostID: host, Tool: tool, Arguments: args, State: "queued", Budget: budget, Scopes: p.Scopes, Created: now(), Updated: now(), Deadline: now() + int64(ttl)*1000, IdempotencyKey: key, Fingerprint: fp}
	t.RootID = t.ID
	tasks, e := b.Store.tasks()
	if e != nil {
		return nil, e
	}
	if parentID != "" {
		if e = p.Require("task:delegate"); e != nil {
			return nil, e
		}
		parent, er := b.Store.task(parentID)
		if er != nil || !b.canRead(p, parent) {
			return nil, fault("SCOPE_DENIED", "parent is not visible")
		}
		if terminal(parent.State) || parent.State == "cancel_requested" || parent.State == "outcome_unknown" {
			return nil, fault("CONFLICT", "parent cannot accept new work")
		}
		root, er := b.Store.task(parent.RootID)
		if er != nil {
			return nil, er
		}
		t.ParentID = parentID
		t.RootID = parent.RootID
		t.Depth = parent.Depth + 1
		t.Budget = root.Budget
		t.Budget.ReservedTokens = budget.ReservedTokens
		t.Budget.UsedTokens = 0
		if t.Depth > root.Budget.MaxDepth {
			return nil, fault("DEPTH_EXCEEDED", "delegation depth exceeded")
		}
		if t.Deadline > parent.Deadline {
			t.Deadline = parent.Deadline
		}
		authority := Principal{Scopes: parent.Scopes}
		if !authority.Allows(scope) {
			return nil, fault("SCOPE_DENIED", "operation exceeds parent authority")
		}
		attenuated := []string{}
		for _, s := range p.Scopes {
			if authority.Allows(s) {
				attenuated = append(attenuated, s)
			}
		}
		t.Scopes = attenuated
		count, reserved := 0, 0
		for _, other := range tasks {
			if other.RootID == t.RootID {
				count++
				reserved += other.Budget.ReservedTokens
			}
		}
		if count >= root.Budget.MaxTasks || reserved+t.Budget.ReservedTokens > root.Budget.TokenLimit {
			return nil, fault("BUDGET_EXCEEDED", "root task or token reservation limit exceeded")
		}
		seen := map[string]bool{}
		for parentID != "" {
			if seen[parentID] {
				return nil, fault("CYCLE_DETECTED", "cyclic ancestry")
			}
			seen[parentID] = true
			a, er := b.Store.task(parentID)
			if er != nil {
				return nil, er
			}
			if a.HostID == host && a.Tool == tool && digest(a.Arguments) == digest(args) {
				return nil, fault("CYCLE_DETECTED", "equivalent operation in ancestry")
			}
			parentID = a.ParentID
		}
	}
	for _, other := range tasks {
		if other.Owner == p.ID && other.Fingerprint == fp && !terminal(other.State) {
			return nil, fault("DUPLICATE_TASK", "equivalent task is already active: "+other.ID)
		}
	}
	if e = b.Store.saveTask(t, "task.accepted", p.ID); e != nil {
		return nil, e
	}
	return t, nil
}
func (b *Broker) claim(p Principal, host string) (any, error) {
	h, e := b.ownedHost(p, host)
	if e != nil {
		return nil, e
	}
	h.LastSeen = now()
	h.Attached = true
	if e = b.Store.put("host", host, h); e != nil {
		return nil, e
	}
	tasks, e := b.Store.tasks()
	if e != nil {
		return nil, e
	}
	for _, t := range tasks {
		if t.HostID != host || t.State != "queued" {
			continue
		}
		if t.Deadline <= now() {
			t.State = "cancelled"
			if e = b.Store.saveTask(t, "task.expired", p.ID); e != nil {
				return nil, e
			}
			continue
		}
		root, e := b.Store.task(t.RootID)
		if e != nil {
			return nil, e
		}
		active := 0
		for _, a := range tasks {
			if a.RootID == t.RootID && (a.State == "running" || a.State == "cancel_requested") {
				active++
			}
		}
		if active >= root.Budget.MaxConcurrent {
			continue
		}
		t.State = "running"
		t.ClaimID = ID()
		t.LeaseUntil = now() + 10000
		t.Attempt++
		if e = b.Store.saveTask(t, "task.claimed", p.ID); e != nil {
			return nil, e
		}
		return Object{"task": t}, nil
	}
	return Object{"task": nil}, nil
}
func (b *Broker) finish(p Principal, v Object) (any, error) {
	t, e := b.Store.task(str(v, "task_id"))
	if e != nil {
		return nil, fault("NOT_FOUND", "task not found")
	}
	h, e := b.ownedHost(p, t.HostID)
	if e != nil {
		return nil, e
	}
	claim := str(v, "claim_id")
	if claim == "" || claim != t.ClaimID {
		return nil, fault("STALE_CLAIM", "claim does not match current attempt")
	}
	outcome := str(v, "outcome")
	if outcome != "succeeded" && outcome != "failed" && outcome != "cancelled" {
		return nil, fault("INVALID_ARGUMENT", "invalid result outcome")
	}
	if terminal(t.State) {
		if t.Receipt != nil && t.Receipt.OutputDigest == digest(v["result"]) && t.Receipt.Outcome == outcome {
			return t, nil
		}
		return nil, fault("CONFLICT", "terminal result differs")
	}
	if outcome == "succeeded" {
		for _, c := range h.Capabilities {
			if c.Name == t.Tool {
				if e = validateSchema(c.OutputSchema, v["result"]); e != nil {
					return nil, fault("SCHEMA_INVALID", e.Error())
				}
			}
		}
	}
	used := number(v, "usage_tokens", 0)
	if used < 0 {
		return nil, fault("INVALID_ARGUMENT", "negative usage")
	}
	if used > t.Budget.ReservedTokens {
		outcome = "failed"
		v["error"] = Object{"type": "BUDGET_EXCEEDED", "message": "actual provider usage exceeded reservation; committed effects remain recorded"}
	}
	t.Budget.UsedTokens = used
	t.State = outcome
	t.Result = v["result"]
	t.Error = v["error"]
	t.LeaseUntil = 0
	t.Receipt = &Receipt{ID: ID(), TaskID: t.ID, Executor: p.ID, HostID: t.HostID, Tool: t.Tool, Attempt: t.Attempt, ClaimID: claim, InputDigest: digest(t.Arguments), OutputDigest: digest(t.Result), Outcome: outcome, At: now(), Verification: "executor-reported; output schema validated; semantic verification is separate"}
	if e = b.Store.saveTask(t, "task.result", p.ID); e != nil {
		return nil, e
	}
	return t, nil
}
func (b *Broker) retry(p Principal, id string) (any, error) {
	t, e := b.Store.task(id)
	if e != nil {
		return nil, fault("NOT_FOUND", "task not found")
	}
	if t.Owner != p.ID && !p.Allows("*") {
		return nil, fault("SCOPE_DENIED", "only owner can retry")
	}
	if t.State != "outcome_unknown" {
		return nil, fault("CONFLICT", "only uncertain tasks can be reconciled for retry")
	}
	var h Host
	if e = b.Store.get("host", t.HostID, &h); e != nil {
		return nil, e
	}
	safe := false
	for _, c := range h.Capabilities {
		if c.Name == t.Tool {
			safe = c.Idempotent
		}
	}
	if !safe {
		return nil, fault("OUTCOME_UNKNOWN", "non-idempotent operation requires host reconciliation")
	}
	if t.Attempt >= 3 {
		return nil, fault("BUDGET_EXCEEDED", "retry limit reached")
	}
	if t.Deadline <= now() {
		return nil, fault("EXPIRED", "task deadline passed")
	}
	t.State = "queued"
	t.ClaimID = ""
	t.LeaseUntil = 0
	return t, b.Store.saveTask(t, "task.retry", p.ID)
}
func (b *Broker) cancel(p Principal, id string) (any, error) {
	target, e := b.Store.task(id)
	if e != nil {
		return nil, fault("NOT_FOUND", "task not found")
	}
	if target.Owner != p.ID && !p.Allows("*") {
		return nil, fault("SCOPE_DENIED", "only task owner can cancel")
	}
	tasks, e := b.Store.tasks()
	if e != nil {
		return nil, e
	}
	owned := map[string]bool{id: true}
	for changed := true; changed; {
		changed = false
		for _, t := range tasks {
			if owned[t.ParentID] && !owned[t.ID] {
				owned[t.ID] = true
				changed = true
			}
		}
	}
	changedIDs := []string{}
	for _, t := range tasks {
		if !owned[t.ID] || terminal(t.State) {
			continue
		}
		if t.State == "queued" {
			t.State = "cancelled"
		} else if t.State != "outcome_unknown" {
			t.State = "cancel_requested"
		}
		if e = b.Store.saveTask(t, "task.cancel_requested", p.ID); e != nil {
			return nil, e
		}
		changedIDs = append(changedIDs, t.ID)
	}
	return Object{"accepted": true, "task_ids": changedIDs, "meaning": "cancellation requested; committed effects are not rolled back"}, nil
}
