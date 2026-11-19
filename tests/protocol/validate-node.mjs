import readline from 'node:readline';import {validate} from '../../sdk/typescript/lib/index.js';
for await(const line of readline.createInterface({input:process.stdin})){let valid=false;try{valid=validate(JSON.parse(line))}catch{}console.log(JSON.stringify({valid}))}
