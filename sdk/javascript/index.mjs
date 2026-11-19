/** JavaScript facade over the shared typed implementation. Works in Node and bundled browsers. */
export {Client, HostAdapter, COCError, VERSION, envelope, validate} from '../typescript/lib/index.js';
import {Client, HostAdapter} from '../typescript/lib/index.js';
export function clientFromEnvironment(environment=process.env){return new Client(environment.COC_URL??'http://127.0.0.1:7310',environment.COC_TOKEN??'',environment.COC_AGENT??'javascript-host')}
export function createHost(client,id,name,definitions){return new HostAdapter(client,id,name,new Map(Object.entries(definitions)),'javascript')}
