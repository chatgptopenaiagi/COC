package broker

import (
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"strings"
	"time"

	"github.com/santhosh-tekuri/jsonschema/v5"
)

const Version = "COC-PROTOCOL/1"

var Methods = []string{"COC.HELLO", "COC.DISCOVER", "COC.AUTHENTICATE", "COC.CAPABILITIES", "COC.REGISTER", "COC.ATTACH", "COC.DELEGATE", "COC.MESSAGE", "COC.TOOL_REQUEST", "COC.TOOL_RESULT", "COC.EVENT", "COC.HEARTBEAT", "COC.ERROR", "COC.CANCEL", "COC.RECOVER", "COC.DETACH", "COC.SHUTDOWN"}

type Object = map[string]any
type Envelope struct {
	ProtocolVersion string   `json:"protocol_version"`
	MessageID       string   `json:"message_id"`
	AgentID         string   `json:"agent_id"`
	ParentAgentID   *string  `json:"parent_agent_id"`
	ChildAgentID    *string  `json:"child_agent_id"`
	HostID          *string  `json:"host_id"`
	SessionID       *string  `json:"session_id"`
	TaskID          *string  `json:"task_id"`
	CorrelationID   *string  `json:"correlation_id"`
	Timestamp       string   `json:"timestamp"`
	Scope           []string `json:"scope"`
	Payload         Object   `json:"payload"`
	Status          string   `json:"status"`
	Error           any      `json:"error"`
	Integrity       Object   `json:"integrity"`
}
type Request struct {
	JSONRPC string   `json:"jsonrpc"`
	ID      string   `json:"id"`
	Method  string   `json:"method"`
	Params  Envelope `json:"params"`
}
type Fault struct {
	Code    int    `json:"code"`
	Message string `json:"message"`
	Data    Object `json:"data,omitempty"`
}

func (f *Fault) Error() string                { return f.Message }
func fault(code string, message string) error { return &Fault{-32000, message, Object{"type": code}} }

type Principal struct {
	ID         string   `json:"id"`
	Scopes     []string `json:"scopes"`
	Expires    int64    `json:"expires"`
	Hash       string   `json:"-"`
	ParentHash string   `json:"-"`
}

func (p Principal) Allows(scope string) bool {
	for _, s := range p.Scopes {
		if s == "*" || s == scope {
			return true
		}
	}
	return false
}
func (p Principal) Require(scope string) error {
	if !p.Allows(scope) {
		return fault("SCOPE_DENIED", "required scope: "+scope)
	}
	return nil
}

