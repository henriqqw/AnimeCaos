package com.animecaos.mobile.data

import com.animecaos.mobile.BuildConfig
import okhttp3.HttpUrl
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import okhttp3.Interceptor
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.io.IOException
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference

object ApiClient {
    private fun normalizeBaseUrl(rawUrl: String): String {
        return if (rawUrl.endsWith("/")) rawUrl else "$rawUrl/"
    }

    private fun parseBaseUrl(rawUrl: String): HttpUrl? {
        val normalized = normalizeBaseUrl(rawUrl)
        return normalized.toHttpUrlOrNull()?.newBuilder()?.encodedPath("/")?.build()
    }

    // VPS production server first, then emulator fallbacks for local development.
    private val vpsBaseUrl = listOf("http://10.0.0.4:8000/")
    private val emulatorFallbackUrls = listOf(
        "http://10.0.2.2:8000/",
        "http://10.0.3.2:8000/",
        "http://127.0.0.1:8000/",
        "http://localhost:8000/",
    )
    private val fallbackBaseUrls = vpsBaseUrl + emulatorFallbackUrls

    private val baseCandidates: List<HttpUrl> = buildList {
        // Production VPS URL first (configured in build.gradle.kts).
        parseBaseUrl(BuildConfig.API_BASE_URL)?.let(::add)
        // Emulator/local fallbacks for development.
        fallbackBaseUrls.forEach { fallback ->
            parseBaseUrl(fallback)?.let(::add)
        }
    }.distinctBy { "${it.scheme}://${it.host}:${it.port}" }

    private val activeBaseRef = AtomicReference(
        baseCandidates.firstOrNull()
            ?: "http://10.0.2.2:8000/".toHttpUrlOrNull()!!
    )

    val baseUrl: String
        get() = activeBaseRef.get().toString()

    private val logging = HttpLoggingInterceptor().apply {
        level = HttpLoggingInterceptor.Level.BASIC
    }

    private val endpointFailover = Interceptor { chain ->
        val originalRequest = chain.request()
        val activeBase = activeBaseRef.get()
        val orderedCandidates = buildList {
            add(activeBase)
            addAll(baseCandidates.filterNot { it == activeBase })
        }.distinctBy { "${it.scheme}://${it.host}:${it.port}" }

        val failures = mutableListOf<String>()
        var lastError: IOException? = null

        for (candidate in orderedCandidates) {
            val rewrittenUrl = originalRequest.url.newBuilder()
                .scheme(candidate.scheme)
                .host(candidate.host)
                .port(candidate.port)
                .build()

            val attemptRequest = originalRequest.newBuilder().url(rewrittenUrl).build()
            try {
                val response = chain.proceed(attemptRequest)
                // Cache the host that worked so future requests try it first.
                activeBaseRef.set(candidate)
                return@Interceptor response
            } catch (error: IOException) {
                lastError = error
                failures.add("${candidate} (${error.javaClass.simpleName})")
            }
        }

        throw IOException(
            "Backend indisponivel. Verifique se o servidor esta rodando (uvicorn app.main:app --host 0.0.0.0 --port 8000). " +
                "Endpoints testados: ${failures.joinToString()}",
            lastError,
        )
    }

    private val client = OkHttpClient.Builder()
        .addInterceptor(endpointFailover)
        .addInterceptor(logging)
        // Reduced connect timeout: 5s per candidate is enough for a local backend.
        // With ~4 candidates this means ~20s worst-case instead of the previous ~60s.
        .connectTimeout(5, TimeUnit.SECONDS)
        // Scraping endpoints can take longer when multiple sources are queried.
        .readTimeout(90, TimeUnit.SECONDS)
        .writeTimeout(90, TimeUnit.SECONDS)
        .callTimeout(120, TimeUnit.SECONDS)
        .build()

    val api: ApiService by lazy {
        Retrofit.Builder()
            .baseUrl(baseCandidates.firstOrNull()?.toString() ?: "http://10.0.2.2:8000/")
            .client(client)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(ApiService::class.java)
    }

    fun absoluteUrl(pathOrUrl: String?): String? {
        if (pathOrUrl.isNullOrBlank()) return null
        if (pathOrUrl.startsWith("http://") || pathOrUrl.startsWith("https://")) return pathOrUrl
        val normalized = if (pathOrUrl.startsWith("/")) pathOrUrl.substring(1) else pathOrUrl
        return normalizeBaseUrl(baseUrl) + normalized
    }
}
