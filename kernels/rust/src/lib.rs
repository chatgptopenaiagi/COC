//! Native COC boundary. No secrets are serialized into protocol messages.
use serde_json::{json, Value};
use std::{process::{Child, Command, Stdio}, thread, time::{Duration, Instant}};
use zeroize::Zeroizing;

pub const SCHEMA: &str = include_str!("../../../specifications/schemas/message.schema.json");
pub fn validate(value: &Value) -> Result<(), String> {
    let schema: Value = serde_json::from_str(SCHEMA).map_err(|e| e.to_string())?;
    let validator = jsonschema::validator_for(&schema).map_err(|e| e.to_string())?;
    validator.validate(value).map_err(|e| e.to_string())
}
/// Validate a UTF-8 COC request at the native ABI boundary.
/// # Safety
/// `data` must address `len` readable bytes owned by the caller for this call.
/// No pointer is retained. Returns 0 for valid, 1 for invalid, 2 for invalid bounds.
#[no_mangle]
pub unsafe extern "C" fn coc_validate_json(data: *const u8, len: usize) -> i32 {
    if data.is_null() || len == 0 || len > 1_048_576 { return 2; }
    let bytes = std::slice::from_raw_parts(data, len);
    match serde_json::from_slice::<Value>(bytes) { Ok(v) if validate(&v).is_ok() => 0, _ => 1 }
}
pub fn envelope(agent: &str, method: &str, payload: Value) -> Value {
    json!({"jsonrpc":"2.0","id":uuid::Uuid::new_v4().to_string(),"method":method,"params":{
        "protocol_version":"COC-PROTOCOL/1","message_id":uuid::Uuid::new_v4().to_string(),"agent_id":agent,
        "parent_agent_id":null,"child_agent_id":null,"host_id":payload.get("host_id"),"session_id":null,
        "task_id":payload.get("task_id"),"correlation_id":null,"timestamp":chrono::Utc::now().to_rfc3339(),
        "scope":[],"payload":payload,"status":"request","error":null,"integrity":{}}})
}
pub struct Client { url: String, token: Zeroizing<String>, pub agent: String, http: reqwest::blocking::Client }
impl Client {
    pub fn new(url: String, token: String, agent: String) -> Result<Self,String> {
        let parsed=reqwest::Url::parse(&url).map_err(|_|"invalid broker URL")?;
        if !parsed.username().is_empty() || parsed.password().is_some() || parsed.query().is_some() || parsed.fragment().is_some() { return Err("invalid broker URL".into()); }
        if parsed.scheme()!="https" && !(parsed.scheme()=="http" && matches!(parsed.host_str(),Some("127.0.0.1"|"localhost"|"[::1]"))) { return Err("remote transport requires TLS".into()); }
        let http = reqwest::blocking::Client::builder().redirect(reqwest::redirect::Policy::none()).timeout(Duration::from_secs(15)).build().map_err(|e|e.to_string())?;
        Ok(Self{url,token:Zeroizing::new(token),agent,http})
    }
    pub fn forward(&self, request: &Value) -> Result<Value,String> {
        validate(request)?;
        if request["params"]["agent_id"] != self.agent { return Err("identity mismatch".into()); }
        self.http.post(format!("{}/rpc",self.url)).bearer_auth(self.token.as_str()).json(request).send()
            .and_then(|r|r.error_for_status()).and_then(|r|r.json()).map_err(|_|"authenticated broker request failed".into())
    }
    pub fn call(&self,method:&str,payload:Value)->Result<Value,String>{
        let r=self.forward(&envelope(&self.agent,method,payload))?;
        if r.get("error").is_some(){return Err(r["error"].to_string());} Ok(r["result"]["payload"]["data"].clone())
    }
}
/// Owns one child process; drop kills and waits. Does not claim ownership of unrelated processes.
pub struct OwnedProcess { child: Child }
impl OwnedProcess {
    pub fn spawn(executable:&str,args:&[String])->std::io::Result<Self>{Ok(Self{child:Command::new(executable).args(args).stdin(Stdio::null()).stdout(Stdio::null()).stderr(Stdio::null()).spawn()?})}
    pub fn pid(&self)->u32{self.child.id()}
    pub fn wait_bounded(&mut self,timeout:Duration)->std::io::Result<bool>{let until=Instant::now()+timeout;loop{if let Some(status)=self.child.try_wait()?{return Ok(status.success())};if Instant::now()>=until{self.child.kill()?;self.child.wait()?;return Ok(false)};thread::sleep(Duration::from_millis(20));}}
}
impl Drop for OwnedProcess {fn drop(&mut self){if self.child.try_wait().ok().flatten().is_none(){let _=self.child.kill();let _=self.child.wait();}}}

#[cfg(test)] mod tests {
    use super::*;
    #[test] fn common_contract(){let v=envelope("native","COC.HELLO",json!({}));assert!(validate(&v).is_ok());let mut bad=v;bad["params"]["protocol_version"]=json!("bad");assert!(validate(&bad).is_err());}
    #[test] fn abi_checks_bounds(){unsafe{assert_eq!(coc_validate_json(std::ptr::null(),20),2);let b=b"{}";assert_eq!(coc_validate_json(b.as_ptr(),b.len()),1);}}
    #[test] fn reject_plaintext_remote(){assert!(Client::new("http://example.org".into(),"secret".into(),"agent".into()).is_err());}
}
