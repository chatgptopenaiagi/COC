package io.coc;
import com.google.gson.*;
import java.time.OffsetDateTime;
import java.util.*;

/** Portable validator for the schema vocabulary used by COC-PROTOCOL/1. */
public final class Contract {
 private Contract() {}
 public static void validate(JsonObject schema, JsonElement value) {
  if(schema.has("const")&&!schema.get("const").equals(value))throw new IllegalArgumentException("constant mismatch");
  if(schema.has("enum")){boolean found=false;for(JsonElement e:schema.getAsJsonArray("enum"))found|=e.equals(value);if(!found)throw new IllegalArgumentException("enum mismatch");}
  if(schema.has("type")){JsonElement type=schema.get("type");boolean ok=false;if(type.isJsonArray()){for(JsonElement t:type.getAsJsonArray())ok|=matches(t.getAsString(),value);}else ok=matches(type.getAsString(),value);if(!ok)throw new IllegalArgumentException("type mismatch");}
  if(value.isJsonNull())return;
  if(value.isJsonObject()){
   JsonObject o=value.getAsJsonObject();if(schema.has("required"))for(JsonElement k:schema.getAsJsonArray("required"))if(!o.has(k.getAsString()))throw new IllegalArgumentException("required: "+k.getAsString());
   JsonObject props=schema.has("properties")?schema.getAsJsonObject("properties"):new JsonObject();for(var e:o.entrySet()){if(props.has(e.getKey()))validate(props.getAsJsonObject(e.getKey()),e.getValue());else if(schema.has("additionalProperties")&&schema.get("additionalProperties").isJsonPrimitive()&&!schema.get("additionalProperties").getAsBoolean())throw new IllegalArgumentException("unknown property");}
  }
  if(value.isJsonArray()){var a=value.getAsJsonArray();if(schema.has("maxItems")&&a.size()>schema.get("maxItems").getAsInt())throw new IllegalArgumentException("array limit");if(schema.has("minItems")&&a.size()<schema.get("minItems").getAsInt())throw new IllegalArgumentException("array minimum");if(schema.has("items"))for(var item:a)validate(schema.getAsJsonObject("items"),item);}
  if(value.isJsonPrimitive()&&value.getAsJsonPrimitive().isString()){String s=value.getAsString();if(schema.has("minLength")&&s.length()<schema.get("minLength").getAsInt())throw new IllegalArgumentException("string minimum");if(schema.has("maxLength")&&s.length()>schema.get("maxLength").getAsInt())throw new IllegalArgumentException("string limit");if(schema.has("format")&&schema.get("format").getAsString().equals("date-time"))OffsetDateTime.parse(s);}
 }
 private static boolean matches(String type,JsonElement v){return switch(type){case "null"->v.isJsonNull();case "object"->v.isJsonObject();case "array"->v.isJsonArray();case "string"->v.isJsonPrimitive()&&v.getAsJsonPrimitive().isString();case "boolean"->v.isJsonPrimitive()&&v.getAsJsonPrimitive().isBoolean();case "number"->v.isJsonPrimitive()&&v.getAsJsonPrimitive().isNumber();case "integer"->v.isJsonPrimitive()&&v.getAsJsonPrimitive().isNumber()&&v.getAsBigDecimal().stripTrailingZeros().scale()<=0;default->false;};}
}
