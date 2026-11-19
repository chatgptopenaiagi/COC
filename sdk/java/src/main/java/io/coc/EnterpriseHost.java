package io.coc;
import com.google.gson.*;
import java.math.*;
import java.nio.file.*;
import java.sql.*;
import java.util.*;

/** Synthetic enterprise records only. No connection to external business/clinical databases. */
public final class EnterpriseHost {
 public static void main(String[] args)throws Exception{
  if(args.length>0&&args[0].equals("validate")){var schema=Client.object(Files.readString(Path.of(args[1])));try(var scanner=new Scanner(System.in)){while(scanner.hasNextLine()){boolean valid;try{Contract.validate(schema,JsonParser.parseString(scanner.nextLine()));valid=true;}catch(Exception e){valid=false;}System.out.println("{\"valid\":"+valid+"}");}}return;}
  if(args.length>0&&args[0].equals("self-test")){var m=Client.envelope("java","COC.HELLO",new JsonObject());var schema=Client.object(Files.readString(Path.of(args[1])));Contract.validate(schema,m);m.remove("method");try{Contract.validate(schema,m);throw new AssertionError("missing method accepted");}catch(IllegalArgumentException expected){}System.out.println("Java contract tests passed");return;}
  var env=System.getenv();var client=new Client(env.getOrDefault("COC_URL","http://127.0.0.1:7310"),Objects.requireNonNull(env.get("COC_TOKEN")),env.getOrDefault("COC_AGENT","java-host"));
  String db=env.getOrDefault("COC_JAVA_DB","mem:coc;DB_CLOSE_DELAY=-1");
  try(var connection=DriverManager.getConnection("jdbc:h2:"+db)){connection.createStatement().execute("CREATE TABLE IF NOT EXISTS invoices(task_id VARCHAR PRIMARY KEY, units INT, unit_price DECIMAL(18,2), total DECIMAL(18,2))");
   var invoice=Client.object("{\"name\":\"invoice\",\"description\":\"Create an idempotent synthetic invoice\",\"version\":\"1.0\",\"idempotent\":true,\"cancellable\":false,\"input_schema\":{\"type\":\"object\",\"required\":[\"units\",\"unit_price\"],\"properties\":{\"units\":{\"type\":\"integer\",\"minimum\":1,\"maximum\":10000},\"unit_price\":{\"type\":\"string\",\"maxLength\":20}},\"additionalProperties\":false},\"output_schema\":{\"type\":\"object\",\"required\":[\"invoice_id\",\"total\"],\"properties\":{\"invoice_id\":{\"type\":\"string\"},\"total\":{\"type\":\"string\"}}}}");
   var synthetic=Client.object("{\"name\":\"synthetic_report\",\"description\":\"Export administrative FHIR-shaped synthetic patient bundle\",\"version\":\"1.0\",\"idempotent\":true,\"cancellable\":false,\"input_schema\":{\"type\":\"object\",\"additionalProperties\":false},\"output_schema\":{\"type\":\"object\",\"required\":[\"resourceType\",\"type\",\"entry\",\"synthetic\"],\"properties\":{\"resourceType\":{\"const\":\"Bundle\"},\"type\":{\"const\":\"collection\"},\"entry\":{\"type\":\"array\"},\"synthetic\":{\"const\":true}}}}");
   Map<String,HostAdapter.Definition> tools=new LinkedHashMap<>();
   tools.put("invoice",new HostAdapter.Definition(invoice,(input,cancelled,task)->{int units=input.get("units").getAsInt();BigDecimal price=new BigDecimal(input.get("unit_price").getAsString()).setScale(2,RoundingMode.UNNECESSARY);if(units<1||units>10000||price.signum()<0)throw new IllegalArgumentException("invalid invoice");BigDecimal total=price.multiply(BigDecimal.valueOf(units));try(var insert=connection.prepareStatement("MERGE INTO invoices KEY(task_id) VALUES(?,?,?,?)")){insert.setString(1,task);insert.setInt(2,units);insert.setBigDecimal(3,price);insert.setBigDecimal(4,total);insert.executeUpdate();}try(var query=connection.prepareStatement("SELECT total FROM invoices WHERE task_id=?")){query.setString(1,task);try(var rows=query.executeQuery()){rows.next();var out=new JsonObject();out.addProperty("invoice_id",task);out.addProperty("total",rows.getBigDecimal(1).toPlainString());return out;}}}));
   tools.put("synthetic_report",new HostAdapter.Definition(synthetic,(input,cancelled,task)->Client.object("{\"resourceType\":\"Bundle\",\"type\":\"collection\",\"synthetic\":true,\"entry\":[{\"resource\":{\"resourceType\":\"Patient\",\"id\":\"synthetic-001\",\"active\":true,\"name\":[{\"family\":\"TEST-ONLY\",\"given\":[\"Synthetic\"]}]}}]}")));
   try(var host=new HostAdapter(client,"java-enterprise","Java enterprise and synthetic healthcare",tools)){host.run(Arrays.asList(args).contains("--once"));}
  }
 }
}
