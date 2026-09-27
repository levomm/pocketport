package app.pocketport.companion

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URI
import java.net.URL
import java.util.concurrent.Executors
import kotlinx.coroutines.delay

private val Bg = Color(0xFF070A09)
private val Panel = Color(0xFF0D1210)
private val Panel2 = Color(0xFF111814)
private val Line = Color(0xFF26362D)
private val TextMain = Color(0xFFEDF4EF)
private val Muted = Color(0xFF8D9B92)
private val Accent = Color(0xFF72F59C)
private val Warning = Color(0xFFD8B46F)

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme(
                colorScheme = darkColorScheme(
                    primary = Accent,
                    onPrimary = Color(0xFF061009),
                    background = Bg,
                    onBackground = TextMain,
                    surface = Panel,
                    onSurface = TextMain,
                    surfaceVariant = Panel2,
                    outline = Line,
                )
            ) {
                Surface(modifier = Modifier.fillMaxSize(), color = Bg) {
                    PocketPortApp()
                }
            }
        }
    }
}

private data class BridgeState(
    val connected: Boolean = false,
    val checking: Boolean = false,
    val version: String = "",
    val arch: String = "",
    val api: String = "",
    val capabilities: List<String> = emptyList(),
    val error: String? = null,
)

private data class PlanState(
    val repository: String,
    val score: String,
    val strategy: String,
    val status: String,
    val method: String,
    val install: List<String>,
    val run: List<String>,
)

private data class PreparedState(
    val repoRoot: String,
    val command: String,
    val runnerAvailable: Boolean,
)

private enum class ActiveJob {
    NONE,
    SCAN,
    PREPARE,
}

