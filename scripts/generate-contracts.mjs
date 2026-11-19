import {readFile,writeFile,mkdir} from 'node:fs/promises';
const schema=JSON.parse(await readFile(new URL('../specifications/schemas/message.schema.json',import.meta.url),'utf8'));
await mkdir(new URL('../sdk/typescript/src/',import.meta.url),{recursive:true});
await writeFile(new URL('../sdk/typescript/src/schema.ts',import.meta.url),'// Generated from the canonical COC schema. Do not edit.\nexport default '+JSON.stringify(schema,null,2)+';\n');
await writeFile(new URL('../kernels/python/src/coc/message.schema.json',import.meta.url),JSON.stringify(schema,null,2)+'\n');