type Capability struct {
	Name         string `json:"name"`
	Description  string `json:"description"`
	InputSchema  Object `json:"input_schema"`
	OutputSchema Object `json:"output_schema"`
	Idempotent   bool   `json:"idempotent"`
	Cancellable  bool   `json:"cancellable"`
	Version      string `json:"version"`
}
type Host struct {
	ID           string       `json:"id"`
	Owner        string       `json:"owner"`
	Name         string       `json:"name"`
	Language     string       `json:"language"`
	Capabilities []Capability `json:"capabilities"`
	LastSeen     int64        `json:"last_seen"`
	Attached     bool         `json:"attached"`
}
type Budget struct {
	MaxDepth       int `json:"max_depth"`
	MaxTasks       int `json:"max_tasks"`
	MaxConcurrent  int `json:"max_concurrent"`
	TokenLimit     int `json:"token_limit"`
	ReservedTokens int `json:"reserved_tokens"`
	UsedTokens     int `json:"used_tokens"`
}
type Task struct {
	ID             string   `json:"id"`
	ParentID       string   `json:"parent_id,omitempty"`
	RootID         string   `json:"root_id"`
	Owner          string   `json:"owner"`
	HostID         string   `json:"host_id"`
	Tool           string   `json:"tool"`
	Arguments      Object   `json:"arguments"`
	Result         any      `json:"result,omitempty"`
	Error          any      `json:"error,omitempty"`
	State          string   `json:"state"`
	Depth          int      `json:"depth"`
	Budget         Budget   `json:"budget"`
	Scopes         []string `json:"scopes"`
	Created        int64    `json:"created"`
	Updated        int64    `json:"updated"`
	Deadline       int64    `json:"deadline"`
	LeaseUntil     int64    `json:"lease_until"`
	ClaimID        string   `json:"claim_id,omitempty"`
	Attempt        int      `json:"attempt"`
	IdempotencyKey string   `json:"idempotency_key"`
	Fingerprint    string   `json:"fingerprint"`
	Receipt        *Receipt `json:"receipt,omitempty"`
}
type Receipt struct {
	ID           string `json:"id"`
	TaskID       string `json:"task_id"`
	Executor     string `json:"executor"`
	HostID       string `json:"host_id"`
	Tool         string `json:"tool"`
	Attempt      int    `json:"attempt"`
	ClaimID      string `json:"claim_id"`
	InputDigest  string `json:"input_digest"`
	OutputDigest string `json:"output_digest"`
	Outcome      string `json:"outcome"`
	At           int64  `json:"at"`
	Verification string `json:"verification"`
}
type Event struct {
	Sequence     int64  `json:"sequence"`
	Kind         string `json:"kind"`
	TaskID       string `json:"task_id,omitempty"`
	Principal    string `json:"principal"`
	Data         Object `json:"data"`
	At           int64  `json:"at"`
	PreviousHash string `json:"previous_hash"`
	Hash         string `json:"hash"`
}

func now() int64 { return time.Now().UnixMilli() }
func ID() string {
	var b [16]byte
	if _, err := rand.Read(b[:]); err != nil {
		panic(err)
	}
	return hex.EncodeToString(b[:])
}
func digest(v any) string {
	data, _ := json.Marshal(v)
	h := sha256.Sum256(data)
	return hex.EncodeToString(h[:])
}
func tokenHash(v string) string     { h := sha256.Sum256([]byte(v)); return hex.EncodeToString(h[:]) }
func str(p Object, k string) string { s, _ := p[k].(string); return s }
func obj(p Object, k string) Object {
	o, _ := p[k].(map[string]any)
	if o == nil {
		return Object{}
	}
	return o
}
func number(p Object, k string, d int) int {
	if v, ok := p[k].(float64); ok {
		return int(v)
	}
	return d
}
func stringsOf(v any) []string {
	a := []string{}
	if x, ok := v.([]any); ok {
		for _, y := range x {
			if s, ok := y.(string); ok {
				a = append(a, s)
			}
		}
	}
	return a
}
func decode(v any, out any) error {
	b, e := json.Marshal(v)
	if e != nil {
		return e
	}
	return json.Unmarshal(b, out)
}
func validateSchema(schema Object, value any) error {
	s, e := schemaCompiled(schema)
	if e != nil {
		return e
	}
	return s.Validate(value)
}
func schemaCompiled(schema Object) (*jsonschema.Schema, error) {
	c := jsonschema.NewCompiler()
	c.Draft = jsonschema.Draft7
	c.LoadURL = func(string) (io.ReadCloser, error) { return nil, errors.New("external schema references are disabled") }
	data, _ := json.Marshal(schema)
	if e := c.AddResource("coc.json", strings.NewReader(string(data))); e != nil {
		return nil, e
	}
	return c.Compile("coc.json")
}
func compileSchema(schema Object) error { _, e := schemaCompiled(schema); return e }
func NewEnvelope(agent string, p Object) Envelope {
	return Envelope{ProtocolVersion: Version, MessageID: ID(), AgentID: agent, Timestamp: time.Now().UTC().Format(time.RFC3339Nano), Scope: []string{}, Payload: p, Status: "request", Integrity: Object{}}
}
func terminal(s string) bool { return s == "succeeded" || s == "failed" || s == "cancelled" }
func (t Task) scope() string { return fmt.Sprintf("tool:%s:%s", t.HostID, t.Tool) }