@Composable
private fun PocketPortApp() {
    val context = LocalContext.current
    val executor = remember { Executors.newSingleThreadExecutor() }
    val main = remember { Handler(Looper.getMainLooper()) }
    val client = remember { PocketPortBridgeClient() }

    var repoInput by remember { mutableStateOf("deepseek-ai/deepseek-harness") }
    var bridge by remember { mutableStateOf(BridgeState()) }
    var plan by remember { mutableStateOf<PlanState?>(null) }
    var prepared by remember { mutableStateOf<PreparedState?>(null) }
    var busy by remember { mutableStateOf(false) }
    var activeJob by remember { mutableStateOf(ActiveJob.NONE) }
    var elapsedSeconds by remember { mutableStateOf(0) }
    var message by remember { mutableStateOf<String?>(null) }

    fun checkBridge() {
        if (bridge.checking) return
        bridge = bridge.copy(checking = true, error = null)
        executor.execute {
            val result = client.health()
            main.post {
                bridge = result.fold(
                    onSuccess = { json ->
                        BridgeState(
                            connected = json.optBoolean("ok"),
                            version = json.optString("version"),
                            arch = json.optString("arch"),
                            api = json.opt("api")?.toString().orEmpty(),
                            capabilities = json.optJSONArray("capabilities").toStrings(),
                        )
                    },
                    onFailure = {
                        BridgeState(error = it.message ?: "PocketPort Core is not reachable.")
                    },
                )
            }
        }
    }

    fun scanRepository() {
        val repository = normalizeRepository(repoInput)
        if (repository == null) {
            message = "Enter owner/repository or a GitHub URL."
            return
        }
        busy = true
        activeJob = ActiveJob.SCAN
        elapsedSeconds = 0
        plan = null
        prepared = null
        message = "Building local execution plan..."
        executor.execute {
            val result = client.plan(repository)
            main.post {
                busy = false
                activeJob = ActiveJob.NONE
                result.fold(
                    onSuccess = { json ->
                        val execution = json.optJSONObject("execution_plan") ?: JSONObject()
                        plan = PlanState(
                            repository = json.optString("repository", repository),
                            score = json.opt("score")?.toString() ?: "-",
                            strategy = json.optString("strategy", "unknown"),
                            status = execution.optString("status", "plan"),
                            method = execution.optString("method", "PocketPort"),
                            install = execution.optJSONArray("install").toStrings(),
                            run = execution.optJSONArray("run").toStrings(),
                        )
                        message = "Plan ready on this phone."
                        checkBridge()
                    },
                    onFailure = {
                        message = it.message ?: "Local planning failed."
                        checkBridge()
                    },
                )
            }
        }
    }

    fun prepareRepository() {
        val repository = plan?.repository ?: normalizeRepository(repoInput) ?: return
        busy = true
        activeJob = ActiveJob.PREPARE
        elapsedSeconds = 0
        message = "Preparing PocketPort workspace..."
        executor.execute {
            val result = client.prepare(repository)
            main.post {
                busy = false
                activeJob = ActiveJob.NONE
                result.fold(
                    onSuccess = { json ->
                        val root = json.optString("repo_root")
                        val hasRunner = !json.isNull("runner") && json.optString("runner").isNotBlank()
                        val quoted = shellQuote(root)
                        val command = "cd " + quoted + " && ./termux-install.sh"
                        prepared = PreparedState(root, command, hasRunner)
                        message = "Workspace prepared. Nothing has executed yet."
                    },
                    onFailure = { message = it.message ?: "Workspace preparation failed." },
                )
            }
        }
    }

    LaunchedEffect(Unit) { checkBridge() }
    LaunchedEffect(activeJob) {
        if (activeJob != ActiveJob.NONE) {
            elapsedSeconds = 0
            val current = activeJob
            while (activeJob == current) {
                delay(1000)
                if (activeJob == current) elapsedSeconds += 1
            }
        }
    }
    DisposableEffect(Unit) { onDispose { executor.shutdownNow() } }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .safeDrawingPadding()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 18.dp, vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        BrandHeader()
        BridgeCard(
            state = bridge,
            onCheck = ::checkBridge,
            onOpenTermux = { copyAndOpenTermux(context, "pocketport serve") },
        )

        Text(
            "Run more GitHub tools on Android.",
            color = TextMain,
            fontSize = 34.sp,
            lineHeight = 36.sp,
            fontWeight = FontWeight.SemiBold,
        )
        Text(
            "Native control surface for PocketPort Core in Termux. One scanner, one source of truth.",
            color = Muted,
            fontSize = 14.sp,
            lineHeight = 20.sp,
        )

        OutlinedTextField(
            value = repoInput,
            onValueChange = { repoInput = it },
            modifier = Modifier.fillMaxWidth(),
            label = { Text("GitHub repository") },
            placeholder = { Text("owner/repository") },
            singleLine = true,
        )

        Button(
            onClick = ::scanRepository,
            enabled = bridge.connected && !busy,
            modifier = Modifier.fillMaxWidth().height(54.dp),
            colors = ButtonDefaults.buttonColors(
                containerColor = Accent,
                contentColor = Color(0xFF061009),
                disabledContainerColor = Color(0xFF203128),
                disabledContentColor = Muted,
            ),
        ) {
            val label = when (activeJob) {
                ActiveJob.SCAN -> "Scanning..."
                ActiveJob.PREPARE -> "Preparing..."
                ActiveJob.NONE -> "Scan on this phone"
            }
            Text(label, fontWeight = FontWeight.Bold)
        }

        if (activeJob != ActiveJob.NONE) {
            OperationProgressCard(activeJob, elapsedSeconds)
        }

        FlowStatusCard(
            bridgeConnected = bridge.connected,
            planReady = plan != null,
            workspaceReady = prepared != null,
            activeJob = activeJob,
        )

        if (!bridge.connected) {
            Text(
                "Open Termux, run pocketport serve, then leave Termux open in the background. Closing it disconnects the bridge.",
                color = Warning,
                fontSize = 12.sp,
                lineHeight = 18.sp,
            )
        }

        message?.let { StatusStrip(it) }
        plan?.let { current -> PlanCard(current, busy, ::prepareRepository) }
        prepared?.let { ready ->
            PreparedCard(ready) { copyAndOpenTermux(context, ready.command) }
        }
        Spacer(Modifier.height(24.dp))
    }
}

