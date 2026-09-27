package ee.osx01.pocketport

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.weight
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

private const val POCKETPORT_WEB = "https://pocketport.vercel.app"
private const val BRIDGE_COMMAND = "pocketport serve"
private const val TERMUX_PACKAGE = "com.termux"

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            PocketPortTheme {
                PocketPortScreen()
            }
        }
    }
}

@Composable
private fun PocketPortTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = MaterialTheme.colorScheme.copy(
            primary = Color(0xFF72F59C),
            onPrimary = Color(0xFF061009),
            background = Color(0xFF070A09),
            surface = Color(0xFF0D1210),
            onBackground = Color(0xFFEDF4EF),
            onSurface = Color(0xFFEDF4EF),
        ),
        content = content,
    )
}

@Composable
private fun PocketPortScreen() {
    val context = LocalContext.current
    var repository by remember { mutableStateOf("") }
    var message by remember { mutableStateOf("Companion shell ready. Local bridge wiring is next.") }

    Surface(
        modifier = Modifier
            .fillMaxSize()
            .background(Color(0xFF070A09)),
        color = Color(0xFF070A09),
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = 20.dp, vertical = 28.dp),
            verticalArrangement = Arrangement.Top,
        ) {
            Text(
                text = "PocketPort",
                color = Color(0xFFEDF4EF),
                fontSize = 28.sp,
                fontWeight = FontWeight.Bold,
            )
            Text(
                text = "ANDROID / TERMUX COMPANION",
                color = Color(0xFF72F59C),
                fontFamily = FontFamily.Monospace,
                fontSize = 11.sp,
            )

            Spacer(Modifier.height(32.dp))

            Text(
                text = "Run more GitHub tools on Android.",
                color = Color(0xFFEDF4EF),
                fontSize = 32.sp,
                lineHeight = 34.sp,
                fontWeight = FontWeight.SemiBold,
            )
            Spacer(Modifier.height(10.dp))
            Text(
                text = "Scan a repository in PocketPort Web or start the local Termux bridge from one place.",
                color = Color(0xFF8D9B92),
                fontSize = 14.sp,
                lineHeight = 20.sp,
            )

            Spacer(Modifier.height(28.dp))

            OutlinedTextField(
                value = repository,
                onValueChange = { repository = it },
                modifier = Modifier.fillMaxWidth(),
                label = { Text("GitHub repository") },
                placeholder = { Text("owner/repository") },
                singleLine = true,
            )

            Spacer(Modifier.height(12.dp))

            Button(
                onClick = {
                    val slug = normalizeRepo(repository)
                    if (slug == null) {
                        message = "Use owner/repository or a GitHub URL."
                    } else {
                        val url = "$POCKETPORT_WEB/scan/${Uri.encode(slug.first)}/${Uri.encode(slug.second)}"
                        context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
                        message = "Opening PocketPort scan."
                    }
                },
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(10.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = Color(0xFF72F59C),
                    contentColor = Color(0xFF061009),
                ),
            ) {
                Text("Scan repository")
            }

            Spacer(Modifier.height(10.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                OutlinedButton(
                    onClick = {
                        copyToClipboard(context, BRIDGE_COMMAND)
                        message = if (openTermux(context)) {
                            "Copied '$BRIDGE_COMMAND' and opened Termux."
                        } else {
                            "Copied '$BRIDGE_COMMAND'. Termux is not installed."
                        }
                    },
                    modifier = Modifier.weight(1f),
                    shape = RoundedCornerShape(10.dp),
                ) {
                    Text("Start bridge")
                }

                OutlinedButton(
                    onClick = {
                        context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(POCKETPORT_WEB)))
                        message = "Opening PocketPort Web."
                    },
                    modifier = Modifier.weight(1f),
                    shape = RoundedCornerShape(10.dp),
                ) {
                    Text("Open web")
                }
            }

            Spacer(Modifier.height(26.dp))

            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(Color(0xFF0D1210), RoundedCornerShape(12.dp))
                    .padding(14.dp),
            ) {
                Text(
                    text = "PHONE BRIDGE",
                    color = Color(0xFF5F6D64),
                    fontFamily = FontFamily.Monospace,
                    fontSize = 10.sp,
                )
                Spacer(Modifier.height(7.dp))
                Text(
                    text = message,
                    color = Color(0xFFB9C5BD),
                    fontSize = 13.sp,
                    lineHeight = 18.sp,
                )
            }
        }
    }
}

private fun normalizeRepo(raw: String): Pair<String, String>? {
    val cleaned = raw.trim()
        .removePrefix("https://github.com/")
        .removePrefix("http://github.com/")
        .removePrefix("github.com/")
        .removeSuffix("/")
        .removeSuffix(".git")

    val parts = cleaned.split("/").filter { it.isNotBlank() }
    if (parts.size != 2) return null
    if (parts.any { !it.matches(Regex("[A-Za-z0-9_.-]+")) }) return null
    return parts[0] to parts[1]
}

private fun copyToClipboard(context: Context, text: String) {
    val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
    clipboard.setPrimaryClip(ClipData.newPlainText("PocketPort command", text))
}

private fun openTermux(context: Context): Boolean {
    val intent = context.packageManager.getLaunchIntentForPackage(TERMUX_PACKAGE) ?: return false
    intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    context.startActivity(intent)
    return true
}
