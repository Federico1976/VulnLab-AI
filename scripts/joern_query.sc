// joern_query.sc
// ================
// Assume il CPG GIA' caricato nel workspace (tramite open/importCpg
// fatto da un comando precedente). Esegue solo la query.

import io.joern.dataflowengineoss.language._
import io.joern.dataflowengineoss.queryengine.EngineContext
import java.io.PrintWriter

@main def main(component: String, outputFile: String) = {
  implicit val context: EngineContext = EngineContext()

  val dangerousSinkPattern = "exec|loadUrl|loadData|addJavascriptInterface|rawQuery|execSQL|" +
    "FileInputStream|FileOutputStream|openFileOutput|forName|DexClassLoader|" +
    "sendBroadcast|getExternalStorage"

  val methods = cpg.method.fullName(s".*${component}.*").l
  val methodNames = methods.map(_.fullName)

  val sinks = cpg.call
    .name(dangerousSinkPattern)
    .where(_.method.fullName(s".*${component}.*"))
    .l

  def escapeJson(s: String): String = s.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", " ")

  val sinkInfo = sinks.map(s => Map(
    "name" -> s.name, "code" -> s.code,
    "line" -> s.lineNumber.getOrElse(-1).toString,
    "methodFullName" -> s.methodFullName
  ))

  val sinksJson = sinkInfo.map { s =>
    s"""    {"name": "${escapeJson(s("name"))}", "code": "${escapeJson(s("code"))}", "line": ${s("line")}, "methodFullName": "${escapeJson(s("methodFullName"))}"}"""
  }.mkString(",\n")
  val methodsJson = methodNames.map(m => s""""${escapeJson(m)}"""").mkString(", ")

  val jsonOutput = s"""{
  "component": "${escapeJson(component)}",
  "method_count": ${methods.size},
  "methods_found": [${methodsJson}],
  "sink_count": ${sinks.size},
  "dangerous_sinks_found": [
${sinksJson}
  ]
}"""

  val writer = new PrintWriter(outputFile)
  writer.write(jsonOutput)
  writer.close()

  println(s"[OK] Metodi trovati: ${methods.size}, Sink: ${sinks.size}")
}
