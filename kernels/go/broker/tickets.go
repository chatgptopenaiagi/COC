package broker

import (
	"encoding/json"
	"io"
	"net/http"
)

// One-use browser bootstrap codes are distinct from long-lived credentials.
func (b *Broker) panelTicket(p Principal) (any, error) {
	if err := p.Require("auth:issue"); err != nil {
		return nil, err
	}
	ticket := ID() + ID()
	record := Object{"parent_hash": p.Hash, "expires": now() + 60000}
	if err := b.Store.put("panel-ticket", tokenHash(ticket), record); err != nil {
		return nil, err
	}
	return Object{"ticket": ticket, "expires_in_seconds": 60, "single_use": true}, nil
}
func (b *Broker) exchangePanelTicket(w http.ResponseWriter, r *http.Request) {
	if r.Method != "POST" || (r.Header.Get("Origin") != "http://"+r.Host && r.Header.Get("Origin") != "https://"+r.Host) {
		http.Error(w, "same-origin POST required", 403)
		return
	}
	body, err := io.ReadAll(http.MaxBytesReader(w, r.Body, 4096))
	if err != nil {
		http.Error(w, "invalid request", 400)
		return
	}
	var request struct {
		Ticket string `json:"ticket"`
	}
	if json.Unmarshal(body, &request) != nil {
		http.Error(w, "invalid request", 400)
		return
	}
	b.mu.Lock()
	defer b.mu.Unlock()
	var record Object
	hash := tokenHash(request.Ticket)
	if b.Store.get("panel-ticket", hash, &record) != nil || int64(number(record, "expires", 0)) <= now() {
		http.Error(w, "invalid or expired ticket", 401)
		return
	}
	parent, err := b.authenticateHash(str(record, "parent_hash"))
	if err != nil {
		http.Error(w, "grant revoked", 401)
		return
	}
	token := ID() + ID()
	expires := now() + 3600000
	if expires > parent.Expires {
		expires = parent.Expires
	}
	scopes, _ := json.Marshal(parent.Scopes)
	tx, err := b.Store.DB.Begin()
	if err != nil {
		http.Error(w, "storage unavailable", 503)
		return
	}
	defer tx.Rollback()
	if _, err = tx.Exec("DELETE FROM objects WHERE kind='panel-ticket' AND id=?", hash); err != nil {
		http.Error(w, "storage unavailable", 503)
		return
	}
	if _, err = tx.Exec("INSERT INTO tokens(hash,principal,scopes,expires,parent_hash) VALUES(?,?,?,?,?)", tokenHash(token), parent.ID, string(scopes), expires, parent.Hash); err != nil {
		http.Error(w, "storage unavailable", 503)
		return
	}
	if err = appendEvent(tx, "panel.connected", "", parent.ID, Object{"expires": expires}); err != nil {
		http.Error(w, "storage unavailable", 503)
		return
	}
	if tx.Commit() != nil {
		http.Error(w, "storage unavailable", 503)
		return
	}
	writeJSON(w, Object{"token": token, "agent": parent.ID, "expires": expires})
}
