declare const _default: {
    $schema: string;
    $id: string;
    title: string;
    type: string;
    required: string[];
    additionalProperties: boolean;
    properties: {
        jsonrpc: {
            const: string;
        };
        id: {
            type: string;
            minLength: number;
            maxLength: number;
        };
        method: {
            enum: string[];
        };
        params: {
            type: string;
            additionalProperties: boolean;
            required: string[];
            properties: {
                protocol_version: {
                    const: string;
                };
                message_id: {
                    type: string;
                    minLength: number;
                    maxLength: number;
                };
                agent_id: {
                    type: string;
                    minLength: number;
                    maxLength: number;
                };
                parent_agent_id: {
                    type: string[];
                };
                child_agent_id: {
                    type: string[];
                };
                host_id: {
                    type: string[];
                };
                session_id: {
                    type: string[];
                };
                task_id: {
                    type: string[];
                };
                correlation_id: {
                    type: string[];
                };
                timestamp: {
                    type: string;
                    format: string;
                };
                scope: {
                    type: string;
                    items: {
                        type: string;
                    };
                    maxItems: number;
                };
                payload: {
                    type: string;
                };
                status: {
                    enum: string[];
                };
                error: {
                    type: string[];
                };
                integrity: {
                    type: string;
                };
            };
        };
    };
};
export default _default;
