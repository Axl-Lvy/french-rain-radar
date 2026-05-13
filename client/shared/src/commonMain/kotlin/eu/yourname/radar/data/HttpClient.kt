package eu.yourname.radar.data

import io.ktor.client.HttpClient
import io.ktor.client.plugins.auth.Auth
import io.ktor.client.plugins.auth.providers.BasicAuthCredentials
import io.ktor.client.plugins.auth.providers.basic
import io.ktor.client.plugins.contentnegotiation.ContentNegotiation
import io.ktor.client.plugins.defaultRequest
import io.ktor.http.URLBuilder
import io.ktor.serialization.kotlinx.json.json
import kotlinx.serialization.json.Json

data class BackendConfig(
    val baseUrl: String,
    val username: String,
    val password: String,
)

object RadarHttpClient {
    val json: Json = Json {
        ignoreUnknownKeys = true
        explicitNulls = false
        prettyPrint = false
    }

    fun create(config: BackendConfig): HttpClient = HttpClient {
        install(ContentNegotiation) { json(json) }
        install(Auth) {
            basic {
                credentials {
                    BasicAuthCredentials(username = config.username, password = config.password)
                }
                sendWithoutRequest { true }
            }
        }
        defaultRequest {
            url(URLBuilder(config.baseUrl).build().toString())
        }
    }
}
