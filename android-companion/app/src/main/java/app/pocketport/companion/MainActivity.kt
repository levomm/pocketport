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
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
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
import androidx.compose.material3.Icon
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
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
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
import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.sin

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
                    PocketPortRoot()
                }
            }
        }
    }
}


@Composable
private fun PocketPortRoot() {
    var showIntro by remember { mutableStateOf(true) }
    if (showIntro) {
        PocketPortLaunchIntro(onDone = { showIntro = false })
    } else {
        PocketPortApp()
    }
}

@Composable
private fun PocketPortLaunchIntro(onDone: () -> Unit) {
    val progress = remember { Animatable(0f) }

    LaunchedEffect(Unit) {
        progress.animateTo(
            targetValue = 1f,
            animationSpec = tween(durationMillis = 3000, easing = LinearEasing),
        )
        onDone()
    }

    val p = progress.value
    val logoPhase = (p / 0.34f).coerceIn(0f, 1f)
    val portalPhase = ((p - 0.32f) / 0.46f).coerceIn(0f, 1f)
    val streakPhase = ((p - 0.75f) / 0.25f).coerceIn(0f, 1f)
    val glitch = if (p < 0.34f) (sin(p * 170f) * 8f).toFloat() else 0f
    val logoAlpha = when {
        p < 0.05f -> p / 0.05f
        p < 0.31f -> 1f
        p < 0.40f -> ((0.40f - p) / 0.09f).coerceIn(0f, 1f)
        else -> 0f
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(Color(0xFF020403))
            .clickable { onDone() },
    ) {
        Canvas(modifier = Modifier.fillMaxSize()) {
            val cx = size.width / 2f
            val horizonY = size.height * 0.64f
            val center = Offset(cx, size.height * 0.54f)

            if (portalPhase > 0f) {
                val pulse = (1f - abs(portalPhase - 0.55f) * 1.8f).coerceIn(0f, 1f)
                val radius = size.minDimension * (0.07f + portalPhase * 0.34f)
                drawCircle(
                    color = Accent.copy(alpha = 0.55f * pulse),
                    radius = radius,
                    center = center,
                    style = Stroke(width = 2.2f),
                )
                drawCircle(
                    color = Accent.copy(alpha = 0.20f * pulse),
                    radius = radius * 0.72f,
                    center = center,
                    style = Stroke(width = 1.2f),
                )
                drawCircle(
                    color = Accent.copy(alpha = 0.12f * pulse),
                    radius = radius * 1.20f,
                    center = center,
                    style = Stroke(width = 5f),
                )
                drawLine(
                    color = Accent.copy(alpha = 0.48f * pulse),
                    start = Offset(size.width * 0.06f, horizonY),
                    end = Offset(size.width * 0.94f, horizonY),
                    strokeWidth = 1.5f,
                )
            }

            if (streakPhase > 0f) {
                val inner = size.minDimension * (0.08f + streakPhase * 0.08f)
                val outer = size.minDimension * (0.23f + streakPhase * 0.55f)
                repeat(28) { index ->
                    val angle = (index.toDouble() / 28.0) * PI * 2.0
                    val dx = cos(angle).toFloat()
                    val dy = sin(angle).toFloat()
                    drawLine(
                        color = Accent.copy(alpha = (0.08f + streakPhase * 0.34f).coerceAtMost(0.42f)),
                        start = Offset(center.x + dx * inner, center.y + dy * inner),
                        end = Offset(center.x + dx * outer, center.y + dy * outer),
                        strokeWidth = if (index % 4 == 0) 2.2f else 1f,
                    )
                }
            }

            val coreAlpha = ((portalPhase - 0.20f) * 2.2f).coerceIn(0f, 1f) * (1f - streakPhase * 0.7f)
            if (coreAlpha > 0f) {
                drawCircle(
                    color = Color(0xFFD8FFE4).copy(alpha = coreAlpha),
                    radius = 4f + streakPhase * 16f,
                    center = Offset(cx, horizonY),
                )
            }
        }

        Column(
            modifier = Modifier
                .align(Alignment.Center)
                .graphicsLayer {
                    translationX = glitch
                    scaleX = 0.92f + logoPhase * 0.08f
                    scaleY = 0.92f + logoPhase * 0.08f
                    alpha = logoAlpha
                },
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Image(
                painter = painterResource(id = R.drawable.ic_pocketport),
                contentDescription = null,
                modifier = Modifier.size(112.dp),
            )
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("Pocket", color = TextMain, fontSize = 27.sp, fontWeight = FontWeight.SemiBold)
                Text("Port", color = Accent, fontSize = 27.sp, fontWeight = FontWeight.SemiBold)
            }
            Text(
                "GITHUB  →  ANDROID",
                color = Muted,
                fontFamily = FontFamily.Monospace,
                fontSize = 9.sp,
            )
        }

        Row(
            modifier = Modifier
                .align(Alignment.BottomCenter)
                .padding(bottom = 64.dp),
            horizontalArrangement = Arrangement.spacedBy(5.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            repeat(7) { index ->
                val active = p * 7f > index
                Box(
                    modifier = Modifier
                        .size(width = if (index == 3) 28.dp else 22.dp, height = if (index == 3) 7.dp else 5.dp)
                        .graphicsLayer {
                            rotationZ = if (index % 2 == 0) -8f else 8f
                            scaleX = if (active) 1f else 0.82f
                            alpha = if (active) 0.95f else 0.25f
                        }
                        .background(
                            if (active) Accent else Color(0xFF203128),
                            RoundedCornerShape(999.dp),
                        )
                )
            }
        }

        Text(
            "tap to skip",
            modifier = Modifier.align(Alignment.BottomCenter).padding(bottom = 34.dp),
            color = Color(0xFF526158),
            fontFamily = FontFamily.Monospace,
            fontSize = 8.sp,
        )
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
    val installCommand: String,
    val runCommand: String?,
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
    var showPlanDetails by remember { mutableStateOf(false) }

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
        showPlanDetails = false
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
                        val installCommand = "cd " + quoted + " && ./termux-install.sh"
                        val runCommand = if (hasRunner) "cd " + quoted + " && ./termux-run.sh" else null
                        prepared = PreparedState(root, installCommand, runCommand)
                        message = "Workspace ready. Step 2: install. Step 3: start the tool."
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
        HeroBlock()
        StepRail(
            bridgeConnected = bridge.connected,
            planReady = plan != null,
            workspaceReady = prepared != null,
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
            modifier = Modifier.fillMaxWidth().height(56.dp),
            colors = ButtonDefaults.buttonColors(
                containerColor = Accent,
                contentColor = Color(0xFF061009),
                disabledContainerColor = Color(0xFF203128),
                disabledContentColor = Muted,
            ),
        ) {
            val label = when (activeJob) {
                ActiveJob.SCAN -> "Scanning repository..."
                ActiveJob.PREPARE -> "Preparing..."
                ActiveJob.NONE -> "Scan repository"
            }
            Icon(
                painter = painterResource(id = R.drawable.ic_scan),
                contentDescription = null,
                modifier = Modifier.size(18.dp),
            )
            Text("  " + label, fontWeight = FontWeight.Bold)
        }

        CompactBridgeStatus(
            state = bridge,
            onCheck = ::checkBridge,
        )

        if (!bridge.connected) {
            BridgeCard(
                state = bridge,
                onCheck = ::checkBridge,
                onOpenTermux = { copyAndOpenTermux(context, "pocketport serve") },
            )
        }

        if (activeJob != ActiveJob.NONE) {
            OperationProgressCard(activeJob, elapsedSeconds)
        }

        message?.let { StatusStrip(it) }

        plan?.let { current ->
            ResultCard(current)
            ResultActions(
                showDetails = showPlanDetails,
                onToggleDetails = { showPlanDetails = !showPlanDetails },
                onOpenGitHub = { openRepository(context, current.repository) },
                onUsePhone = ::prepareRepository,
                busy = busy,
            )
            if (showPlanDetails) {
                PlanCard(current)
            }
        }

        prepared?.let { ready ->
            PreparedCard(
                state = ready,
                onInstall = { copyAndOpenTermux(context, ready.installCommand) },
                onRun = { ready.runCommand?.let { copyAndOpenTermux(context, it) } },
            )
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
            Image(
                painter = painterResource(id = R.drawable.ic_pocketport),
                contentDescription = "PocketPort",
                modifier = Modifier.size(38.dp),
            )
            Text("  Pocket", color = TextMain, fontSize = 19.sp, fontWeight = FontWeight.SemiBold)
            Text("Port", color = Accent, fontSize = 19.sp, fontWeight = FontWeight.SemiBold)
        }
        Text("ANDROID", color = Muted, fontFamily = FontFamily.Monospace, fontSize = 8.sp)
    }
}

