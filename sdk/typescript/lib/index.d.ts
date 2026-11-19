export declare const VERSION: "COC-PROTOCOL/1";
export type Method = 'COC.HELLO' | 'COC.DISCOVER' | 'COC.AUTHENTICATE' | 'COC.CAPABILITIES' | 'COC.REGISTER' | 'COC.ATTACH' | 'COC.DELEGATE' | 'COC.MESSAGE' | 'COC.TOOL_REQUEST' | 'COC.TOOL_RESULT' | 'COC.EVENT' | 'COC.HEARTBEAT' | 'COC.ERROR' | 'COC.CANCEL' | 'COC.RECOVER' | 'COC.DETACH' | 'COC.SHUTDOWN';
export type Json = string | number | boolean | null | Json[] | {
    [key: string]: Json;
};
export type Payload = Record<string, Json>;
export interface Envelope {
    protocol_version: typeof VERSION;
    message_id: string;
    agent_id: string;
    parent_agent_id: string | null;
    child_agent_id: string | null;
    host_id: string | null;
    session_id: string | null;
    task_id: string | null;
    correlation_id: string | null;
    timestamp: string;
    scope: string[];
    payload: Payload;
    status: 'request' | 'ok' | 'error' | 'event';
    error: Payload | null;
    integrity: Payload;
}
export interface Request {
    jsonrpc: '2.0';
    id: string;
    method: Method;
    params: Envelope;
}
export interface Receipt {
    id: string;
    task_id: string;
    executor: string;
    host_id: string;
    tool: string;
    input_digest: string;
    output_digest: string;
    outcome: string;
    at: number;
    verification: string;
}
export interface Task {
    id: string;
    root_id: string;
    parent_id?: string;
    owner: string;
    host_id: string;
    tool: string;
    arguments: Payload;
    state: 'queued' | 'running' | 'succeeded' | 'failed' | 'cancel_requested' | 'cancelled' | 'outcome_unknown';
    result?: Json;
    error?: Json;
    claim_id?: string;
    receipt?: Receipt;
    created: number;
    updated: number;
    deadline: number;
}
export interface Capability {
    name: string;
    description: string;
    version: string;
    input_schema: Payload;
    output_schema: Payload;
    idempotent: boolean;
    cancellable: boolean;
}
export interface Host {
    id: string;
    owner: string;
    name: string;
    language: string;
    capabilities: Capability[];
    last_seen: number;
    attached: boolean;
}
export interface Event {
    sequence: number;
    kind: string;
    task_id?: string;
    principal: string;
    data: Payload;
    at: number;
    hash: string;
    previous_hash: string;
}
export interface Snapshot {
    version: string;
    broker: {
        pid: number;
        uptime_ms: number;
        go_allocated_bytes: number;
        goroutines: number;
        cpu_percent: number | null;
        gpu_usage: number | null;
        rss_bytes?: number | null;
        cpu_measurement?: string;
        owned_subprocess_count?: number;
    };
    hosts: Host[];
    agents: Payload[];
    sessions: Payload[];
    tasks: Task[];
    events: Event[];
    integrity_verified: boolean;
}
export declare function validate(message: unknown): message is Request;
export declare function envelope(agent: string, method: Method, payload?: Payload): Request;
export declare class COCError extends Error {
    code: string;
    constructor(code: string, message: string);
}
export declare class Client {
    readonly url: string;
    private readonly token;
    readonly agent: string;
    constructor(url: string, token: string, agent: string);
    call<T = Payload>(method: Method, payload?: Payload, signal?: AbortSignal): Promise<T>;
    submit(host: string, tool: string, args: Payload, parentId?: string, key?: `${string}-${string}-${string}-${string}-${string}`): Promise<Task>;
    wait(id: string, timeout?: number): Promise<Task>;
    events(after?: number, signal?: AbortSignal): AsyncGenerator<Event>;
    discover_capabilities(): Promise<{
        hosts: Host[];
    }>;
    get_task_status(task_id: string): Promise<Task>;
    cancel_task(task_id: string): Promise<Payload>;
    detach_agent(host_id: string): Promise<Payload>;
}
export type ToolHandler = (args: Payload, signal: AbortSignal, task: Task) => Promise<Json> | Json;
export declare class HostAdapter {
    client: Client;
    id: string;
    name: string;
    tools: Map<string, {
        capability: Capability;
        execute: ToolHandler;
    }>;
    language: string;
    private stopController;
    private active;
    constructor(client: Client, id: string, name: string, tools: Map<string, {
        capability: Capability;
        execute: ToolHandler;
    }>, language?: string);
    discover_capabilities(): Capability[];
    read_application_state(): {
        host_id: string;
        active_tasks: string[];
    };
    list_available_tools(): string[];
    execute_authorized_tool(task: Task, signal: AbortSignal): Promise<Json>;
    subscribe_to_events(after?: number): AsyncGenerator<Event, any, any>;
    get_task_status(id: string): Promise<Task>;
    cancel_task(id: string): void;
    report_error(id: string): Promise<Payload>;
    request_operator_assistance(id: string, reason: string): Promise<Payload>;
    detach_agent(): Promise<Payload>;
    run(once?: boolean): Promise<void>;
}
