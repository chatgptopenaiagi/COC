import test from 'node:test';import assert from 'node:assert/strict';
import {envelope,validate,Client} from '../../sdk/typescript/lib/index.js';
test('typed envelope conforms and rejects unknown methods',()=>{const message=envelope('sdk','COC.HELLO',{});assert.equal(validate(message),true);message.method='COC.UNSAFE';assert.equal(validate(message),false)});
test('all metadata is required',()=>{const m=envelope('sdk','COC.HELLO',{});delete m.params.integrity;assert.equal(validate(m),false)});
test('remote plaintext rejected',()=>assert.throws(()=>new Client('http://example.com','x','sdk'),/HTTPS/));
