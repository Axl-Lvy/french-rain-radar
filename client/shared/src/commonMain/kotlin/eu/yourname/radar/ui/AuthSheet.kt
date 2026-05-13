package eu.yourname.radar.ui

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
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

@Composable
fun AuthSheet(
    onSubmit: (baseUrl: String, username: String, password: String) -> Unit,
    initialBaseUrl: String = "http://localhost:8080",
    initialUsername: String = "",
    modifier: Modifier = Modifier,
) {
    var baseUrl by remember { mutableStateOf(initialBaseUrl) }
    var username by remember { mutableStateOf(initialUsername) }
    var password by remember { mutableStateOf("") }
    Column(modifier = modifier.padding(24.dp)) {
        Text("Connect to your radar server")
        OutlinedTextField(value = baseUrl, onValueChange = { baseUrl = it }, label = { Text("Base URL") })
        OutlinedTextField(value = username, onValueChange = { username = it }, label = { Text("Username") })
        OutlinedTextField(
            value = password,
            onValueChange = { password = it },
            label = { Text("Password") },
            visualTransformation = PasswordVisualTransformation(),
        )
        Button(onClick = { onSubmit(baseUrl, username, password) }) { Text("Connect") }
    }
}