@Composable
private fun BrandHeader() {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(
                modifier = Modifier
                    .size(34.dp)
                    .background(Color(0xFF0C2A1B), RoundedCornerShape(9.dp))
                    .border(1.dp, Color(0xFF12673F), RoundedCornerShape(9.dp)),
                contentAlignment = Alignment.Center,
            ) {
                Text(">_", color = Accent, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold)
            }
            Text("  Pocket", color = TextMain, fontSize = 20.sp, fontWeight = FontWeight.Bold)
            Text("Port", color = Accent, fontSize = 20.sp, fontWeight = FontWeight.Bold)
        }
        Text("COMPANION", color = Muted, fontFamily = FontFamily.Monospace, fontSize = 9.sp)
    }
}

@Composable
private fun BridgeCard(state: BridgeState, onCheck: () -> Unit, onOpenTermux: () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = Panel),
        border = androidx.compose.foundation.BorderStroke(1.dp, Line),
        shape = RoundedCornerShape(14.dp),
    ) {
        Column(modifier = Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        Modifier.size(9.dp).background(
                            if (state.connected) Accent else if (state.error != null) Warning else Muted,
                            CircleShape,
                        )
                    )
                    Text(
                        if (state.connected) "  PocketPort Core connected" else "  Phone bridge",
                        color = TextMain,
                        fontSize = 13.sp,
                        fontWeight = FontWeight.SemiBold,
                    )
                }
                Text(
                    when {
                        state.checking -> "CHECKING"
                        state.connected -> "READY"
                        else -> "OFFLINE"
                    },
                    color = if (state.connected) Accent else Muted,
                    fontFamily = FontFamily.Monospace,
                    fontSize = 9.sp,
                )
            }

            if (state.connected) {
                Text(
                    state.arch.ifBlank { "unknown" } + " · API " + state.api.ifBlank { "?" } + " · v" + state.version.ifBlank { "?" },
                    color = Muted,
                    fontFamily = FontFamily.Monospace,
                    fontSize = 10.sp,
                )
                if (state.capabilities.isNotEmpty()) {
                    Text(
                        state.capabilities.joinToString("  •  "),
                        color = Color(0xFF9FB0A5),
                        fontFamily = FontFamily.Monospace,
                        fontSize = 9.sp,
                    )
                }
            } else {
                Text(
                    "1. Open Termux\n2. Run: pocketport serve\n3. Come back and tap Check bridge",
                    color = Muted,
                    fontSize = 11.sp,
                    lineHeight = 17.sp,
                )
                CommandLine("pocketport serve")
            }

            Text(
                "Keep Termux open with pocketport serve running in the background. If you close Termux, the bridge disconnects.",
                color = Warning,
                fontSize = 10.sp,
                lineHeight = 15.sp,
            )

            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = onOpenTermux, modifier = Modifier.weight(1f)) {
                    Text("Copy + open Termux", fontSize = 10.sp)
                }
                Button(
                    onClick = onCheck,
                    enabled = !state.checking,
                    modifier = Modifier.weight(1f),
                    colors = ButtonDefaults.buttonColors(containerColor = Panel2, contentColor = TextMain),
                ) {
                    Text(if (state.checking) "Checking..." else "Check bridge", fontSize = 11.sp)
                }
            }
        }
    }
}


