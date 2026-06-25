import io.joern.dataflowengineoss.language._
import io.joern.dataflowengineoss.queryengine.EngineContext
import java.io.PrintWriter

@main def main(component: String, outputFile: String) = {
  implicit val context: EngineContext = EngineContext()

  val pattern = "exec|loadUrl|loadData|addJavascriptInterface|rawQuery|execSQL|FileInputStream|FileOutputStream|openFileOutput|forName|DexClassLoader|sendBroadcast|getExternalStorage"

  val methods = cpg.method.fullName(".*" + component + ".*").l
  val sinks = cpg.call.name(pattern).where(_.method.fullName(".*" + component + ".*")).l

  val writer = new PrintWriter(outputFile)
  writer.println("{")
  writer.println("\"component\": \"" + component + "\",")
  writer.println("\"method_count\": " + methods.size + ",")
  writer.println("\"sink_count\": " + sinks.size)
  writer.println("}")
  writer.close()

  println("DONE methods=" + methods.size + " sinks=" + sinks.size)
}
