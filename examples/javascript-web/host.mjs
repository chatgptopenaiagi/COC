import {clientFromEnvironment,createHost} from '../../sdk/javascript/index.mjs';
const host=createHost(clientFromEnvironment(),'javascript-web','JavaScript text application',{
 'text_metrics':{capability:{name:'text_metrics',description:'Count words and Unicode code points',version:'1.0',idempotent:true,cancellable:false,input_schema:{type:'object',properties:{text:{type:'string',maxLength:10000}},required:['text'],additionalProperties:false},output_schema:{type:'object',properties:{words:{type:'integer'},characters:{type:'integer'}},required:['words','characters'],additionalProperties:false}},execute:({text})=>({words:text.trim()?text.trim().split(/\s+/u).length:0,characters:[...text].length})}
});
process.on('SIGINT',()=>host.detach_agent());
await host.run(process.argv.includes('--once'));
