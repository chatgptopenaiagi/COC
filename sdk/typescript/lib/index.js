import { Validator } from '@cfworker/json-schema';
import schema from './schema.js';
export const VERSION = 'COC-PROTOCOL/1';
const validator = new Validator(schema, '7');
const contracts = { validate: (schema, value) => new Validator(schema, '7').validate(value).valid };
export function validate(message) { return validator.validate(message).valid; }
export function envelope(agent, method, payload = {}) { return { jsonrpc: '2.0', id: crypto.randomUUID(), method, params: { protocol_version: VERSION, message_id: crypto.randomUUID(), agent_id: agent, parent_agent_id: null, child_agent_id: null, host_id: typeof payload.host_id === 'string' ? payload.host_id : null, session_id: null, task_id: typeof payload.task_id === 'string' ? payload.task_id : null, correlation_id: null, timestamp: new Date().toISOString(), scope: [], payload, status: 'request', error: null, integrity: {} } }; }
export class COCError extends Error {
    code;
    constructor(code, message) {
        super(message);
        this.code = code;
        this.name = 'COCError';
    }
}
export class Client {
    url;
    token;
    agent;
    constructor(url, token, agent) {
        this.url = url;
        this.token = token;
        this.agent = agent;
        const u = new URL(url);
        if (u.username || u.password || u.search || u.hash)
            throw new Error('invalid broker URL');
        if (u.protocol !== 'https:' && !(u.protocol === 'http:' && ['127.0.0.1', 'localhost', '[::1]'].includes(u.hostname)))
            throw new Error('remote transport requires HTTPS');
    }
    async call(method, payload = {}, signal) { const message = envelope(this.agent, method, payload); if (!validate(message))
        throw new COCError('SCHEMA_INVALID', 'invalid COC envelope'); const response = await fetch(this.url + '/rpc', { method: 'POST', redirect: 'error', headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + this.token }, body: JSON.stringify(message), signal: signal ?? AbortSignal.timeout(15000) }); if (!response.ok)
        throw new COCError('HTTP_' + response.status, 'broker request rejected'); const result = await response.json(); if (result.error)
        throw new COCError(result.error.data?.type ?? String(result.error.code), result.error.message); if (result.id !== message.id)
        throw new COCError('CORRELATION', 'response id mismatch'); return result.result.payload.data; }
    submit(host, tool, args, parentId = '', key = crypto.randomUUID()) { return this.call(parentId ? 'COC.DELEGATE' : 'COC.TOOL_REQUEST', { host_id: host, tool, arguments: args, parent_id: parentId, idempotency_key: key }); }
    async wait(id, timeout = 120000) { const end = Date.now() + timeout; while (Date.now() < end) {
        const t = await this.call('COC.RECOVER', { task_id: id });
        if (['succeeded', 'failed', 'cancelled', 'outcome_unknown'].includes(t.state))
            return t;
        await delay(100);
    } throw new Error('wait timed out; execution outcome remains unresolved'); }
    async *events(after = 0, signal) { let retry = 250; while (!signal?.aborted) {
        try {
            const response = await fetch(`${this.url}/events?after=${after}`, { redirect: 'error', headers: { Authorization: 'Bearer ' + this.token }, signal });
            if (response.status === 401 || response.status === 403)
                throw new COCError('UNAUTHORIZED', 'event access rejected');
            if (!response.ok || !response.body)
                throw new Error('event stream unavailable');
            let buffer = '';
            for await (const chunk of streamChunks(response.body)) {
                buffer += chunk;
                let index;
                while ((index = buffer.indexOf('\n\n')) >= 0) {
                    const frame = buffer.slice(0, index);
                    buffer = buffer.slice(index + 2);
                    const data = frame.split('\n').find(l => l.startsWith('data: '));
                    if (data) {
                        const event = JSON.parse(data.slice(6));
                        if (event.sequence > after) {
                            after = event.sequence;
                            retry = 250;
                            yield event;
                        }
                    }
                }
            }
        }
        catch (error) {
            if (signal?.aborted)
                return;
            if (error instanceof COCError)
                throw error;
        }
        await delay(retry, signal);
        retry = Math.min(retry * 2, 5000);
    } }
    discover_capabilities() { return this.call('COC.CAPABILITIES'); }
    get_task_status(task_id) { return this.call('COC.RECOVER', { task_id }); }
    cancel_task(task_id) { return this.call('COC.CANCEL', { task_id }); }
    detach_agent(host_id) { return this.call('COC.DETACH', { host_id }); }
}
async function* streamChunks(body) { const reader = body.getReader(); const decoder = new TextDecoder(); try {
    while (true) {
        const r = await reader.read();
        if (r.done)
            return;
        yield decoder.decode(r.value, { stream: true });
    }
}
finally {
    reader.releaseLock();
} }
function delay(ms, signal) { return new Promise(resolve => { if (signal?.aborted) {
    resolve();
    return;
} const timer = setTimeout(done, ms); function done() { signal?.removeEventListener('abort', done); clearTimeout(timer); resolve(); } signal?.addEventListener('abort', done, { once: true }); }); }
export class HostAdapter {
    client;
    id;
    name;
    tools;
    language;
    stopController = new AbortController();
    active = new Map();
    constructor(client, id, name, tools, language = 'typescript') {
        this.client = client;
        this.id = id;
        this.name = name;
        this.tools = tools;
        this.language = language;
    }
    discover_capabilities() { return [...this.tools.values()].map(t => t.capability); }
    read_application_state() { return { host_id: this.id, active_tasks: [...this.active.keys()] }; }
    list_available_tools() { return [...this.tools.keys()]; }
    async execute_authorized_tool(task, signal) { const tool = this.tools.get(task.tool); if (!tool)
        throw new Error('tool not registered'); if (!contracts.validate(tool.capability.input_schema, task.arguments))
        throw new Error('invalid input'); const result = await tool.execute(task.arguments, signal, task); if (!contracts.validate(tool.capability.output_schema, result))
        throw new Error('invalid output'); return result; }
    subscribe_to_events(after = 0) { return this.client.events(after, this.stopController.signal); }
    get_task_status(id) { return this.client.get_task_status(id); }
    cancel_task(id) { this.active.get(id)?.abort(); }
    report_error(id) { return this.client.call('COC.ERROR', { task_id: id, category: 'host_execution', message: 'host execution failed' }); }
    request_operator_assistance(id, reason) { return this.client.call('COC.EVENT', { task_id: id, kind: 'operator_assistance', reason }); }
    async detach_agent() { this.stopController.abort(); for (const a of this.active.values())
        a.abort(); return this.client.detach_agent(this.id); }
    async run(once = false) { await this.client.call('COC.REGISTER', { kind: 'host', id: this.id, name: this.name, language: this.language, capabilities: this.discover_capabilities() }); let heartbeatBusy = false; const timer = setInterval(async () => { if (heartbeatBusy)
        return; heartbeatBusy = true; try {
        const r = await this.client.call('COC.HEARTBEAT', { host_id: this.id });
        r.cancel_task_ids.forEach(id => this.cancel_task(id));
    }
    catch {
        for (const c of this.active.values())
            c.abort();
    }
    finally {
        heartbeatBusy = false;
    } }, 400); try {
        while (!this.stopController.signal.aborted) {
            const r = await this.client.call('COC.RECOVER', { action: 'claim', host_id: this.id });
            if (!r.task) {
                await delay(100, this.stopController.signal);
                continue;
            }
            const task = r.task;
            const cancel = new AbortController();
            this.active.set(task.id, cancel);
            let result = null;
            let error = null;
            let outcome = 'succeeded';
            try {
                result = await this.execute_authorized_tool(task, cancel.signal);
            }
            catch {
                outcome = cancel.signal.aborted ? 'cancelled' : 'failed';
                error = { message: 'host execution failed' };
                await this.report_error(task.id);
            }
            await this.client.call('COC.TOOL_RESULT', { task_id: task.id, claim_id: task.claim_id ?? '', outcome, result, error });
            this.active.delete(task.id);
            if (once)
                break;
        }
    }
    finally {
        clearInterval(timer);
    } }
}
