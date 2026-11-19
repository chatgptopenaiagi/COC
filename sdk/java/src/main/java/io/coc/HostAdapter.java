package io.coc;
import com.google.gson.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

/** Construct as a singleton bean in Spring or use directly in any JVM application. */
public final class HostAdapter implements AutoCloseable {
 @FunctionalInterface public interface Tool {JsonElement execute(JsonObject arguments,AtomicBoolean cancelled,String taskId)throws Exception;}
 public record Definition(JsonObject contract,Tool execute){}
 private final Client client;private final String id,name;private final Map<String,Definition> tools;private final ConcurrentMap<String,AtomicBoolean> active=new ConcurrentHashMap<>();private final AtomicBoolean stopping=new AtomicBoolean();
 public HostAdapter(Client client,String id,String name,Map<String,Definition> tools){this.client=client;this.id=id;this.name=name;this.tools=Map.copyOf(tools);}
 public JsonArray discoverCapabilities(){var result=new JsonArray();tools.values().forEach(v->result.add(v.contract()));return result;}
 public Set<String> listAvailableTools(){return tools.keySet();}
 public JsonObject readApplicationState(){var o=new JsonObject();o.addProperty("host_id",id);o.addProperty("active_tasks",active.size());return o;}
 public JsonElement executeAuthorizedTool(JsonObject task,AtomicBoolean cancelled)throws Exception{var tool=tools.get(task.get("tool").getAsString());if(tool==null)throw new IllegalArgumentException("unknown tool");var args=task.getAsJsonObject("arguments");Contract.validate(tool.contract().getAsJsonObject("input_schema"),args);var result=tool.execute().execute(args,cancelled,task.get("id").getAsString());Contract.validate(tool.contract().getAsJsonObject("output_schema"),result);return result;}
 public JsonElement getTaskStatus(String task)throws Exception{return client.getTaskStatus(task);}
 public void cancelTask(String task){var flag=active.get(task);if(flag!=null)flag.set(true);}
 public void subscribeToEvents(long after,java.util.function.Consumer<JsonObject> consumer)throws Exception{client.subscribeToEvents(after,consumer);}
 public void reportError(String task,String type)throws Exception{var p=new JsonObject();p.addProperty("task_id",task);p.addProperty("category",type);client.call("COC.ERROR",p);}
 public void requestOperatorAssistance(String task,String reason)throws Exception{var p=new JsonObject();p.addProperty("task_id",task);p.addProperty("kind","operator_assistance");p.addProperty("reason",reason);client.call("COC.EVENT",p);}
 public void detachAgent()throws Exception{stopping.set(true);active.values().forEach(v->v.set(true));client.detachAgent(id);}
 public void run(boolean once)throws Exception{var registration=new JsonObject();registration.addProperty("kind","host");registration.addProperty("id",id);registration.addProperty("name",name);registration.addProperty("language","java");registration.add("capabilities",discoverCapabilities());client.call("COC.REGISTER",registration);var heartbeat=Executors.newSingleThreadScheduledExecutor();heartbeat.scheduleWithFixedDelay(()->{try{var response=client.call("COC.HEARTBEAT",Client.object("{\"host_id\":\""+id+"\"}")).getAsJsonObject();for(var task:response.getAsJsonArray("cancel_task_ids"))cancelTask(task.getAsString());}catch(Exception e){active.values().forEach(v->v.set(true));}},400,400,TimeUnit.MILLISECONDS);
 try{while(!stopping.get()){var request=new JsonObject();request.addProperty("action","claim");request.addProperty("host_id",id);var next=client.call("COC.RECOVER",request).getAsJsonObject().get("task");if(next.isJsonNull()){Thread.sleep(100);continue;}var task=next.getAsJsonObject();String taskId=task.get("id").getAsString();var cancelled=new AtomicBoolean();active.put(taskId,cancelled);var result=new JsonObject();result.addProperty("task_id",taskId);result.add("claim_id",task.get("claim_id"));try{result.add("result",executeAuthorizedTool(task,cancelled));result.addProperty("outcome","succeeded");}catch(Exception e){result.addProperty("outcome",cancelled.get()?"cancelled":"failed");result.add("error",Client.object("{\"message\":\"enterprise operation failed\"}"));reportError(taskId,e.getClass().getSimpleName());}client.call("COC.TOOL_RESULT",result);active.remove(taskId);if(once)break;}}finally{heartbeat.shutdownNow();}}
 @Override public void close(){stopping.set(true);active.values().forEach(v->v.set(true));}
}
