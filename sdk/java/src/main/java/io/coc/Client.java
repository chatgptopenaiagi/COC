package io.coc;
import com.google.gson.*;
import java.io.*;
import java.net.URI;
import java.net.http.*;
import java.time.*;
import java.util.*;
import java.util.function.Consumer;

/** Thread-safe JVM client. Tokens are transport credentials, never message metadata. */
public final class Client {
 private final String url,token; public final String agent; private final HttpClient http;
 public static final Gson JSON=new GsonBuilder().serializeNulls().create();
 public Client(String url,String token,String agent){URI u=URI.create(url);if(u.getUserInfo()!=null||u.getQuery()!=null||u.getFragment()!=null||u.getHost()==null)throw new IllegalArgumentException("invalid broker URL");if(!u.getScheme().equals("https")&&!(u.getScheme().equals("http")&&Set.of("127.0.0.1","localhost","[::1]").contains(u.getHost())))throw new IllegalArgumentException("remote connections require TLS");this.url=url;this.token=token;this.agent=agent;http=HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(10)).followRedirects(HttpClient.Redirect.NEVER).build();}
 public static JsonObject object(String text){return JsonParser.parseString(text).getAsJsonObject();}
 public static JsonObject envelope(String agent,String method,JsonObject payload){var p=new JsonObject();p.addProperty("protocol_version","COC-PROTOCOL/1");p.addProperty("message_id",UUID.randomUUID().toString());p.addProperty("agent_id",agent);for(String name:List.of("parent_agent_id","child_agent_id","host_id","session_id","task_id","correlation_id"))p.add(name,JsonNull.INSTANCE);p.addProperty("timestamp",Instant.now().toString());p.add("scope",new JsonArray());p.add("payload",payload);p.addProperty("status","request");p.add("error",JsonNull.INSTANCE);p.add("integrity",new JsonObject());var r=new JsonObject();r.addProperty("jsonrpc","2.0");r.addProperty("id",UUID.randomUUID().toString());r.addProperty("method",method);r.add("params",p);return r;}
 public JsonElement call(String method,JsonObject payload)throws IOException,InterruptedException{var request=envelope(agent,method,payload);var body=HttpRequest.BodyPublishers.ofString(JSON.toJson(request));var response=http.send(HttpRequest.newBuilder(URI.create(url+"/rpc")).timeout(Duration.ofSeconds(15)).header("Authorization","Bearer "+token).header("Content-Type","application/json").POST(body).build(),HttpResponse.BodyHandlers.ofString());if(response.statusCode()!=200)throw new IOException("broker rejected request: "+response.statusCode());var parsed=object(response.body());if(parsed.has("error"))throw new IOException(parsed.get("error").toString());if(!parsed.get("id").equals(request.get("id")))throw new IOException("response id mismatch");return parsed.getAsJsonObject("result").getAsJsonObject("payload").get("data");}
 public void subscribeToEvents(long after,Consumer<JsonObject> consumer)throws IOException,InterruptedException{var request=HttpRequest.newBuilder(URI.create(url+"/events?after="+after)).header("Authorization","Bearer "+token).GET().build();var response=http.send(request,HttpResponse.BodyHandlers.ofInputStream());if(response.statusCode()!=200){response.body().close();throw new IOException("event authorization failed");}try(var reader=new BufferedReader(new InputStreamReader(response.body(),java.nio.charset.StandardCharsets.UTF_8))){String line;while((line=reader.readLine())!=null){if(line.startsWith("data: "))consumer.accept(object(line.substring(6)));}}}
 public JsonElement getTaskStatus(String id)throws Exception{var p=new JsonObject();p.addProperty("task_id",id);return call("COC.RECOVER",p);}
 public JsonElement cancelTask(String id)throws Exception{var p=new JsonObject();p.addProperty("task_id",id);return call("COC.CANCEL",p);}
 public JsonElement discoverCapabilities()throws Exception{return call("COC.CAPABILITIES",new JsonObject());}
 public JsonElement detachAgent(String host)throws Exception{var p=new JsonObject();p.addProperty("host_id",host);return call("COC.DETACH",p);}
}