@Composable
private fun OperationProgressCard(job: ActiveJob, elapsed: Int) {
    var expanded by remember(job) { mutableStateOf(true) }
    val timeout = if (job == ActiveJob.SCAN) 90 else 240
    val remaining = (timeout - elapsed).coerceAtLeast(0)
    val progress = (elapsed.toFloat() / timeout.toFloat()).coerceIn(0f, 0.98f)
    val stages = if (job == ActiveJob.SCAN) {
        listOf(
            "Contact bridge",
            "Inspect repository",
            "Build execution plan",
        )
    } else {
        listOf(
            "Create workspace",
            "Apply compatibility fixes",
            "Write install / run handoff",
        )
    }
    val stageIndex = if (job == ActiveJob.SCAN) {
        when {
            elapsed < 4 -> 0
            elapsed < 20 -> 1
            else -> 2
        }
    } else {
        when {
            elapsed < 10 -> 0
            elapsed < 55 -> 1
            else -> 2
        }
    }

    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = Color(0xFF0A100C)),
        border = androidx.compose.foundation.BorderStroke(1.dp, Color(0xFF21402D)),
        shape = RoundedCornerShape(14.dp),
    ) {
        Column(modifier = Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        if (job == ActiveJob.SCAN) "SCANNING REPOSITORY" else "PREPARING WORKSPACE",
                        color = Accent,
                        fontFamily = FontFamily.Monospace,
                        fontSize = 9.sp,
                    )
                    Text(
                        stages[stageIndex],
                        color = TextMain,
                        fontSize = 13.sp,
                        fontWeight = FontWeight.SemiBold,
                    )
                }
                OutlinedButton(onClick = { expanded = !expanded }) {
                    Text(if (expanded) "Less" else "Details", fontSize = 9.sp)
                }
            }

            SegmentedPulseRail(progress = progress, stageIndex = stageIndex)

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Text(
                    elapsed.toString() + "s elapsed",
                    color = Muted,
                    fontFamily = FontFamily.Monospace,
                    fontSize = 9.sp,
                )
                Text(
                    "~" + remaining + "s timeout window left",
                    color = Muted,
                    fontFamily = FontFamily.Monospace,
                    fontSize = 9.sp,
                )
            }

            if (expanded) {
                stages.forEachIndexed { index, label ->
                    val state = when {
                        index < stageIndex -> "DONE"
                        index == stageIndex -> "NOW"
                        else -> "NEXT"
                    }
                    val color = if (index <= stageIndex) Accent else Muted
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                    ) {
                        Text((index + 1).toString() + ". " + label, color = color, fontSize = 10.sp)
                        Text(state, color = color, fontFamily = FontFamily.Monospace, fontSize = 8.sp)
                    }
                }
                Text(
                    "The timer is a live timeout/ETA indicator, not a fake exact build percentage.",
                    color = Muted,
                    fontSize = 9.sp,
                    lineHeight = 14.sp,
                )
            }
        }
    }
}

@Composable
private fun SegmentedPulseRail(progress: Float, stageIndex: Int) {
    val segments = 12
    val activeSegments = (progress * segments).toInt().coerceIn(0, segments)

    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        repeat(segments) { index ->
            val filled = index < activeSegments
            val pulse = index == activeSegments.coerceAtMost(segments - 1)
            val segmentColor = when {
                filled -> Accent
                pulse -> Warning
                else -> Color(0xFF18231D)
            }
            Box(
                modifier = Modifier
                    .weight(1f)
                    .height(if (pulse) 9.dp else 6.dp)
                    .background(segmentColor, RoundedCornerShape(999.dp))
            )
        }
    }

    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        repeat(3) { index ->
            val done = index < stageIndex
            val active = index == stageIndex
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Box(
                    modifier = Modifier
                        .size(if (active) 16.dp else 12.dp)
                        .background(
                            when {
                                done -> Accent
                                active -> Warning
                                else -> Color(0xFF26362D)
                            },
                            CircleShape,
                        )
                )
                Text(
                    when (index) {
                        0 -> "START"
                        1 -> "WORK"
                        else -> "PLAN"
                    },
                    color = if (done || active) TextMain else Muted,
                    fontFamily = FontFamily.Monospace,
                    fontSize = 7.sp,
                )
            }
        }
    }
}

