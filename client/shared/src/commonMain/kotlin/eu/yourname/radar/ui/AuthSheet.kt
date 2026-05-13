package eu.yourname.radar.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import eu.yourname.radar.Config

/**
 * First-launch prompt for HTTP Basic credentials. The backend URL is baked
 * into [Config.BASE_URL]; only the credentials are entered at runtime.
 *
 * The submit callback receives plain text — the caller is responsible for
 * persisting them (we use [eu.yourname.radar.settings.SettingsStore]).
 */
@Composable
fun AuthSheet(
    onSubmit: (username: String, password: String) -> Unit,
    initialUsername: String = "",
    modifier: Modifier = Modifier,
    paddingValues: PaddingValues = PaddingValues(24.dp),
) {
    var username by remember { mutableStateOf(initialUsername) }
    var password by remember { mutableStateOf("") }
    val canSubmit = username.isNotBlank() && password.isNotEmpty()
    Column(
        modifier = modifier.fillMaxWidth().padding(paddingValues),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("Connect to ${Config.BASE_URL}", style = MaterialTheme.typography.titleMedium)
        OutlinedTextField(
            value = username,
            onValueChange = { username = it },
            label = { Text("Username") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        OutlinedTextField(
            value = password,
            onValueChange = { password = it },
            label = { Text("Password") },
            visualTransformation = PasswordVisualTransformation(),
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        Button(
            enabled = canSubmit,
            onClick = { onSubmit(username.trim(), password) },
        ) { Text("Connect") }
    }
}
