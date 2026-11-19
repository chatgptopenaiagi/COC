package broker

import (
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"strconv"
	"strings"
	"time"
)

func (b *Broker) Handler(ui string) http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, Object{"status": "ready", "protocol": Version})
	})
	mux.HandleFunc("/rpc", b.rpc)
	mux.HandleFunc("/events", b.stream)
	mux.HandleFunc("/session/exchange", b.exchangePanelTicket)
	if ui != "" {
		mux.Handle("/", http.FileServer(http.Dir(ui)))
	}
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Content-Type-Options", "nosniff")
		w.Header().Set("Cache-Control", "no-store")
		w.Header().Set("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'")
		if origin := r.Header.Get("Origin"); origin != "" && origin != "http://"+r.Host && origin != "https://"+r.Host {
			http.Error(w, "origin denied", 403)
			return
		}
		mux.ServeHTTP(w, r)
	})
}
func writeJSON(w http.ResponseWriter, v any) {
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(v)
}
func (b *Broker) authRequest(r *http.Request) (Principal, error) {
	auth := r.Header.Get("Authorization")
	if !strings.HasPrefix(auth, "Bearer ") {
		return Principal{}, fault("UNAUTHORIZED", "bearer token required")
	}
	return b.Authenticate(strings.TrimPrefix(auth, "Bearer "))
}
func (b *Broker) rpc(w http.ResponseWriter, r *http.Request) {
	if r.Method != "POST" {
		http.Error(w, "POST required", 405)
		return
	}
	p, e := b.authRequest(r)
	if e != nil {
		w.WriteHeader(401)
		writeJSON(w, Object{"error": "unauthorized"})
		return
	}
	data, e := io.ReadAll(http.MaxBytesReader(w, r.Body, 1<<20))
	if e != nil {
		http.Error(w, "message too large", 413)
		return
	}
	var raw any
	if e = json.Unmarshal(data, &raw); e != nil {
		writeJSON(w, Object{"jsonrpc": "2.0", "id": nil, "error": Fault{-32700, "invalid JSON", nil}})
		return
	}
	var req Request
	if e = validateSchema(b.Schema, raw); e == nil {
		e = json.Unmarshal(data, &req)
	}
	if e != nil {
		writeJSON(w, Object{"jsonrpc": "2.0", "id": nil, "error": Fault{-32600, "invalid COC envelope", Object{"detail": e.Error()}}})
		return
	}
	at, e := time.Parse(time.RFC3339Nano, req.Params.Timestamp)
	if e != nil || time.Since(at) > 10*time.Minute || time.Until(at) > time.Minute {
		writeJSON(w, Object{"jsonrpc": "2.0", "id": req.ID, "error": Fault{-32602, "timestamp outside allowed window", nil}})
		return
	}
	if req.Params.Status != "request" {
		writeJSON(w, Object{"jsonrpc": "2.0", "id": req.ID, "error": Fault{-32602, "request status required", nil}})
		return
	}
	result, e := b.Dispatch(p, req)
	if e != nil {
		var f *Fault
		if !errors.As(e, &f) {
			f = &Fault{-32603, "internal operation failed", Object{"type": "INTERNAL"}}
		}
		writeJSON(w, Object{"jsonrpc": "2.0", "id": req.ID, "error": f})
		return
	}
	envelope := NewEnvelope("broker", Object{"data": result})
	envelope.Status = "ok"
	envelope.CorrelationID = &req.Params.MessageID
	envelope.TaskID = req.Params.TaskID
	envelope.Integrity = Object{"payload_sha256": digest(envelope.Payload)}
	writeJSON(w, Object{"jsonrpc": "2.0", "id": req.ID, "result": envelope})
}
func (b *Broker) stream(w http.ResponseWriter, r *http.Request) {
	p, e := b.authRequest(r)
	if e != nil {
		http.Error(w, "unauthorized", 401)
		return
	}
	if e = p.Require("system:read"); e != nil {
		http.Error(w, "scope denied", 403)
		return
	}
	after, _ := strconv.ParseInt(r.URL.Query().Get("after"), 10, 64)
	flusher, ok := w.(http.Flusher)
	if !ok {
		http.Error(w, "stream unavailable", 500)
		return
	}
	w.Header().Set("Content-Type", "text/event-stream")
	w.WriteHeader(200)
	flusher.Flush()
	ticker := time.NewTicker(200 * time.Millisecond)
	defer ticker.Stop()
	for {
		select {
		case <-r.Context().Done():
			return
		case <-b.Shutdown:
			return
		case <-ticker.C:
			if _, e = b.authRequest(r); e != nil {
				return
			}
			events, e := b.Store.events(after, 100)
			if e != nil {
				return
			}
			for _, v := range events {
				data, _ := json.Marshal(v)
				if _, e = fmt.Fprintf(w, "id: %d\ndata: %s\n\n", v.Sequence, data); e != nil {
					return
				}
				after = v.Sequence
			}
			flusher.Flush()
		}
	}
}