@Composable
private fun HeroBlock() {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(
            "ANDROID / TERMUX COMPATIBILITY",
            color = Accent,
            fontFamily = FontFamily.Monospace,
            fontSize = 9.sp,
        )
        Text(
            "Run more GitHub tools on Android.",
            color = TextMain,
            fontSize = 36.sp,
            lineHeight = 38.sp,
            fontWeight = FontWeight.SemiBold,
        )
        Text(
            "PocketPort scans the repository, finds the Termux path, applies safe fixes, and prepares the handoff on your phone.",
            color = Muted,
            fontSize = 14.sp,
            lineHeight = 20.sp,
        )
    }
}

@Composable
private fun StepRail(
    bridgeConnected: Boolean,
    planReady: Boolean,
    workspaceReady: Boolean,
) {
    val steps = listOf(
        Triple("01", "Scan repo", bridgeConnected),
        Triple("02", "Connect phone", planReady),
        Triple("03", "Run in Termux", workspaceReady),
    )
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(7.dp),
    ) {
        steps.forEach { (number, label, active) ->
            Row(
                modifier = Modifier
                    .weight(1f)
                    .background(if (active) Color(0xFF0C1B12) else Color(0xFF0A0F0C), RoundedCornerShape(999.dp))
                    .border(
                        1.dp,
                        if (active) Color(0xFF2D6A43) else Color(0xFF1F3027),
                        RoundedCornerShape(999.dp),
                    )
                    .padding(horizontal = 9.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.Center,
            ) {
                Text(number, color = Accent, fontFamily = FontFamily.Monospace, fontSize = 8.sp)
                Text("  " + label, color = if (active) TextMain else Muted, fontSize = 8.sp)
            }
        }
    }
}

