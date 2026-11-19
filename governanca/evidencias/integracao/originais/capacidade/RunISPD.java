import ispd.arquivo.xml.IconicoXML;
import ispd.motor.ProgressoSimulacao;
import ispd.motor.metricas.*;
import ispd.motor.filas.Tarefa;
import ispd.gui.JResultados;
import java.awt.Color;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import javax.swing.*;

/** Runs the unchanged original iSPD classes; exports observed metrics, never estimates them. */
public class RunISPD {
  static final Path BASE = Paths.get(System.getProperty("user.dir"));
  static class Progress extends ProgressoSimulacao {
    public void incProgresso(int n) {}
    public void print(String s, Color c) { System.out.print(s); }
  }
  static String q(String s) { return "\"" + s.replace("\\", "\\\\").replace("\"","\\\"").replace("\n","\\n").replace("\r","\\r") + "\""; }
  static String json(Object x) {
    if(x==null) return "null";
    if(x instanceof String) return q((String)x);
    if(x instanceof Number) { double d=((Number)x).doubleValue(); return Double.isFinite(d)?x.toString():"null"; }
    if(x instanceof Boolean) return x.toString();
    if(x instanceof Map) { StringJoiner j=new StringJoiner(",","{","}"); ((Map<?,?>)x).forEach((k,v)->j.add(q(k.toString())+":"+json(v))); return j.toString(); }
    if(x instanceof Collection) { StringJoiner j=new StringJoiner(",","[","]"); for(Object e:(Collection<?>)x) j.add(json(e)); return j.toString(); }
    return q(x.toString());
  }
  static Map<String,Object> map(Object... a) { Map<String,Object> m=new LinkedHashMap<>(); for(int i=0;i<a.length;i+=2)m.put((String)a[i],a[i+1]); return m; }
  static Map<String,Object> scalars(Object x) throws Exception {
    Map<String,Object> m=new TreeMap<>();
    for(java.lang.reflect.Method f:x.getClass().getMethods()) if(f.getName().startsWith("get")&&f.getParameterCount()==0&&(f.getReturnType().isPrimitive()||f.getReturnType()==String.class)) m.put(f.getName().substring(3),f.invoke(x));
    return m;
  }
  public static void generate(String name,int nodes,String scheduler,int tasks,int comp,int comm,double power,double bandwidth,double latency,int cores) throws Exception {
    IconicoXML model=new IconicoXML();
    model.addUsers(Arrays.asList("user1"));
    model.addCluster(350,200,0,0,"Cluster0",nodes,power,cores,1000.0,0.0,bandwidth,latency,scheduler,"user1",true);
    model.setLoadRandom(tasks,0,comp,comp,comp,1.0,comm,comm,comm,1.0);
    Files.createDirectories(BASE.resolve("models"));
    if(!IconicoXML.escrever(model.getDescricao(),BASE.resolve("models/"+name+".imsx").toFile()))throw new IOException("Cannot save "+name);
  }
  public static Metricas run(String name,int repeat) throws Exception {
    Path file=BASE.resolve("models/"+name+".imsx");
    org.w3c.dom.Document doc=IconicoXML.ler(file.toFile());
    Progress p=new Progress(); p.validarInicioSimulacao(doc);
    Metricas metrics=p.simulacaoSequencial(doc);
    Map<String,Object> m=map("scenario",name,"repeat",repeat,"model",file.toString(),"engine","Original iSPD.jar / ProgressoSimulacao.simulacaoSequencial","executed_at",java.time.OffsetDateTime.now(java.time.ZoneId.of("America/Sao_Paulo")).toString(),"global",scalars(metrics.getMetricasGlobais()),"task_averages",scalars(metrics));
    List<Object> resources=new ArrayList<>(),communication=new ArrayList<>(),tasks=new ArrayList<>();
    for(Map.Entry<String,MetricasProcessamento> e:metrics.getMetricasProcessamento().entrySet()) { Map<String,Object> v=scalars(e.getValue());v.put("key",e.getKey());resources.add(v); }
    for(Map.Entry<String,MetricasComunicacao> e:metrics.getMetricasComunicacao().entrySet()) communication.add(scalars(e.getValue()));
    for(Tarefa t:metrics.getTarefas()) {
      List<Object> history=new ArrayList<>();
      for(ispd.motor.filas.servidores.CS_Processamento r:t.getHistoricoProcessamento()) history.add(map("id",r.getId(),"node_number",r.getnumeroMaquina()));
      tasks.add(map("id",t.getIdentificador(),"state",t.getEstado(),"completed",t.getEstado()==Tarefa.CONCLUIDO,"created_s",t.getTimeCriacao(),"compute_mflop",t.getTamProcessamento(),"send_mbits",t.getArquivoEnvio(),"resource",t.getLocalProcessamento().getId(),"resource_node_number",t.getCSLProcessamento().getnumeroMaquina(),"processing_history",history,"processing_start_s",t.getTempoInicial(),"processing_finish_s",t.getTempoFinal(),"metrics",scalars(t.getMetricas())));
    }
    m.put("processing_resources",resources);m.put("communication_resources",communication);m.put("tasks",tasks);
    Files.createDirectories(BASE.resolve("results"));
    Files.write(BASE.resolve("results/"+name+"_run"+repeat+".json"),json(m).getBytes("UTF-8"));
    System.out.println("OBSERVED_RESULT "+name+" "+json(m.get("global"))+" averages="+json(m.get("task_averages")));
    return metrics;
  }
  public static void main(String[] args) throws Exception {
    Locale.setDefault(Locale.US);
    if(args.length>0&&args[0].equals("--generate")) {
      generate(args[1],Integer.parseInt(args[2]),args[3],Integer.parseInt(args[4]),Integer.parseInt(args[5]),Integer.parseInt(args[6]),Double.parseDouble(args[7]),Double.parseDouble(args[8]),Double.parseDouble(args[9]),Integer.parseInt(args[10]));return;
    }
    if(args.length>0&&args[0].equals("--show")) {
      Metricas m=run(args[1],1);
      SwingUtilities.invokeLater(()-> { try { UIManager.setLookAndFeel("javax.swing.plaf.nimbus.NimbusLookAndFeel"); JResultados j=new JResultados(null,m,m.getRedeDeFilas(),m.getTarefas(),new ispd.arquivo.xml.ConfiguracaoISPD());j.setTitle("iSPD Results - "+args[1]);j.setDefaultCloseOperation(WindowConstants.DISPOSE_ON_CLOSE);j.setLocationRelativeTo(null);j.setVisible(true); }catch(Exception ex){ex.printStackTrace();} });return;
    }
    if(args.length>0&&args[0].equals("--run")) {run(args[1],args.length>2?Integer.parseInt(args[2]):1);return;}
    String[] names={"bairro_2_workers","bairro_4_workers"};
    int[] nodes={2,4};
    for(int i=0;i<names.length;i++) {
      generate(names[i],nodes[i],"RoundRobin",120,60000,16,20000,1000,.001,1);
      for(int repeat=1;repeat<=2;repeat++)run(names[i],repeat);
    }
  }
}