@Composable
private fun FlowStatusCard(
    bridgeConnected: Boolean,
    planReady: Boolean,
    workspaceReady: Boolean,
    activeJob: ActiveJob,
) {
    val rows = listOf(
        Triple("Bridge", bridgeConnected, activeJob == ActiveJob.NONE && !bridgeConnected),
        Triple("Scan", planReady, activeJob == ActiveJob.SCAN),
        Triple("Plan", planReady, false),
        Triple("Prepare", workspaceReady, activeJob == ActiveJob.PREPARE),
        Triple("Handoff", workspaceReady, false),
    )

    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = Panel),
        border = androidx.compose.foundation.BorderStroke(1.dp, Line),
        shape = RoundedCornerShape(14.dp),
    ) {
        Column(modifier = Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("LIVE FLOW", color = Muted, fontFamily = FontFamily.Monospace, fontSize = 9.sp)
            rows.forEach { (label, done, active) ->
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween,
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Box(
                            modifier = Modifier
                                .size(8.dp)
                                .background(
                                    when {
                                        done -> Accent
                                        active -> Warning
                                        else -> Color(0xFF334039)
                                    },
                                    CircleShape,
                                )
                        )
                        Text("  " + label, color = if (done || active) TextMain else Muted, fontSize = 10.sp)
                    }
                    Text(
                        when {
                            done -> "DONE"
                            active -> "RUNNING"
                            else -> "WAITING"
                        },
                        color = when {
                            done -> Accent
                            active -> Warning
                            else -> Muted
                        },
                        fontFamily = FontFamily.Monospace,
                        fontSize = 8.sp,
                    )
                }
            }
        }
    }
}

@Composable
private fun StatusStrip(text: String) {
    Box(
        modifier = Modifier.fillMaxWidth()
            .background(Color(0xFF0A100C), RoundedCornerShape(10.dp))
            .border(1.dp, Color(0xFF1F2D25), RoundedCornerShape(10.dp))
            .padding(12.dp),
    ) {
        Text(text, color = Muted, fontSize = 11.sp, lineHeight = 16.sp)
    }
}

@Composable
private fun PlanCard(plan: PlanState, busy: Boolean, onPrepare: () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = Panel),
        border = androidx.compose.foundation.BorderStroke(1.dp, Color(0xFF21402D)),
        shape = RoundedCornerShape(14.dp),
    ) {
        Column(modifier = Modifier.padding(15.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text("LOCAL EXECUTION PLAN", color = Accent, fontFamily = FontFamily.Monospace, fontSize = 9.sp)
            Text(plan.repository, color = TextMain, fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
            Text(
                "score " + plan.score + " · " + plan.strategy + " · " + plan.method,
                color = TextMain,
                fontFamily = FontFamily.Monospace,
                fontSize = 11.sp,
            )
            Text(
                plan.status + " · " + plan.install.size + " install · " + plan.run.size + " run commands",
                color = Muted,
                fontFamily = FontFamily.Monospace,
                fontSize = 10.sp,
            )
            (plan.install + plan.run).take(3).forEach { CommandLine(it) }
            Button(
                onClick = onPrepare,
                enabled = !busy,
                modifier = Modifier.fillMaxWidth().height(50.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Accent, contentColor = Color(0xFF061009)),
            ) {
                Text("Prepare on this phone", fontWeight = FontWeight.Bold)
            }
        }
    }
}

@Composable
private fun CommandLine(command: String) {
    Box(
        modifier = Modifier.fillMaxWidth()
            .background(Color(0xFF080D0A), RoundedCornerShape(8.dp))
            .padding(10.dp),
    ) {
        Text(command, color = Color(0xFF9FB0A5), fontFamily = FontFamily.Monospace, fontSize = 9.sp, lineHeight = 14.sp)
    }
}

@Composable
private fun PreparedCard(state: PreparedState, onRun: () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = Color(0xFF0A140E)),
        border = androidx.compose.foundation.BorderStroke(1.dp, Color(0xFF2E6642)),
        shape = RoundedCornerShape(14.dp),
    ) {
        Column(modifier = Modifier.padding(15.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text("READY FOR HANDOFF", color = Accent, fontFamily = FontFamily.Monospace, fontSize = 9.sp)
            Text("Workspace prepared locally", color = TextMain, fontSize = 17.sp, fontWeight = FontWeight.SemiBold)
            Text(state.repoRoot, color = Muted, fontFamily = FontFamily.Monospace, fontSize = 9.sp)
            CommandLine(state.command)
            Button(
                onClick = onRun,
                modifier = Modifier.fillMaxWidth().height(54.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Accent, contentColor = Color(0xFF061009)),
            ) {
                Text("Copy install & open Termux", fontWeight = FontWeight.Bold)
            }
            if (state.runnerAvailable) {
                Text(
                    "Runner is prepared for the next step. Some tools require arguments or a profile.",
                    color = Muted,
                    fontSize = 10.sp,
                    lineHeight = 15.sp,
                )
                CommandLine("./termux-run.sh [arguments if required]")
            }
            Text(
                "The APK installs dependencies only. It never auto-starts repository code. Paste the copied command in Termux and press Enter.",
                color = Muted,
                fontSize = 10.sp,
                lineHeight = 15.sp,
            )
        }
    }
}