@Composable
private fun CompactBridgeStatus(state: BridgeState, onCheck: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(Color(0xFF0A100C), RoundedCornerShape(11.dp))
            .border(1.dp, if (state.connected) Color(0xFF21402D) else Line, RoundedCornerShape(11.dp))
            .padding(horizontal = 12.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(
                Modifier
                    .size(8.dp)
                    .background(if (state.connected) Accent else Warning, CircleShape)
            )
            Text(
                if (state.connected) "  PocketPort Core connected" else "  PocketPort Core offline",
                color = if (state.connected) TextMain else Muted,
                fontSize = 11.sp,
            )
        }
        OutlinedButton(onClick = onCheck, enabled = !state.checking) {
            Icon(
                painter = painterResource(id = R.drawable.ic_connect),
                contentDescription = null,
                modifier = Modifier.size(15.dp),
            )
            Text(if (state.checking) "  ..." else "  Check", fontSize = 9.sp)
        }
    }
}

@Composable
private fun ResultCard(plan: PlanState) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = Color(0xFF09110C)),
        border = androidx.compose.foundation.BorderStroke(1.dp, Color(0xFF21402D)),
        shape = RoundedCornerShape(14.dp),
    ) {
        Column(modifier = Modifier.padding(15.dp), verticalArrangement = Arrangement.spacedBy(7.dp)) {
            Text("POCKETPORT RESULT", color = Accent, fontFamily = FontFamily.Monospace, fontSize = 9.sp)
            Text(plan.repository.removePrefix("https://github.com/"), color = TextMain, fontSize = 17.sp, fontWeight = FontWeight.SemiBold)
            Text(
                plan.status.uppercase() + "  ·  " + plan.strategy + "  ·  " + plan.method + "  ·  score " + plan.score,
                color = Muted,
                fontFamily = FontFamily.Monospace,
                fontSize = 9.sp,
            )
        }
    }
}

