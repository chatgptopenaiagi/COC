package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"net"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"strings"
	"syscall"
	"time"

	"github.com/chatgptopenaiagi/COC/kernels/go/broker"
)

func main() {
	if err := run(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
func run() error {
	listen := flag.String("listen", "127.0.0.1:7310", "listen address")
	db := flag.String("db", ".runtime/coc.sqlite3", "SQLite path")
	schemaPath := flag.String("schema", "specifications/schemas/message.schema.json", "protocol schema")
	ui := flag.String("ui", "applications/operator-panel", "static UI directory")
	ready := flag.String("ready", "", "write readiness metadata")
	cert := flag.String("tls-cert", "", "TLS certificate")
	key := flag.String("tls-key", "", "TLS private key")
	flag.Parse()
	host, _, e := net.SplitHostPort(*listen)
	if e != nil {
		return e
	}
	ip := net.ParseIP(host)
	if (ip == nil || !ip.IsLoopback()) && (*cert == "" || *key == "") {
		return fmt.Errorf("non-loopback binding requires TLS")
	}
	data, e := os.ReadFile(*schemaPath)
	if e != nil {
		return e
	}
	schema := broker.Object{}
	if e = json.Unmarshal(data, &schema); e != nil {
		return e
	}
	b, e := broker.New(*db, os.Getenv("COC_BOOTSTRAP_TOKEN"), schema)
	if e != nil {
		return e
	}
	defer b.Store.DB.Close()
	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer cancel()
	go b.Supervise(ctx)
	ln, e := net.Listen("tcp", *listen)
	if e != nil {
		return e
	}
	server := &http.Server{Handler: b.Handler(*ui), ReadHeaderTimeout: 5 * time.Second, IdleTimeout: 30 * time.Second, MaxHeaderBytes: 16384}
	scheme := "http"
	if *cert != "" {
		scheme = "https"
	}
	url := scheme + "://" + ln.Addr().String()
	if *ready != "" {
		if e = os.MkdirAll(filepath.Dir(*ready), 0700); e != nil {
			return e
		}
		info, _ := json.Marshal(broker.Object{"pid": os.Getpid(), "url": url, "database": *db, "protocol": broker.Version, "started_at": time.Now().UTC().Format(time.RFC3339)})
		if e = os.WriteFile(*ready, info, 0600); e != nil {
			return e
		}
	}
	fmt.Printf("COC ready at %s\n", url)
	go func() {
		select {
		case <-ctx.Done():
		case <-b.Shutdown:
		}
		deadline, done := context.WithTimeout(context.Background(), 5*time.Second)
		defer done()
		_ = server.Shutdown(deadline)
	}()
	if strings.HasPrefix(url, "https:") {
		e = server.ServeTLS(ln, *cert, *key)
	} else {
		e = server.Serve(ln)
	}
	if e == http.ErrServerClosed {
		return nil
	}
	return e
}