private class PocketPortBridgeClient(private val baseUrl: String = "http://127.0.0.1:33343") {
    fun health(): Result<JSONObject> = request("GET", "/health", null)
    fun plan(repository: String): Result<JSONObject> =
        request("POST", "/api/plan", JSONObject().put("repository", repository))
    fun prepare(repository: String): Result<JSONObject> =
        request("POST", "/api/prepare", JSONObject().put("repository", repository))

    private fun request(method: String, path: String, body: JSONObject?): Result<JSONObject> = runCatching {
        val connection = (URL(baseUrl + path).openConnection() as HttpURLConnection).apply {
            requestMethod = method
            connectTimeout = 2500
            readTimeout = when (path) {
                "/health" -> 2500
                "/api/plan" -> 90000
                "/api/prepare" -> 240000
                else -> 60000
            }
            useCaches = false
            setRequestProperty("Accept", "application/json")
            if (body != null) {
                doOutput = true
                setRequestProperty("Content-Type", "application/json")
                outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
            }
        }
        try {
            val status = connection.responseCode
            val stream = if (status in 200..299) connection.inputStream else connection.errorStream
            val text = stream?.bufferedReader()?.use { it.readText() }.orEmpty()
            val json = if (text.isBlank()) JSONObject() else JSONObject(text)
            if (status !in 200..299) {
                throw IllegalStateException(json.optString("error", "PocketPort Core returned HTTP " + status))
            }
            json
        } finally {
            connection.disconnect()
        }
    }
}

internal fun normalizeRepository(input: String): String? {
    var value = input.trim()
    if (value.isBlank()) return null
    if (value.startsWith("git@github.com:")) value = value.removePrefix("git@github.com:")
    if (value.startsWith("http://") || value.startsWith("https://")) {
        val uri = runCatching { URI(value) }.getOrNull() ?: return null
        if (!uri.host.equals("github.com", ignoreCase = true)) return null
        value = uri.path.orEmpty().trim('/')
    } else {
        value = value.removePrefix("github.com/").trim('/')
    }
    value = value.removeSuffix(".git").trim('/')
    if (!Regex("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$").matches(value)) return null
    return "https://github.com/" + value
}

private fun JSONArray?.toStrings(): List<String> {
    if (this == null) return emptyList()
    return buildList {
        for (index in 0 until length()) {
            val value = optString(index)
            if (value.isNotBlank()) add(value)
        }
    }
}

private fun shellQuote(value: String): String =
    "'" + value.replace("'", "'\"'\"'") + "'"

private fun copyAndOpenTermux(context: Context, command: String) {
    val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
    clipboard.setPrimaryClip(ClipData.newPlainText("PocketPort command", command))
    val launch = context.packageManager.getLaunchIntentForPackage("com.termux")
    if (launch != null) {
        launch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        context.startActivity(launch)
    } else {
        context.startActivity(
            Intent(Intent.ACTION_VIEW, Uri.parse("https://f-droid.org/packages/com.termux/"))
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        )
    }
}