@Composable
private fun ResultActions(
    showDetails: Boolean,
    onToggleDetails: () -> Unit,
    onOpenGitHub: () -> Unit,
    onUsePhone: () -> Unit,
    busy: Boolean,
) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = onToggleDetails, modifier = Modifier.weight(1f)) {
                Icon(
                    painter = painterResource(id = R.drawable.ic_fixes),
                    contentDescription = null,
                    modifier = Modifier.size(16.dp),
                )
                Text(if (showDetails) "  Hide fixes" else "  View fixes", fontSize = 10.sp)
            }
            OutlinedButton(onClick = onOpenGitHub, modifier = Modifier.weight(1f)) {
                Icon(
                    painter = painterResource(id = R.drawable.ic_github),
                    contentDescription = null,
                    modifier = Modifier.size(16.dp),
                )
                Text("  GitHub ↗", fontSize = 10.sp)
            }
        }
        Button(
            onClick = onUsePhone,
            enabled = !busy,
            modifier = Modifier.fillMaxWidth().height(54.dp),
            colors = ButtonDefaults.buttonColors(containerColor = Accent, contentColor = Color(0xFF061009)),
        ) {
            Icon(
                painter = painterResource(id = R.drawable.ic_phone),
                contentDescription = null,
                modifier = Modifier.size(18.dp),
            )
            Text("  Use on this phone", fontWeight = FontWeight.Bold)
        }
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
                    Icon(
                        painter = painterResource(id = R.drawable.ic_termux),
                        contentDescription = null,
                        modifier = Modifier.size(16.dp),
                    )
                    Text("  Open Termux", fontSize = 10.sp)
                }
                Button(
                    onClick = onCheck,
                    enabled = !state.checking,
                    modifier = Modifier.weight(1f),
                    colors = ButtonDefaults.buttonColors(containerColor = Panel2, contentColor = TextMain),
                ) {
                    Icon(
                        painter = painterResource(id = R.drawable.ic_connect),
                        contentDescription = null,
                        modifier = Modifier.size(16.dp),
                    )
                    Text(if (state.checking) "  Checking..." else "  Check bridge", fontSize = 11.sp)
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
private fun PlanCard(plan: PlanState) {
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
private fun PreparedCard(
    state: PreparedState,
    onInstall: () -> Unit,
    onRun: () -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = Color(0xFF0A140E)),
        border = androidx.compose.foundation.BorderStroke(1.dp, Color(0xFF2E6642)),
        shape = RoundedCornerShape(14.dp),
    ) {
        Column(modifier = Modifier.padding(15.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text("READY ON THIS PHONE", color = Accent, fontFamily = FontFamily.Monospace, fontSize = 9.sp)
            Text("Workspace prepared locally", color = TextMain, fontSize = 17.sp, fontWeight = FontWeight.SemiBold)
            Text(state.repoRoot, color = Muted, fontFamily = FontFamily.Monospace, fontSize = 9.sp)

            Text("02  INSTALL / REPAIR", color = Accent, fontFamily = FontFamily.Monospace, fontSize = 9.sp)
            Text(
                "Run this first. Wait until Termux returns to the prompt without an error.",
                color = Muted,
                fontSize = 10.sp,
                lineHeight = 15.sp,
            )
            CommandLine(state.installCommand)
            Button(
                onClick = onInstall,
                modifier = Modifier.fillMaxWidth().height(54.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Accent, contentColor = Color(0xFF061009)),
            ) {
                Icon(
                    painter = painterResource(id = R.drawable.ic_termux),
                    contentDescription = null,
                    modifier = Modifier.size(18.dp),
                )
                Text("  02  Install in Termux", fontWeight = FontWeight.Bold)
            }

            Text("03  START TOOL", color = Accent, fontFamily = FontFamily.Monospace, fontSize = 9.sp)
            if (state.runCommand != null) {
                Text(
                    "After install succeeds, run this. PocketPort will start the detected Android-compatible entrypoint.",
                    color = Muted,
                    fontSize = 10.sp,
                    lineHeight = 15.sp,
                )
                CommandLine(state.runCommand)
                Button(
                    onClick = onRun,
                    modifier = Modifier.fillMaxWidth().height(54.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = Accent, contentColor = Color(0xFF061009)),
                ) {
                    Icon(
                        painter = painterResource(id = R.drawable.ic_termux),
                        contentDescription = null,
                        modifier = Modifier.size(18.dp),
                    )
                    Text("  03  Start in Termux", fontWeight = FontWeight.Bold)
                }
            } else {
                Text(
                    "PocketPort did not find a trustworthy launch command. Installation can finish, but automatic start is unavailable.",
                    color = Warning,
                    fontSize = 10.sp,
                    lineHeight = 15.sp,
                )
            }

            Text(
                "Buttons copy the exact command and open Termux. Repository code is never started silently.",
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

private fun openRepository(context: Context, repository: String) {
    context.startActivity(
        Intent(Intent.ACTION_VIEW, Uri.parse(repository))
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    )
}

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
